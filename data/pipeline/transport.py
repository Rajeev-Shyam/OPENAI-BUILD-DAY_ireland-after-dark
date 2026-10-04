"""Export NTA stop points and audit static/realtime identifiers, without routing."""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time

from .download import atomic_write
from .gtfs import build_gtfs
from .gtfs_realtime import ENDPOINTS, MAX_BYTES, freshness, normalize_feed
from .nta_download import file_hash, registry


def _readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)


def _metadata(connection):
    metadata = {key: json.loads(value) for key, value in connection.execute("SELECT key, value FROM metadata")}
    if metadata.get("schema_version") != 1 or not metadata.get("archive_sha256"):
        raise ValueError("Unsupported or missing GTFS database metadata")
    return metadata


def _write_json(output, document, protected=()):
    if Path(output).resolve() in {Path(p).resolve() for p in protected}:
        raise ValueError("Output must not overwrite an input")
    atomic_write(Path(output), (json.dumps(document, indent=2, allow_nan=False) + "\n").encode())


def build_from_manifest(source, raw_dir, output):
    """Build only the exact immutable archive declared by a verified manifest."""
    sources = registry()
    if source not in sources:
        raise ValueError("Unknown NTA static source")
    raw_dir = Path(raw_dir)
    manifest_path = raw_dir / (source + ".manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("schema_version") != 1 or manifest.get("source") != source
            or manifest.get("source_url") != sources[source]["url"]):
        raise ValueError("Static source manifest does not match the NTA registry")
    snapshot = (raw_dir / manifest["snapshot"]).resolve()
    if raw_dir.resolve() not in snapshot.parents:
        raise ValueError("Static snapshot must be inside its manifest directory")
    if Path(output).resolve() in {snapshot, manifest_path.resolve(), (raw_dir / sources[source]["filename"]).resolve()}:
        raise ValueError("Database output must not overwrite source input")
    if file_hash(snapshot) != manifest.get("sha256"):
        raise ValueError("Static snapshot checksum mismatch; download again")
    return build_gtfs(snapshot, output, source_id=source, source_url=manifest["source_url"])


def export_stops(database, output):
    """Write all geolocated source stop/station/entrance records as GeoJSON.

    Map points do not imply a currently running service, accessible platform,
    public shelter or realtime coverage. Missing point locations are counted.
    """
    features = []
    skipped = 0
    with closing(_readonly(database)) as connection:
        metadata = _metadata(connection)
        for stop_id, name, latitude, longitude, kind, parent in connection.execute(
                "SELECT stop_id, stop_name, stop_lat, stop_lon, location_type, parent_station FROM stops ORDER BY stop_id"):
            if latitude == "" or longitude == "":
                skipped += 1
                continue
            lat, lon = float(latitude), float(longitude)
            if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
                raise ValueError("Invalid stop coordinates in processed database")
            features.append({"type": "Feature", "id": stop_id,
                             "properties": {"stop_id": stop_id, "stop_name": name,
                                            "location_type": kind or "0", "parent_station": parent or None},
                             "geometry": {"type": "Point", "coordinates": [lon, lat]}})
    document = {"type": "FeatureCollection", "features": features,
                "metadata": {"schema_version": 1, "source_id": metadata.get("source_id"),
                             "archive_sha256": metadata["archive_sha256"],
                             "source_url": metadata.get("source_url"),
                             "feature_count": len(features), "records_without_coordinates": skipped,
                             "attribution": "National Transport Authority, CC BY 4.0; transformed to GeoJSON",
                             "limitations": "Static stop locations; not evidence of service now, shelter, accessibility or realtime coverage."}}
    _write_json(output, document, (database,))
    return document["metadata"]


def _check_descriptor(connection, descriptor):
    """Check exact membership only; never guess a trip from a display name."""
    issues, trip_id, static_trip = [], descriptor.get("trip_id"), None
    relationship = descriptor.get("schedule_relationship", "SCHEDULED")
    if trip_id:
        static_trip = connection.execute("SELECT route_id, service_id FROM trips WHERE trip_id=?", (trip_id,)).fetchone()
        if static_trip is None:
            issues.append("dynamic_trip_not_in_static" if relationship in {"ADDED", "UNSCHEDULED", "DUPLICATED", "NEW"}
                          else "trip_id_not_in_static")
    else:
        issues.append("trip_id_absent_not_resolved")
    route_id = descriptor.get("route_id")
    if route_id:
        if connection.execute("SELECT 1 FROM routes WHERE route_id=?", (route_id,)).fetchone() is None:
            issues.append("route_id_not_in_static")
        if static_trip is not None and static_trip[0] != route_id:
            issues.append("trip_route_mismatch")
    return issues, trip_id, static_trip, relationship


def _check_stop(connection, trip_id, static_trip, reference):
    issues = []
    stop_id, sequence = reference.get("stop_id"), reference.get("stop_sequence")
    if stop_id and connection.execute("SELECT 1 FROM stops WHERE stop_id=?", (stop_id,)).fetchone() is None:
        issues.append("stop_id_not_in_static")
    if static_trip is not None:
        if sequence is not None:
            stop = connection.execute("SELECT stop_id FROM stop_times WHERE trip_id=? AND stop_sequence=?", (trip_id, sequence)).fetchone()
            if stop is None:
                issues.append("stop_sequence_not_on_trip")
            elif stop_id and stop[0] != stop_id:
                issues.append("stop_id_sequence_mismatch")
        elif stop_id and connection.execute("SELECT 1 FROM stop_times WHERE trip_id=? AND stop_id=? LIMIT 1", (trip_id, stop_id)).fetchone() is None:
            issues.append("stop_id_not_on_trip")
    return issues


