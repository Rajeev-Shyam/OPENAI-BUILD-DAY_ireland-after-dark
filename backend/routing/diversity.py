"""Treat small crossing/sidewalk changes as the same walking option."""
from pyproj import Transformer
from shapely.geometry import LineString
from shapely.ops import transform

PROJECT = Transformer.from_crs(4326, 2157, always_xy=True).transform
CORRIDOR_M = 15
SIMILAR_FRACTION = 0.85


def same_corridor(first, second):
    """Both routes following the other's 15 m corridor for >=85% are duplicates.

    This is a display-diversity heuristic, not a safety or route quality score.
    Metric geometry also catches opposite sidewalks with different graph IDs.
    """
    a = transform(PROJECT, LineString(first['geometry']['coordinates']))
    b = transform(PROJECT, LineString(second['geometry']['coordinates']))
    if not a.length or not b.length:
        return a.equals(b)
    return (a.intersection(b.buffer(CORRIDOR_M)).length / a.length >= SIMILAR_FRACTION
            and b.intersection(a.buffer(CORRIDOR_M)).length / b.length >= SIMILAR_FRACTION)
