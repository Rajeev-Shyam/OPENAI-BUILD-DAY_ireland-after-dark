"""Build an auditable, time-specific edge-score bundle for the routing team."""
from __future__ import annotations

import argparse
import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from data.pipeline.edges import file_sha256, load_edges, metric_geometry
from data.pipeline.footfall import build_profiles, match_footfall
from data.pipeline.lighting import clean_lights, enrich_lighting

SCHEMA_VERSION = 1
CORE_SOURCES = ("lighting", "footfall_counts", "footfall_locations")


def atomic_json(path: str | Path, document: dict) -> None:
    """Publish one complete bundle, never a partially written consumer file."""
    path = Path(path)
    # Serialise before creating a temporary file: nonfinite output is a hard error.
    content = json.dumps(document, indent=2, allow_nan=False, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix="." + path.name + ".", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def validate_time(weekday: int, hour: int) -> None:
    if type(weekday) is not int or not 0 <= weekday <= 6:
        raise ValueError("weekday must be an integer 0..6 (Monday=0)")
    if type(hour) is not int or not 0 <= hour <= 23:
        raise ValueError("hour must be an integer 0..23")


def source_provenance(raw_dir: Path) -> dict:
    """Require downloader provenance; never silently bless manually edited data."""
    provenance = {}
    for name in CORE_SOURCES:
        path = raw_dir / f"{name}.csv"
        manifest_path = raw_dir / f"{name}.manifest.json"
        if not manifest_path.exists():
            raise ValueError(f"Missing {name}.manifest.json; run python -m data.pipeline.download first")
        entry = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(entry, dict) or entry.get("source") != name or not entry.get("sha256"):
            raise ValueError(f"No download provenance for {name}")
        if file_sha256(path) != entry["sha256"]:
            raise ValueError(f"Source checksum mismatch for {name}; download it again")
        provenance[name] = entry
    return provenance


def build_bundle(edges_path: str | Path, raw_dir: str | Path, *, weekday: int,
                 hour: int, lighting_buffer_m: float = 20.0,
                 footfall_radius_m: float = 100.0) -> dict:
    validate_time(weekday, hour)
    for value in (lighting_buffer_m, footfall_radius_m):
        if not math.isfinite(value) or value <= 0:
            raise ValueError("Matching distances must be finite positive metres")
    raw_dir, edges_path = Path(raw_dir), Path(edges_path)
    provenance = source_provenance(raw_dir)
    graph_hash = file_sha256(edges_path)
    edges = load_edges(edges_path)
    graph_description = json.loads(edges_path.read_text(encoding="utf-8"))
    lights, lighting_quality = clean_lights(raw_dir / "lighting.csv")
    profiles = build_profiles(raw_dir / "footfall_counts.csv", raw_dir / "footfall_locations.csv")
    lighting = enrich_lighting(edges, lights, buffer_m=lighting_buffer_m)
    rows = []
    for edge, metrics in zip(edges, lighting):
        projected = metric_geometry(edge["geometry"])
        rows.append({**metrics, "length_m": projected.length,
                     **match_footfall(projected, profiles, weekday, hour, radius_m=footfall_radius_m)})
    # Catch inputs replaced during a build, not just modifications before starting.
    if graph_hash != file_sha256(edges_path):
        raise ValueError("Graph file changed during processing; retry with a stable snapshot")
    source_provenance(raw_dir)
    for name, entry in provenance.items():
        if file_sha256(raw_dir / f"{name}.csv") != entry["sha256"]:
            raise ValueError(f"Source {name} changed during processing; retry")
    total_length = sum(row["length_m"] for row in rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "graph": {"sha256": graph_hash, "edge_count": len(edges), "input_crs": "EPSG:4326",
                  "measurement_crs": "EPSG:2157", "identity_fields": ["u", "v", "key"],
                  "input_description": graph_description.get("description"),
                  "is_test_fixture": graph_description.get("is_test_fixture", False)},
        "time_slice": {"weekday": weekday, "hour": hour, "timezone": "Europe/Dublin",
                       "timezone_verified": False},
        "parameters": {"lighting_buffer_m": lighting_buffer_m, "footfall_radius_m": footfall_radius_m,
                       "footfall_full_zero_days_excluded": True,
                       "lighting_score": "100 * recorded-asset proximity length fraction",
                       "footfall_score": "min(100, 100 * log1p(counter mean count) / log1p(1000))"},
        "sources": provenance,
        "quality": {"lighting": lighting_quality,
                    "edge_summary": {
                        "edge_count": len(rows),
                        "edges_with_lighting_evidence": sum(r["has_lighting_data"] for r in rows),
                        "edges_with_footfall_evidence": sum(r["has_footfall_data"] for r in rows),
                        "lighting_supported_length_fraction": sum(r["length_m"] * r["lighting_data_coverage_fraction"] for r in rows) / total_length,
                        "footfall_supported_length_fraction": sum(r["length_m"] * r["footfall_coverage_fraction"] for r in rows) / total_length,
                    }},
        "limitations": [
            "Prototype preference scores, not measures of safety or a probability of harm.",
            "Recorded lighting assets do not establish brightness, operation or complete inventory coverage.",
            "Counter proximity is a local historical activity proxy, not a pedestrian count on each street.",
            "Euclidean matching can cross rivers, walls and parallel streets; topology was not verified.",
            "Footfall timestamps are assumed Europe/Dublin wall time; publisher timezone remains unverified.",
            "Flags mean some evidence exists; use supported-length fractions, freshness and sample counts for confidence.",
            "This bundle is valid only for its graph fingerprint and selected weekday/hour.",
        ],
        "edges": rows,
        "footfall_profiles": profiles,
    }


def load_scores(bundle_path: str | Path, edges_path: str | Path, *, weekday: int, hour: int) -> dict:
    """Consumer guard: refuse a graph/time mismatch instead of silently misrouting."""
    validate_time(weekday, hour)
    document = json.loads(Path(bundle_path).read_text(encoding="utf-8"))
    if document.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported edge bundle schema")
    if document.get("graph", {}).get("sha256") != file_sha256(edges_path):
        raise ValueError("Graph fingerprint mismatch; rebuild scores for this graph")
    time_slice = document.get("time_slice", {})
    if (time_slice.get("weekday"), time_slice.get("hour")) != (weekday, hour):
        raise ValueError("Time slice mismatch; rebuild or evaluate profiles for the requested time")
    expected = {(e["u"], e["v"], e["key"]): metric_geometry(e["geometry"]).length
                for e in load_edges(edges_path)}
    result = {}
    rows = document.get("edges")
    if not isinstance(rows, list):
        raise ValueError("Score bundle must contain an edges list")
    for row in rows:
        if not isinstance(row, dict) or any(not isinstance(row.get(k), str) for k in ("u", "v", "key")):
            raise ValueError("Score edge identities must be strings")
        identity = tuple(row[k] for k in ("u", "v", "key"))
        if identity in result:
            raise ValueError("Duplicate edge identity in score bundle")
        length = row.get("length_m")
        if (type(length) not in (int, float) or not math.isfinite(length) or length <= 0
                # PROJ/GEOS across Windows/Linux differed by at most 2.24 nm on
                # the same fingerprinted graph. Relative-only tolerance rejects
                # tiny edges; allow 10 nm absolute roundoff, not changed geometry.
                or identity not in expected or not math.isclose(length, expected[identity], rel_tol=1e-9, abs_tol=1e-8)):
            raise ValueError("Edge length does not match graph geometry")
        for score in ("lighting_score", "footfall_score"):
            if score not in row:
                raise ValueError(f"Missing {score}")
            value = row[score]
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 100):
                raise ValueError(f"Invalid {score}")
        for flag, fraction, score in (
            ("has_lighting_data", "lighting_data_coverage_fraction", "lighting_score"),
            ("has_footfall_data", "footfall_coverage_fraction", "footfall_score"),
        ):
            value = row.get(fraction)
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"Invalid {fraction}")
            if type(row.get(flag)) is not bool:
                raise ValueError(f"Invalid {flag}")
            if row[flag] != (value > 0) or row[flag] != (row[score] is not None):
                raise ValueError(f"Inconsistent {flag}, coverage fraction and score")
        count = row.get("lighting_asset_count")
        buffer_m = row.get("lighting_buffer_m")
        if type(count) is not int or count < 0:
            raise ValueError("Invalid lighting_asset_count")
        if type(buffer_m) not in (int, float) or not math.isfinite(buffer_m) or buffer_m <= 0:
            raise ValueError("Invalid lighting_buffer_m")
        proximity = row.get("lighting_proximity_fraction")
        density = row.get("lighting_density_per_km")
        basis = row.get("lighting_coverage_basis")
        if row["has_lighting_data"]:
            if type(proximity) not in (int, float) or not math.isfinite(proximity) or not 0 <= proximity <= 1:
                raise ValueError("Invalid lighting_proximity_fraction")
            if not math.isclose(row["lighting_score"], proximity * 100, abs_tol=1e-9):
                raise ValueError("Lighting score does not match proximity fraction")
            if (type(density) not in (int, float) or not math.isfinite(density)
                    or not math.isclose(density, count * 1000 / length, abs_tol=1e-9)):
                raise ValueError("Lighting density does not match asset count and length")
            if basis == "recorded_asset_proximity":
                if count == 0 or not math.isclose(proximity, row["lighting_data_coverage_fraction"], abs_tol=1e-9):
                    raise ValueError("Recorded asset evidence does not match supported length")
            elif basis != "declared_inventory_coverage" or row["lighting_data_coverage_fraction"] != 1:
                raise ValueError("Invalid lighting coverage basis")
        elif proximity is not None or density is not None or basis != "unknown":
            raise ValueError("Unknown lighting must not contain invented observations")
        samples = row.get("footfall_sample_count")
        mean = row.get("expected_pedestrians_per_hour")
        counter = row.get("footfall_counter_id")
        distance = row.get("footfall_counter_distance_m")
        if type(samples) is not int or samples < 0:
            raise ValueError("Invalid footfall_sample_count")
        if row["has_footfall_data"]:
            if (samples == 0 or not isinstance(counter, str) or not counter
                    or type(mean) not in (int, float) or not math.isfinite(mean) or mean < 0
                    or type(distance) not in (int, float) or not math.isfinite(distance) or distance < 0):
                raise ValueError("Footfall evidence requires valid mean, counter and sample count")
            if not math.isclose(row["footfall_score"], min(100, 100 * math.log1p(mean) / math.log1p(1000)), abs_tol=1e-9):
                raise ValueError("Footfall score does not match counter mean")
        elif samples != 0 or mean is not None or counter is not None or distance is not None:
            raise ValueError("Unknown footfall must not contain invented observations")
        result[identity] = row
    if set(result) != set(expected):
        raise ValueError("Score bundle does not match the graph's edge identities")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edges", type=Path, required=True, help="Routing team's WGS84 edge GeoJSON")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/edge_scores.json"))
    parser.add_argument("--weekday", type=int, required=True, help="Monday=0 ... Sunday=6")
    parser.add_argument("--hour", type=int, required=True, help="Assumed Europe/Dublin hour, 0..23")
    parser.add_argument("--lighting-buffer-m", type=float, default=20.0)
    parser.add_argument("--footfall-radius-m", type=float, default=100.0)
    args = parser.parse_args(argv)
    try:
        protected = [args.edges] + [args.raw_dir / f"{s}{suffix}" for s in CORE_SOURCES for suffix in (".csv", ".manifest.json")]
        if args.output.resolve() in {path.resolve() for path in protected}:
            raise ValueError("Output must not overwrite an input or download manifest")
        bundle = build_bundle(args.edges, args.raw_dir, weekday=args.weekday, hour=args.hour,
                              lighting_buffer_m=args.lighting_buffer_m, footfall_radius_m=args.footfall_radius_m)
        atomic_json(args.output, bundle)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f"Data pipeline failed: {exc}\n")
    print(json.dumps({"output": str(args.output), **bundle["quality"]["edge_summary"]}, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