def audit_links(database, normalized, *, now=None):
    """Report identifier compatibility and freshly assessed timestamps.

    A match is not proof of correct service-date matching, an active departure,
    a prediction, or that the static feed is the generation used by the server.
    """
    now = time.time() if now is None else now
    if not math.isfinite(now):
        raise ValueError("Audit time must be finite")
    if normalized.get("schema_version") != 1:
        raise ValueError("Unsupported normalized realtime schema")
    policy = normalized["freshness_policy_seconds"]
    if type(policy) not in (int, float) or not math.isfinite(policy) or policy <= 0:
        raise ValueError("Invalid realtime freshness policy")
    state = freshness(normalized["header"].get("timestamp"), now, policy)
    rows = []
    with closing(_readonly(database)) as connection:
        metadata = _metadata(connection)
        for category in ("trip_updates", "vehicle_positions"):
            for item in normalized[category]:
                payload = item["data"]
                issues, trip_id, static_trip, relationship = _check_descriptor(connection, payload.get("trip", {}))
                references = payload.get("stop_time_update", []) if category == "trip_updates" else [{
                    "stop_id": payload.get("stop_id"), "stop_sequence": payload.get("current_stop_sequence")}]
                for reference in references:
                    if category == "trip_updates" and not reference.get("stop_id") and "stop_sequence" not in reference:
                        issues.append("stop_reference_absent")
                    issues.extend(_check_stop(connection, trip_id, static_trip, reference))
                observation = freshness(payload.get("timestamp"), now, policy)
                rows.append({"entity_id": item["entity_id"], "entity_type": category,
                             "trip_id": trip_id, "schedule_relationship": relationship,
                             "identifier_status": "matched" if not issues else "unresolved",
                             "issues": sorted(set(issues)), "observation_freshness": observation,
                             "fresh_observation": state["status"] == "fresh" and observation["status"] == "fresh"})
        for item in normalized["alerts"]:
            issues = []
            for selector in item["data"].get("informed_entity", []):
                if selector.get("trip"):
                    issues.extend(_check_descriptor(connection, selector["trip"])[0])
                for field, table in (("agency_id", "agency"), ("route_id", "routes"), ("stop_id", "stops")):
                    if selector.get(field) and connection.execute(f"SELECT 1 FROM {table} WHERE {field}=?", (selector[field],)).fetchone() is None:
                        issues.append(field + "_not_in_static")
            rows.append({"entity_id": item["entity_id"], "entity_type": "alerts",
                         "identifier_status": "matched" if not issues else "unresolved",
                         "issues": sorted(set(issues)), "fresh_observation": False,
                         "active_period_evaluated": False})
    return {"schema_version": 1, "assessed_at_unix": now,
            "static_source_id": metadata.get("source_id"), "static_archive_sha256": metadata["archive_sha256"],
            "feed_freshness": state, "entities": rows,
            "counts": {"checked_entities": len(rows),
                       "matched_identifiers": sum(row["identifier_status"] == "matched" for row in rows),
                       "unresolved_identifiers": sum(row["identifier_status"] == "unresolved" for row in rows),
                       "unsupported_entities": len(normalized.get("unsupported_entities", []))},
            "limitations": ["Identifier audit only; service-date and trip-instance matching not implemented.",
                            "Missing realtime entities are unknown, not on time or cancelled.",
                            "Matched or fresh records do not establish availability or a boardable trip.",
                            "Feed freshness is reassessed at audit time; this report ages immediately.",
                            "Use the NTA companion static feed; matching IDs alone cannot prove feed generation alignment.",
                            "Alerts are preserved and selectors checked; active periods are not evaluated."]}


def audit_snapshot(database, manifest_path, output, *, now=None):
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("source_url") not in ENDPOINTS.values():
        raise ValueError("Unsupported NTA realtime manifest")
    snapshot = (manifest_path.parent / manifest["snapshot"]).resolve()
    if manifest_path.parent.resolve() not in snapshot.parents:
        raise ValueError("Realtime snapshot must be inside its manifest directory")
    with snapshot.open("rb") as handle:
        body = handle.read(MAX_BYTES + 1)
    if (len(body) > MAX_BYTES or len(body) != manifest.get("bytes")
            or hashlib.sha256(body).hexdigest() != manifest.get("sha256")):
        raise ValueError("Realtime snapshot size/hash does not match provenance")
    normalized = normalize_feed(body, now=now)
    report = audit_links(database, normalized, now=now)
    report["realtime_sha256"] = manifest["sha256"]
    report["realtime_source_url"] = manifest["source_url"]
    _write_json(output, report, (database, manifest_path, snapshot))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="Build static SQLite from a verified download manifest")
    build.add_argument("--source", choices=list(registry()), default="nta_gtfs_realtime")
    build.add_argument("--raw-dir", type=Path, default=Path("data/raw/nta"))
    build.add_argument("--output", type=Path, required=True)
    stops = sub.add_parser("stops", help="Export static stop locations for a map")
    stops.add_argument("--database", type=Path, required=True)
    stops.add_argument("--output", type=Path, required=True)
    audit = sub.add_parser("audit", help="Audit a raw realtime snapshot against a processed timetable")
    audit.add_argument("--database", type=Path, required=True)
    audit.add_argument("--realtime-manifest", type=Path, required=True)
    audit.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            result = build_from_manifest(args.source, args.raw_dir, args.output)
        elif args.command == "stops":
            result = export_stops(args.database, args.output)
        else:
            result = audit_snapshot(args.database, args.realtime_manifest, args.output)
        print(json.dumps(result.get("counts", result), allow_nan=False))
    except (ValueError, OSError, KeyError, TypeError, sqlite3.Error) as error:
        parser.exit(1, f"Transport handoff failed: {error}\n")


if __name__ == "__main__":
    main()
