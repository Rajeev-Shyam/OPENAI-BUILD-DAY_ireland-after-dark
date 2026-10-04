"""Classify pedestrian crossings from the OSM tags already on the graph.

A crossing is an edge tagged footway=crossing. It is a signal crossing if OSM
says so, otherwise major_unsignalised when it meets a main road and minor when
it does not. OSM tagging is incomplete: an untagged crossing is not classified.
"""

import networkx as nx

SIGNAL_TAGS = {"traffic_signals", "pelican", "pedestrian_signals", "toucan", "puffin"}
MAJOR_ROADS = {"motorway", "trunk", "primary", "secondary", "tertiary"}


def _values(tag) -> set[str]:
    """OSMnx stores a merged tag as a list; treat one value and many alike."""
    if tag is None:
        return set()
    return set(tag) if isinstance(tag, list) else {tag}


def classify_crossings(G: nx.MultiDiGraph) -> dict[tuple[int, int, int], str]:
    """Crossing type per edge: signal, minor or major_unsignalised."""
    on_major_road = set()
    for u, v, highway in G.edges(data="highway"):
        if {value.removesuffix("_link") for value in _values(highway)} & MAJOR_ROADS:
            on_major_road.update((u, v))

    crossings = {}
    for u, v, key, data in G.edges(keys=True, data=True):
        if "crossing" not in _values(data.get("footway")):
            continue
        if _values(data.get("crossing")) & SIGNAL_TAGS:
            crossings[(u, v, key)] = "signal"
        elif u in on_major_road or v in on_major_road:
            crossings[(u, v, key)] = "major_unsignalised"
        else:
            crossings[(u, v, key)] = "minor"
    return crossings
