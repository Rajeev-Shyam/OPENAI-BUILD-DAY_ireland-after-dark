"""Historical DCC pedestrian profiles; proximity is a proxy, never live activity.

Only exact source series identifiers (outer whitespace stripped) are joined. A
nearby counter cannot establish activity on another street or across a river.
"""
from __future__ import annotations

import csv
import hashlib
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from pyproj import Transformer
from shapely.geometry import Point

PROJECT = Transformer.from_crs("EPSG:4326", "EPSG:2157", always_xy=True)
LOCAL_ZONE = ZoneInfo("Europe/Dublin")


def _read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        headers = [h.strip() for h in (reader.fieldnames or [])]
        if not headers or len(headers) != len(set(headers)):
            raise ValueError("CSV has missing or duplicate column names")
        reader.fieldnames = headers
        rows = list(reader)
    if any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ValueError("CSV rows do not match header width")
    return headers, rows


def _count(value):
    value = value.strip()
    if not value:
        return None
    # Do not silently coerce sensor error strings, negative or fractional counts.
    if not value.isascii() or not value.isdigit():
        raise ValueError(f"Invalid pedestrian count: {value!r}")
    return int(value)


def _uncertain_local_time(stamp):
    first = stamp.replace(tzinfo=LOCAL_ZONE, fold=0)
    second = stamp.replace(tzinfo=LOCAL_ZONE, fold=1)
    return (first.utcoffset() != second.utcoffset()
            or first.astimezone(timezone.utc).astimezone(LOCAL_ZONE).replace(tzinfo=None) != stamp)


def build_profiles(counts_path, locations_path, exclude_full_zero_days=True):
    """Build observed weekday/hour bins, provenance and a quality audit.

    Monday=0. Naive source timestamps are *assumed* Europe/Dublin wall clock;
    the publisher metadata does not confirm this. Duplicate/ambiguous hours
    are excluded, never averaged twice. Missing readings remain missing.
    """
    headers, rows = _read_csv(counts_path)
    location_headers, locations = _read_csv(locations_path)
    required = {"_id", "Counter Locations", "Eco-Visio Oupput", "Latitude", "Longitude", "User Type"}
    if not required.issubset(location_headers):
        raise ValueError("Unexpected pedestrian location schema")
    if "Time" not in headers or any("cycl" in h.lower() for h in headers):
        raise ValueError("Expected pedestrian counts, received cyclist or unsupported schema")
    # The verified 2026 source has one total followed by IN and OUT columns.
    series = {}
    for header in headers:
        if header == "Time" or header.endswith((" IN", " OUT")):
            continue
        incoming = [header + suffix for suffix in (" IN", " Pedestrian IN", " Pedestrians IN", " Peds IN", " Channel 1 IN") if header + suffix in headers]
        outgoing = [header + suffix for suffix in (" OUT", " Pedestrian OUT", " Pedestrians OUT", " Peds OUT", " Channel 2 OUT") if header + suffix in headers]
        if len(incoming) != 1 or len(outgoing) != 1:
            # Dawson/Molesworth is an explicit source naming exception.
            if header == "Dawson Street/Molesworth Pedestrian":
                incoming, outgoing = ["Dawson Street/Molesworth IN"], ["Dawson Street/Molesworth OUT"]
            else:
                raise ValueError(f"Unrecognised total/IN/OUT structure for {header!r}")
        if incoming[0] not in headers or outgoing[0] not in headers:
            raise ValueError(f"Missing direction column for {header!r}")
        series[header] = (incoming[0], outgoing[0])
    mapped = []
    used_ids, used_names = set(), set()
    excluded = []
    for row in locations:
        if row["User Type"].strip().lower() != "pedestrians":
            raise ValueError("Non-pedestrian counter in pedestrian locations")
        name, counter_id = row["Eco-Visio Oupput"].strip(), row["_id"].strip()
        if not name or not counter_id or name in used_names or counter_id in used_ids:
            raise ValueError("Duplicate or empty pedestrian counter identifier")
        used_names.add(name)
        used_ids.add(counter_id)
        lon, lat = float(row["Longitude"]), float(row["Latitude"])
        if not (-11 <= lon <= -5 and 51 <= lat <= 56):
            raise ValueError(f"Invalid Ireland counter coordinates: {name}")
        if any(word in name.lower() for word in ("removed", "nonresponsive", "nonrepsonsive", "overcounting")):
            excluded.append({"series": name, "reason": "publisher flags faulty or removed counter"})
        elif name not in series:
            excluded.append({"series": name, "reason": "no exact total-series match"})
        else:
            mapped.append({"counter_id": counter_id, "series": name, "name": row["Counter Locations"].strip(), "longitude": lon, "latitude": lat})
    if not mapped:
        raise ValueError("No pedestrian total series matched location identifiers")
    timestamps = []
    for row in rows:
        try:
            stamp = datetime.strptime(row["Time"].strip(), "%d/%m/%Y %H:%M")
        except ValueError as exc:
            raise ValueError(f"Invalid footfall timestamp {row['Time']!r}") from exc
        if stamp.minute != 0:
            raise ValueError("Footfall rows must be hourly")
        timestamps.append(stamp)
    if not timestamps:
        raise ValueError("Footfall CSV has no observations")
    duplicates = {t for t, n in Counter(timestamps).items() if n > 1}
    diagnostic = {"row_count": len(rows), "duplicate_timestamps": sorted(t.isoformat() for t in duplicates),
                  "excluded_timestamp_rows": 0, "excluded_counters": excluded,
                  "unmapped_total_series": sorted(set(series) - {c["series"] for c in mapped})}
    observations = defaultdict(list)
    mismatch_count = Counter()
    for stamp, row in zip(timestamps, rows):
        # Validate counts even for excluded timestamp rows; corrupt input fails closed.
        counts = {h: _count(row[h]) for h in headers if h != "Time"}
        if stamp in duplicates or _uncertain_local_time(stamp):
            diagnostic["excluded_timestamp_rows"] += 1
            continue
        for counter in mapped:
            name = counter["series"]
            total = counts[name]
            incoming, outgoing = (counts[h] for h in series[name])
            if total is None:
                continue  # Never fabricate a total from partially available directions.
            if incoming is not None and outgoing is not None and total != incoming + outgoing:
                mismatch_count[name] += 1
                continue
            observations[name].append((stamp, total))
    for counter in mapped:
        observations_for_counter = observations[counter["series"]]
        days = defaultdict(list)
        for stamp, count in observations_for_counter:
            days[stamp.date()].append(count)
        # A full observed zero day could be a fault; exclude conservatively,
        # keeping ordinary zero hours among otherwise active days.
        zero_days = {day for day, values in days.items() if exclude_full_zero_days and len(values) == 24 and not any(values)}
        bins = defaultdict(list)
        for stamp, count in observations_for_counter:
            if stamp.date() not in zero_days:
                bins[(stamp.weekday(), stamp.hour)].append(count)
        counter["bins"] = [{"weekday": day, "hour": hour, "mean_count": sum(values) / len(values),
                            "sample_count": len(values)} for (day, hour), values in sorted(bins.items())]
        counter["quality"] = {"excluded_full_zero_days": sorted(str(d) for d in zero_days),
                               "total_direction_mismatches": mismatch_count[counter["series"]],
                               "observed_hours": sum(len(values) for values in bins.values())}
    return {"schema_version": 1, "timezone": "Europe/Dublin", "timezone_verified": False,
            "exclude_full_zero_days": exclude_full_zero_days,
            "time_basis": "source wall-clock labels; Europe/Dublin assumed, DST/duplicate hours excluded",
            "observation_start": min(timestamps).isoformat(), "observation_end": max(timestamps).isoformat(),
            "source_sha256": {"counts": hashlib.sha256(Path(counts_path).read_bytes()).hexdigest(),
                              "locations": hashlib.sha256(Path(locations_path).read_bytes()).hexdigest()},
            "counters": mapped, "diagnostics": diagnostic}


