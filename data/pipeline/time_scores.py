"""Validate a score snapshot and optionally re-evaluate historical activity.

This is preparation for routing, not a per-request full-Ireland computation.
No inventory download or lighting rebuild is performed.
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from data.pipeline.build import load_scores, validate_time
from data.pipeline.edges import file_sha256, load_edges, metric_geometry
from data.pipeline.footfall import match_footfall

LOCAL_ZONE = ZoneInfo("Europe/Dublin")


def departure_slot(departure_time: datetime) -> tuple[int, int]:
    if not isinstance(departure_time, datetime) or departure_time.utcoffset() is None:
        raise ValueError("departure_time must be a timezone-aware datetime")
    local = departure_time.astimezone(LOCAL_ZONE)
    return local.weekday(), local.hour


def validate_profiles(profiles: dict, sources: dict) -> None:
    """Reject ambiguous, corrupt or untraceable profiles before using any bin."""
    if not isinstance(profiles, dict) or type(profiles.get("schema_version")) is not int or profiles["schema_version"] != 1:
        raise ValueError("Unsupported footfall profile schema")
    if profiles.get("timezone") != "Europe/Dublin" or profiles.get("timezone_verified") is not False:
        raise ValueError("Footfall profiles must retain the unverified Europe/Dublin time assumption")
    hashes = profiles.get("source_sha256", {})
    if not isinstance(sources, dict) or not isinstance(hashes, dict):
        raise ValueError("Invalid footfall profile provenance")
    for name, source in (("counts", "footfall_counts"), ("locations", "footfall_locations")):
        entry = sources.get(source)
        if not isinstance(entry, dict):
            raise ValueError("Invalid footfall source provenance")
        expected = entry.get("sha256")
        if not isinstance(expected, str) or len(expected) != 64 or hashes.get(name) != expected:
            raise ValueError("Footfall profile source hash mismatch")
    counters = profiles.get("counters")
    if not isinstance(counters, list):
        raise ValueError("Footfall profiles must contain a counters list")
    identities = set()
    for counter in counters:
        if not isinstance(counter, dict):
            raise ValueError("Invalid footfall counter")
        identity = counter.get("counter_id")
        if not isinstance(identity, str) or not identity.strip() or identity in identities:
            raise ValueError("Duplicate or invalid footfall counter identity")
        identities.add(identity)
        for key, low, high in (("longitude", -11, -5), ("latitude", 51, 56)):
            value = counter.get(key)
            if type(value) not in (float, int) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError("Invalid Ireland footfall counter coordinates")
        bins = counter.get("bins")
        if not isinstance(bins, list):
            raise ValueError("Footfall counter must contain bins")
        seen = set()
        for observation in bins:
            if not isinstance(observation, dict):
                raise ValueError("Invalid footfall observation")
            day, hour = observation.get("weekday"), observation.get("hour")
            validate_time(day, hour)
            if (day, hour) in seen:
                raise ValueError("Duplicate footfall weekday/hour bin")
            seen.add((day, hour))
            mean, count = observation.get("mean_count"), observation.get("sample_count")
            if type(mean) not in (int, float) or not math.isfinite(mean) or mean < 0:
                raise ValueError("Invalid footfall mean_count")
            if type(count) is not int or count < 1:
                raise ValueError("Invalid footfall sample_count")


def load_time_scores(bundle_path: str | Path, edges_path: str | Path, *,
                     departure_time: datetime | None = None) -> tuple[dict, dict]:
    """Return validated rows keyed by exact (u,v,key) and their time metadata.

    Omitted departure time preserves the original snapshot. An explicit instant
    recomputes activity from all counters with that local weekday/hour, including
    reassignment when the original counter has no observation for the new slot.
    Missing slots stay unknown. Both autumn repeated hours use the same historical
    wall-clock bin; the source cannot distinguish them.
    """
    if departure_time is not None:
        day, hour = departure_slot(departure_time)
    bundle_path, edges_path = Path(bundle_path), Path(edges_path)
    bundle_hash, graph_hash = file_sha256(bundle_path), file_sha256(edges_path)
    document = json.loads(bundle_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("time_slice"), dict):
        raise ValueError("Score bundle requires time_slice metadata")
    if type(document.get("schema_version")) is not int or document["schema_version"] != 1:
        raise ValueError("Unsupported edge bundle schema")
    if not isinstance(document.get("graph"), dict):
        raise ValueError("Score bundle requires graph metadata")
    original = document["time_slice"]
    if original.get("timezone") != "Europe/Dublin":
        raise ValueError("Unsupported score bundle timezone")
    rows = load_scores(bundle_path, edges_path, weekday=original.get("weekday"), hour=original.get("hour"))
    result_slice = dict(original)
    if departure_time is not None:
        profiles = document.get("footfall_profiles")
        validate_profiles(profiles, document.get("sources", {}))
        parameters = document.get("parameters")
        if not isinstance(parameters, dict):
            raise ValueError("Missing score bundle parameters")
        radius = parameters.get("footfall_radius_m")
        if type(radius) not in (float, int) or not math.isfinite(radius) or radius <= 0:
            raise ValueError("Invalid footfall_radius_m")
        # Remove other bins once, rather than scanning 168 bins on every edge.
        selected = {**profiles, "counters": [
            {**counter, "bins": [b for b in counter["bins"] if (b["weekday"], b["hour"]) == (day, hour)]}
            for counter in profiles["counters"]
            if any((b["weekday"], b["hour"]) == (day, hour) for b in counter["bins"])
        ]}
        for edge in load_edges(edges_path):
            identity = edge["u"], edge["v"], edge["key"]
            rows[identity] = {**rows[identity], **match_footfall(
                metric_geometry(edge["geometry"]), selected, day, hour, radius_m=radius)}
        result_slice = {"weekday": day, "hour": hour, "timezone": "Europe/Dublin",
                        "timezone_verified": False}
    if bundle_hash != file_sha256(bundle_path) or graph_hash != file_sha256(edges_path):
        raise ValueError("Score bundle or graph changed during evaluation; retry with stable inputs")
    return rows, result_slice
