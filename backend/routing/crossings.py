"""Classify pedestrian crossings from the OSM tags already on the graph.

A crossing is an edge tagged footway=crossing. Only explicit tags decide its
type (see docs/crossing-data.md): signals make it a signal crossing; an
explicitly unsignalised one is major_unsignalised when it meets a main road
and minor when it does not. Missing or contradictory tags leave it unknown,
which is costed as neutral and never assumed to be unsignalised.

Unlike the pipeline's exported evidence, this also reads edges that OSMnx
merged from several ways, so a merged edge that contains a crossing counts.
"""

import networkx as nx

SIGNAL_TAGS = {"traffic_signals", "pelican", "pedestrian_signals", "toucan", "puffin"}
UNSIGNALISED_TAGS = {"unmarked", "uncontrolled", "marked", "zebra", "informal"}
MAJOR_ROADS = {"motorway", "trunk", "primary", "secondary", "tertiary"}


def _values(tag) -> set[str]:
    """OSMnx stores a merged tag as a list; treat one value and many alike."""
    if tag is None:
        return set()
    return set(tag) if isinstance(tag, list) else {tag}


def classify_crossings(G: nx.MultiDiGraph) -> dict[tuple[int, int, int], str]:
    """Crossing type per edge: signal, minor, major_unsignalised or unknown."""
    on_major_road = set()
    for u, v, highway in G.edges(data="highway"):
        if {value.removesuffix("_link") for value in _values(highway)} & MAJOR_ROADS:
            on_major_road.update((u, v))

    crossings = {}
    for u, v, key, data in G.edges(keys=True, data=True):
        if "crossing" not in _values(data.get("footway")):
            continue
        kinds = _values(data.get("crossing"))
        signals = _values(data.get("crossing:signals"))
        signalised = "yes" in signals or bool(kinds & SIGNAL_TAGS)
        unsignalised = "no" in signals or bool(kinds & UNSIGNALISED_TAGS)
        if signalised == unsignalised:  # no evidence, or tags that disagree
            crossings[(u, v, key)] = "unknown"
        elif signalised:
            crossings[(u, v, key)] = "signal"
        elif u in on_major_road or v in on_major_road:
            crossings[(u, v, key)] = "major_unsignalised"
        else:
            crossings[(u, v, key)] = "minor"
    return crossings
