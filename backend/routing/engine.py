"""Fastest and Night routes on the walking graph.

Deterministic: the same graph, scores and request give the same routes.
Coordinates in are (lat, lon); GeoJSON out is [lon, lat].
"""

import math
from dataclasses import dataclass

import networkx as nx
import numpy as np
import shapely
from pyproj import Transformer
from shapely.geometry import LineString

from . import config
from .scores import EdgeKey, EdgeScore, apply_scores, quiet_term

EARTH_RADIUS_M = 6_371_009  # same radius OSMnx uses for edge lengths
LatLon = tuple[float, float]


class RoutingError(Exception):
    """Carries a stable code so the API can map it to a response."""

    code = "routing_error"


class OutsideCoverage(RoutingError):
    code = "outside_coverage"


class SamePoint(RoutingError):
    code = "same_point"


class NoRoute(RoutingError):
    code = "no_route"


@dataclass(frozen=True)
class Preferences:
    """Preference strengths, 0 and up. Zero switches a factor off."""

    well_lit: float = 1.0
    busier: float = 0.5
    crossings: float = 1.0
    less_walking: float = 0.0  # 0 to 1; 1 ignores every other preference

    def scaled(self, factor: float = 1.0) -> "Preferences":
        factor *= 1.0 - min(1.0, max(0.0, self.less_walking))
        return Preferences(
            well_lit=max(0.0, self.well_lit) * factor,
            busier=max(0.0, self.busier) * factor,
            crossings=max(0.0, self.crossings) * factor,
        )


def night_cost(data: dict, prefs: Preferences, quiet: float | None = None) -> float:
    """NightCost of one edge, in metre-equivalents. Never below its length.

    quiet replaces the edge's own activity term when activity comes from a
    requested time slot instead of the bundle's snapshot.
    """
    quiet = data["quiet"] if quiet is None else quiet
    return (
        data["length"] * (1.0 + prefs.well_lit * data["dark"] + prefs.busier * quiet)
        + prefs.crossings * data["crossing_m"]
    )


