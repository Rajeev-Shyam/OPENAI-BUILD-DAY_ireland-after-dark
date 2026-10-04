"""Validate the routing team's GeoJSON without changing graph identities."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform

METRIC_CRS = "EPSG:2157"
TO_METRIC = Transformer.from_crs("EPSG:4326", METRIC_CRS, always_xy=True)


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def edge_id(value: object) -> str:
    # Floats lose precision for large OSM IDs and bool is an int subclass.
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("u, v and key must be nonempty strings or integers")
    text = str(value)
    if not text or text.strip() != text:
        raise ValueError("u, v and key must be nonempty and have no surrounding whitespace")
    return text


def metric_geometry(geometry):
    return transform(TO_METRIC.transform, geometry)


def load_edges(path: str | Path) -> list[dict]:
    """Read RFC 7946 lon/lat LineStrings; reject unusable/misidentified graphs."""
    with Path(path).open(encoding="utf-8") as handle:
        document = json.load(handle)
    if not isinstance(document, dict) or document.get("type") != "FeatureCollection":
        raise ValueError("edges must be a GeoJSON FeatureCollection")
    if "crs" in document:
        raise ValueError("GeoJSON must be RFC 7946 WGS84 lon/lat with no crs member")
    features = document.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("edge collection must contain at least one feature")
    edges, seen = [], set()
    for index, feature in enumerate(features):
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise ValueError(f"feature {index}: expected a GeoJSON Feature")
        properties = feature.get("properties")
        if not isinstance(properties, dict) or not all(k in properties for k in ("u", "v", "key")):
            raise ValueError(f"feature {index}: missing u, v or key")
        identity = tuple(edge_id(properties[k]) for k in ("u", "v", "key"))
        if identity in seen:
            raise ValueError(f"duplicate graph edge {identity}")
        seen.add(identity)
        raw_geometry = feature.get("geometry")
        if not isinstance(raw_geometry, dict) or raw_geometry.get("type") != "LineString":
            raise ValueError(f"edge {identity}: geometry must be LineString")
        coordinates = raw_geometry.get("coordinates")
        if not isinstance(coordinates, list) or len(coordinates) < 2:
            raise ValueError(f"edge {identity}: need at least two coordinates")
        for coordinate in coordinates:
            if not isinstance(coordinate, (list, tuple)) or len(coordinate) != 2:
                raise ValueError(f"edge {identity}: need two-dimensional lon/lat coordinates")
            if any(isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n)
                   for n in coordinate):
                raise ValueError(f"edge {identity}: coordinates must be finite numbers")
            lon, lat = coordinate
            if not (-11.0 <= lon <= -5.0 and 51.0 <= lat <= 56.0):
                raise ValueError(f"edge {identity}: coordinates outside Ireland bounds or axes reversed")
        geometry = shape(raw_geometry)
        projected = metric_geometry(geometry)
        if not geometry.is_valid or not math.isfinite(projected.length) or projected.length <= 0:
            raise ValueError(f"edge {identity}: invalid or zero-length geometry")
        edges.append(dict(zip(("u", "v", "key"), identity), geometry=geometry))
    return edges
