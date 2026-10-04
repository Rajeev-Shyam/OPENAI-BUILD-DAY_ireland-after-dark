"""Check a position against a chosen route. Stateless: nothing is stored."""

import shapely
from pyproj import Transformer
from shapely.geometry import LineString

from . import config

_TO_METRIC = Transformer.from_crs("EPSG:4326", config.METRIC_CRS, always_xy=True).transform
_TO_WGS84 = Transformer.from_crs(config.METRIC_CRS, "EPSG:4326", always_xy=True).transform


def check_deviation(
    geometry: dict,
    position: tuple[float, float],
    tolerance_m: float = config.DEVIATION_TOLERANCE_M,
) -> dict:
    """How far a (lat, lon) position is from a route, and how far along it.

    geometry is the route's GeoJSON LineString as returned by the engine.
    off_route is true when the position is further than tolerance_m from it.
    """
    route = LineString([_TO_METRIC(lon, lat) for lon, lat in geometry["coordinates"]])
    lat, lon = position
    here = shapely.Point(_TO_METRIC(lon, lat))
    distance = route.distance(here)
    progress = route.project(here)
    nearest_lon, nearest_lat = _TO_WGS84(*route.interpolate(progress).coords[0])
    return {
        "off_route": distance > tolerance_m,
        "distance_m": round(distance, 1),
        "progress_m": round(progress, 1),
        "remaining_m": round(route.length - progress, 1),
        "nearest": {"lat": nearest_lat, "lon": nearest_lon},
    }
