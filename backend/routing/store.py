"""Picks the graph for a request: the cached Dublin area, else an on-demand tile.

Outside the cached area a tile around the two points is fetched from OSM
once and cached to disk, so routing works across Ireland without holding a
national graph in memory.
"""

import math

from . import config
from .engine import (
    LatLon,
    OutsideCoverage,
    Preferences,
    RoutingEngine,
    RoutingError,
    _haversine_m,
)
from .graph import build_graph, graph_bbox
from .scores import load_edge_scores

BBox = tuple[float, float, float, float]
TILE_GRID_DEG = 0.01  # tile edges snap outward to this grid so tiles are reused


class TooFar(RoutingError):
    code = "too_far"


class GraphUnavailable(RoutingError):
    code = "graph_unavailable"


def _inside(point: LatLon, bbox: BBox) -> bool:
    lat, lon = point
    left, bottom, right, top = bbox
    return left <= lon <= right and bottom <= lat <= top


def tile_bbox(origin: LatLon, destination: LatLon) -> BBox:
    """Bounding box around both points plus a margin, snapped to the tile grid."""
    lat = (origin[0] + destination[0]) / 2
    margin_lat = config.TILE_MARGIN_M / 111_320
    margin_lon = margin_lat / math.cos(math.radians(lat))

    def down(value: float) -> float:
        return round(math.floor(value / TILE_GRID_DEG) * TILE_GRID_DEG, 2)

    def up(value: float) -> float:
        return round(math.ceil(value / TILE_GRID_DEG) * TILE_GRID_DEG, 2)

    return (
        down(min(origin[1], destination[1]) - margin_lon),
        down(min(origin[0], destination[0]) - margin_lat),
        up(max(origin[1], destination[1]) + margin_lon),
        up(max(origin[0], destination[0]) + margin_lat),
    )


class GraphStore:
    def __init__(self, area: str = config.DEFAULT_AREA, allow_download: bool = True):
        self.allow_download = allow_download
        self.bundle = load_edge_scores()
        self._engines: dict[str, tuple[BBox, RoutingEngine]] = {}
        self._add(area, config.AREAS[area])

    def _add(self, name: str, bbox: BBox) -> RoutingEngine:
        G = build_graph(name, bbox)
        engine = RoutingEngine(G, self.bundle.scores)
        self._engines[name] = (graph_bbox(G) or bbox, engine)
        return engine

    def engine_for(self, origin: LatLon, destination: LatLon) -> tuple[str, RoutingEngine]:
        for name, (bbox, engine) in self._engines.items():
            if _inside(origin, bbox) and _inside(destination, bbox):
                return name, engine

        for point in (origin, destination):
            if not all(math.isfinite(c) for c in point) or not _inside(point, config.IRELAND_BBOX):
                raise OutsideCoverage("Both points must be on the island of Ireland.")
        apart_km = float(
            _haversine_m(*(math.radians(c) for c in (*origin, *destination)))
        ) / 1000
        if apart_km > config.MAX_ON_DEMAND_KM:
            raise TooFar(
                f"Points are {apart_km:.1f} km apart; walking routes outside the "
                f"cached area are limited to {config.MAX_ON_DEMAND_KM:.0f} km."
            )
        if not self.allow_download:
            raise OutsideCoverage("These points are outside the cached walking network.")

        bbox = tile_bbox(origin, destination)
        name = "tile_" + "_".join(f"{c:.2f}" for c in bbox)
        try:
            return name, self._add(name, bbox)
        except Exception as error:  # OSM download or parse failure
            raise GraphUnavailable(
                f"Could not fetch the walking network for this area: {error}"
            ) from error


_store: GraphStore | None = None


def get_store() -> GraphStore:
    """Shared store. Call once at API startup so the first request is fast."""
    global _store
    if _store is None:
        _store = GraphStore()
    return _store


def get_route(
    origin: LatLon,
    destination: LatLon,
    prefs: Preferences = Preferences(),
    max_extra_minutes: float | None = config.DEFAULT_MAX_EXTRA_MIN,
) -> dict:
    """Fastest and Night routes between two (lat, lon) points in Ireland."""
    area, engine = get_store().engine_for(origin, destination)
    result = engine.route(origin, destination, prefs, max_extra_minutes)
    result["area"] = area
    # Activity scores are historical means for this weekday and hour only.
    result["time_slice"] = get_store().bundle.time_slice
    return result