def _haversine_m(lat1, lon1, lat2, lon2):
    """Great-circle metres. Inputs in radians; works on numpy arrays."""
    a = (
        np.sin((lat2 - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(a))


class RoutingEngine:
    def __init__(self, G: nx.MultiDiGraph, scores: dict[EdgeKey, EdgeScore] | None = None):
        self.G = G
        self.scores_matched = apply_scores(G, scores or {})
        self._to_metric = Transformer.from_crs(
            "EPSG:4326", config.METRIC_CRS, always_xy=True
        ).transform
        # Index one geometry per street: the walking graph stores both directions.
        self._streets = [
            (u, v, key)
            for u, v, key in G.edges(keys=True)
            if u <= v or not G.has_edge(v, u, key)
        ]
        lines = np.array([LineString(self._coords(edge)) for edge in self._streets], dtype=object)
        self._tree = shapely.STRtree(
            shapely.transform(
                lines, lambda xy: np.column_stack(self._to_metric(xy[:, 0], xy[:, 1]))
            )
        )

    def snap(self, point: LatLon) -> tuple[int, float]:
        """Nearer end node of the closest walking path, and metres to that path."""
        lat, lon = point
        if not (math.isfinite(lat) and math.isfinite(lon)):
            raise OutsideCoverage("Coordinates must be finite numbers.")
        here = shapely.Point(self._to_metric(lon, lat))
        nearest = self._tree.nearest(here)
        distance = float(self._tree.geometries[nearest].distance(here))
        if distance > config.MAX_SNAP_M:
            raise OutsideCoverage(
                f"No walking path within {config.MAX_SNAP_M:.0f} m of "
                f"({lat:.5f}, {lon:.5f}); nearest is {distance:.0f} m away."
            )
        u, v, _ = self._streets[nearest]

        def metres_to(node: int) -> float:
            xy = self._to_metric(self.G.nodes[node]["x"], self.G.nodes[node]["y"])
            return math.dist(xy, (here.x, here.y))

        return min((u, v), key=metres_to), distance

    def _path(
        self, source: int, target: int, prefs: Preferences | None, activity=None
    ) -> list[EdgeKey]:
        """Cheapest edge sequence. prefs=None minimises distance only."""
        if prefs is None:
            cost = lambda u, v, key, data: data["length"]
        elif activity is None:
            cost = lambda u, v, key, data: night_cost(data, prefs)
        else:
            quiet, unknown = activity.quiet, quiet_term(None, 0.0)
            cost = lambda u, v, key, data: night_cost(
                data, prefs, quiet.get((u, v, key), unknown)
            )

        def weight(u, v, parallel):
            return min(cost(u, v, key, data) for key, data in parallel.items())

        try:
            _, nodes = nx.bidirectional_dijkstra(self.G, source, target, weight=weight)
        except nx.NetworkXNoPath:
            raise NoRoute("No walking route connects these two points.") from None
        return [
            (u, v, min(self.G[u][v], key=lambda key: cost(u, v, key, self.G[u][v][key])))
            for u, v in zip(nodes, nodes[1:])
        ]

    def streets_within(self, point: LatLon, radius_m: float) -> list[EdgeKey]:
        """Indexed streets within radius_m of a (lat, lon) point, one per street."""
        here = shapely.Point(self._to_metric(point[1], point[0]))
        hits = self._tree.query(here, predicate="dwithin", distance=radius_m)
        return [self._streets[index] for index in hits]

    def metric_line(self, edge: EdgeKey) -> LineString:
        """The edge's geometry in config.METRIC_CRS metres."""
        return LineString([self._to_metric(lon, lat) for lon, lat in self._coords(edge)])

    def _length(self, edges: list[EdgeKey]) -> float:
        return sum(self.G.edges[edge]["length"] for edge in edges)

    def _coords(self, edge: EdgeKey) -> list[list[float]]:
        u, v, _ = edge
        start = [self.G.nodes[u]["x"], self.G.nodes[u]["y"]]
        end = [self.G.nodes[v]["x"], self.G.nodes[v]["y"]]
        geometry = self.G.edges[edge].get("geometry")
        if geometry is None:
            return [start, end]
        coords = [list(xy) for xy in geometry.coords]
        # Geometry may be stored in the opposite direction of travel.
        if math.dist(coords[0], start) > math.dist(coords[-1], start):
            coords.reverse()
        return coords

    def _describe(self, edges: list[EdgeKey], prefs: Preferences, activity=None) -> dict:
        coordinates: list[list[float]] = []
        segments = []
        cost = 0.0
        # Metres of the route: near a recorded light, with lighting evidence,
        # near a counter, and near a counter weighted by its activity score.
        lit_m = lighting_known_m = activity_known_m = activity_m = 0.0
        crossings = dict.fromkeys(config.CROSSING_PENALTY_M, 0)
        run = None  # most severe type in the current run of crossing edges
        for edge in edges:
            data = self.G.edges[edge]
            length = data["length"]
            coords = self._coords(edge)
            coordinates.extend(coords if not coordinates else coords[1:])
            if activity is None:
                active, active_cover = data["activity"], data["activity_coverage"]
            else:
                active, active_cover = activity.scores.get(edge, (None, 0.0))
            cost += night_cost(data, prefs, quiet_term(active, active_cover))
            lit_m += length * (data["lighting"] or 0.0)
            lighting_known_m += length * data["lighting_coverage"]
            activity_known_m += length * active_cover
            activity_m += length * active_cover * (active or 0.0)
            # Consecutive crossing edges are one crossing of the road.
            if data["crossing_type"]:
                run = max(run or data["crossing_type"], data["crossing_type"],
                          key=config.CROSSING_PENALTY_M.get)
            elif run:
                crossings[run] += 1
                run = None
            segments.append(
                {
                    "u": edge[0],
                    "v": edge[1],
                    "key": edge[2],
                    "length_m": round(length, 1),
                    "lighting": data["lighting"],
                    "lighting_coverage": data["lighting_coverage"],
                    "activity": active,
                    "activity_coverage": active_cover,
                    "crossing": data["crossing_type"],
                }
            )
        if run:
            crossings[run] += 1
        distance = self._length(edges)
        return {
            "geometry": {"type": "LineString", "coordinates": coordinates},
            "distance_m": round(distance, 1),
            "duration_min": round(distance / config.WALK_SPEED_MPS / 60, 1),
            "night_cost": round(cost, 1),
            # score: share of the route near a recorded light.
            "lighting": {
                "score": round(lit_m / distance, 3) if lighting_known_m else None,
                "coverage": round(lighting_known_m / distance, 3),
            },
            # score: mean counter activity over the part of the route near a counter.
            "activity": {
                "score": round(activity_m / activity_known_m, 3) if activity_known_m else None,
                "coverage": round(activity_known_m / distance, 3),
            },
            "crossings": crossings,
            "segments": segments,
        }

    def route(
        self,
        origin: LatLon,
        destination: LatLon,
        prefs: Preferences = Preferences(),
        max_extra_minutes: float | None = config.DEFAULT_MAX_EXTRA_MIN,
        activity=None,
    ) -> dict:
        """Compare the fastest route with the Night route.

        The Night route never exceeds the fastest by more than
        max_extra_minutes of walking (None disables the cap). If it would,
        preferences are relaxed by halves until it fits, else it falls back
        to the fastest route.

        activity is an ActivitySlot for the departure time; without one the
        bundle's own weekday and hour are used.
        """
        source, origin_snap = self.snap(origin)
        target, destination_snap = self.snap(destination)
        if source == target:
            raise SamePoint("Origin and destination snap to the same point.")

        fastest = self._path(source, target, None)  # distance only
        shortest_m = self._length(fastest)
        cap_m = (
            math.inf
            if max_extra_minutes is None
            else shortest_m + config.WALK_SPEED_MPS * 60 * max(0.0, max_extra_minutes)
        )

        night, scale = fastest, 0.0
        if self.scores_matched:
            for attempt in range(5):
                factor = 0.5**attempt
                candidate = self._path(source, target, prefs.scaled(factor), activity)
                if self._length(candidate) <= cap_m:
                    night, scale = candidate, factor
                    break

        if not self.scores_matched:
            status = "baseline_only"  # no score data: not a preference result
        elif night != fastest:
            status = "ok"
        elif scale == 1.0:
            status = "same_route"  # preferences already favour the fastest
        else:
            status = "no_alternative"  # the preferred route broke the detour cap

        full = prefs.scaled()
        extra_m = self._length(night) - shortest_m
        return {
            "status": status,
            "fastest": self._describe(fastest, full, activity),
            "night": self._describe(night, full, activity),
            "detour": {
                "extra_m": round(extra_m, 1),
                "extra_min": round(extra_m / config.WALK_SPEED_MPS / 60, 1),
                "max_extra_min": max_extra_minutes,
                "preference_scale": scale,
            },
            "snap": {
                "origin": self._snap_info(source, origin_snap),
                "destination": self._snap_info(target, destination_snap),
            },
        }

    def _snap_info(self, node: int, distance: float) -> dict:
        return {
            "node": node,
            "lat": self.G.nodes[node]["y"],
            "lon": self.G.nodes[node]["x"],
            "distance_m": round(distance, 1),
        }
