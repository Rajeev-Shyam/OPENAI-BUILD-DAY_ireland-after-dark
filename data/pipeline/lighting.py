"""Recorded lighting asset proximity; never measured brightness or safety.

All public inputs are WGS84 longitude/latitude. Distance operations use Irish
Transverse Mercator (EPSG:2157). Unknown inventory coverage is kept distinct
from a surveyed edge with zero nearby assets.
"""

from __future__ import annotations

import csv
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from pyproj import Transformer
from shapely.geometry import LineString, Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform, unary_union
from shapely.strtree import STRtree


@dataclass(frozen=True)
class Light:
    asset_id: str
    longitude: float
    latitude: float
    unit_type: str = ""


def clean_lights(path: str | Path) -> tuple[list[Light], dict]:
    """Read DCC CSV; report rejected rows and deduplicate by asset identity.

    Coordinates outside a generous Ireland envelope are rejected as malformed,
    not used to infer coverage. Conflicting duplicate IDs fail rather than
    selecting an arbitrary position. Different assets at one position remain.
    """
    lights: dict[str, Light] = {}
    report = {"input_rows": 0, "accepted_rows": 0, "duplicate_rows": 0,
              "rejected_rows": 0, "rejection_reasons": {}, "unit_types": {}}
    rejected: Counter = Counter()
    unit_types: Counter = Counter()
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("Lighting CSV has no header")
        names = [name.strip().lower() for name in reader.fieldnames]
        if len(set(names)) != len(names):
            raise ValueError("Lighting CSV has duplicate column names")
        reader.fieldnames = names
        required = {"id", "latitude", "longitude", "unit_type"}
        if not required.issubset(names):
            raise ValueError(f"Lighting CSV missing columns: {sorted(required - set(names))}")
        for row in reader:
            report["input_rows"] += 1
            if None in row or any(value is None for value in row.values()):
                rejected["malformed_row"] += 1
                continue
            asset_id = row["id"].strip()
            if not asset_id:
                rejected["missing_asset_id"] += 1
                continue
            try:
                longitude, latitude = float(row["longitude"]), float(row["latitude"])
            except (ValueError, TypeError):
                rejected["invalid_coordinates"] += 1
                continue
            if not (math.isfinite(longitude) and math.isfinite(latitude)
                    and -11 <= longitude <= -5 and 51 <= latitude <= 56):
                rejected["invalid_coordinates"] += 1
                continue
            light = Light(asset_id, longitude, latitude, row["unit_type"].strip())
            if asset_id in lights:
                if lights[asset_id] != light:
                    raise ValueError(f"Conflicting lighting records for asset ID {asset_id}")
                report["duplicate_rows"] += 1
                continue
            lights[asset_id] = light
            unit_types[light.unit_type] += 1
    report.update(accepted_rows=len(lights), rejected_rows=sum(rejected.values()),
                  rejection_reasons=dict(rejected), unit_types=dict(unit_types))
    if not lights:
        raise ValueError(f"Lighting CSV contains no valid assets: {report}")
    return list(lights.values()), report


def enrich_lighting(
    edges: Iterable[Mapping], lights: Iterable[Light], *, buffer_m: float = 20.0,
    coverage_geometry: BaseGeometry | None = None,
    metric_crs: str = "EPSG:2157",
) -> list[dict]:
    """Return metrics keyed by the caller's exact ``(u, v, key)`` identifiers.

    ``geometry`` must be a WGS84 LineString. An asset may support more than one
    nearby edge; this is proximity matching, not proven street ownership.
    ``coverage_geometry`` is optional WGS84 Polygon/MultiPolygon whose inventory
    applicability has been independently verified, never a point-derived bbox.
    Lighting score is the prototype 100 * length fraction within ``buffer_m``
    of recorded assets, nullable if there is no evidence. It is not confidence.
    """
    if not math.isfinite(buffer_m) or buffer_m <= 0:
        raise ValueError("buffer_m must be finite and positive")
    # Keep units auditable: alternate projections may not use metres.
    if metric_crs != "EPSG:2157":
        raise ValueError("Only metric_crs='EPSG:2157' is supported")
    project = Transformer.from_crs("EPSG:4326", metric_crs, always_xy=True).transform
    points = []
    seen_assets = set()
    for light in lights:
        if light.asset_id in seen_assets:
            raise ValueError(f"Duplicate asset ID supplied: {light.asset_id}")
        seen_assets.add(light.asset_id)
        if not (-11 <= light.longitude <= -5 and 51 <= light.latitude <= 56):
            raise ValueError(f"Invalid lighting coordinates: {light.asset_id}")
        points.append(transform(project, Point(light.longitude, light.latitude)))
    tree = STRtree(points) if points else None
    coverage_metric = None
    if coverage_geometry is not None:
        if (coverage_geometry.geom_type not in {"Polygon", "MultiPolygon"}
                or coverage_geometry.is_empty or not coverage_geometry.is_valid):
            raise ValueError("Coverage must be a valid nonempty WGS84 Polygon/MultiPolygon")
        west, south, east, north = coverage_geometry.bounds
        if not (-11 <= west <= east <= -5 and 51 <= south <= north <= 56):
            raise ValueError("Coverage must use WGS84 coordinates within the Ireland envelope")
        coverage_metric = transform(project, coverage_geometry)
        if not coverage_metric.is_valid:
            raise ValueError("Coverage could not be projected to EPSG:2157")
    results = []
    seen_edges = set()
    for edge in edges:
        identifiers = {name: edge[name] for name in ("u", "v", "key")}
        identity = tuple(identifiers.values())
        if identity in seen_edges:
            raise ValueError(f"Duplicate edge ID: {identity}")
        seen_edges.add(identity)
        geometry = edge["geometry"]
        if not isinstance(geometry, LineString) or geometry.is_empty or not geometry.is_valid:
            raise ValueError(f"Edge {identity} must have a valid nonempty LineString")
        if geometry.has_z:
            raise ValueError(f"Edge {identity} must use two-dimensional coordinates")
        if any(not (-11 <= x <= -5 and 51 <= y <= 56) for x, y in geometry.coords):
            raise ValueError(f"Edge {identity} is outside the supported Ireland envelope")
        line = transform(project, geometry)
        length = line.length
        if not math.isfinite(length) or length <= 0:
            raise ValueError(f"Edge {identity} must have positive finite length")
        indices = tree.query(line.buffer(buffer_m)) if tree is not None else []
        nearby = [points[int(i)] for i in indices if points[int(i)].distance(line) <= buffer_m]
        fraction = 0.0
        if nearby:
            footprint = unary_union([point.buffer(buffer_m, quad_segs=32) for point in nearby])
            fraction = min(1.0, max(0.0, line.intersection(footprint).length / length))
        declared = coverage_metric is not None and coverage_metric.covers(line)
        positive_evidence = fraction > 0
        has_data = bool(declared or positive_evidence)
        basis = ("declared_inventory_coverage" if declared else
                 "recorded_asset_proximity" if positive_evidence else "unknown")
        results.append({**identifiers,
                        "lighting_asset_count": len(nearby),
                        "lighting_density_per_km": len(nearby) * 1000 / length if has_data else None,
                        "lighting_proximity_fraction": fraction if has_data else None,
                        "lighting_score": fraction * 100 if has_data else None,
                        "has_lighting_data": has_data,
                        "lighting_data_coverage_fraction": 1.0 if declared else fraction,
                        "lighting_coverage_basis": basis,
                        "lighting_buffer_m": buffer_m})
    return results