def match_footfall(edge_geometry_projected, profiles, weekday, hour, radius_m=100.0):
    """Assign one counter with valid temporal data, using EPSG:2157 metres.

    Pick the largest supported portion of the edge, then nearest midpoint and
    stable counter id. Single-counter coverage avoids blending incompatible
    point counts. This is a bounded proximity assumption, not street evidence.
    """
    if type(weekday) is not int or not 0 <= weekday <= 6 or type(hour) is not int or not 0 <= hour <= 23:
        raise ValueError("weekday must be 0..6 and hour 0..23")
    if not math.isfinite(radius_m) or radius_m <= 0:
        raise ValueError("Footfall radius must be positive finite metres")
    edge = edge_geometry_projected
    if edge.is_empty or not edge.is_valid or edge.geom_type != "LineString" or not math.isfinite(edge.length) or edge.length <= 0:
        raise ValueError("Expected a valid nonzero projected LineString")
    result = {"has_footfall_data": False, "footfall_coverage_fraction": 0.0,
              "footfall_score": None, "expected_pedestrians_per_hour": None,
              "footfall_counter_id": None, "footfall_sample_count": 0,
              "footfall_counter_distance_m": None}
    candidates = []
    for counter in profiles["counters"]:
        observation = next((b for b in counter["bins"] if b["weekday"] == weekday and b["hour"] == hour), None)
        if observation is None or observation["sample_count"] < 1:
            continue
        point = Point(*PROJECT.transform(counter["longitude"], counter["latitude"]))
        if edge.distance(point) >= radius_m:
            continue
        fraction = min(1.0, edge.intersection(point.buffer(radius_m)).length / edge.length)
        if fraction > 0:
            candidates.append((-fraction, edge.interpolate(0.5, normalized=True).distance(point), counter["counter_id"], observation, edge.distance(point)))
    if candidates:
        negative_fraction, _, counter_id, observation, distance = min(candidates, key=lambda c: c[:3])
        count = observation["mean_count"]
        result.update(has_footfall_data=True, footfall_coverage_fraction=-negative_fraction,
                      footfall_score=min(100.0, 100 * math.log1p(count) / math.log1p(1000)),
                      expected_pedestrians_per_hour=count, footfall_counter_id=counter_id,
                      footfall_sample_count=observation["sample_count"], footfall_counter_distance_m=distance)
    return result
