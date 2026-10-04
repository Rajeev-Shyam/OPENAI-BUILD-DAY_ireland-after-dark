"""Download the OSM walking network and cache it to disk.

Build the Dublin cache once:

    python -m backend.routing --area dublin

The cache is GraphML (plain data, safe to load). Edge identity everywhere is
OSMnx's (u, v, key), where u and v are OSM node ids.
"""

import json
import time
from pathlib import Path

import networkx as nx
import osmnx as ox

from data.pipeline.crossings import EVIDENCE_VERSION, export_crossing_evidence

from . import config

# Kept on edges so crossings and tagged lighting can be inspected later.
EXTRA_WAY_TAGS = ["footway", "crossing", "crossing:signals", "lit", "foot"]


def cache_path(name: str) -> Path:
    return config.PROCESSED_DIR / f"graph_{name}.graphml"


def download_graph(bbox: tuple[float, float, float, float]) -> nx.MultiDiGraph:
    """Fetch the walking network inside bbox (left, bottom, right, top)."""
    ox.settings.use_cache = True
    ox.settings.cache_folder = str(config.RAW_DIR / "osm_cache")
    ox.settings.requests_timeout = config.OVERPASS_TIMEOUT_S
    ox.settings.useful_tags_way = sorted(
        set(ox.settings.useful_tags_way) | set(EXTRA_WAY_TAGS)
    )
    failures = []
    for url in config.OVERPASS_URLS:
        ox.settings.overpass_url = url
        try:
            # Largest connected component only, so a snap never lands on an island.
            G = ox.graph_from_bbox(
                bbox=bbox, network_type="walk", simplify=True, retain_all=False
            )
            # Preserve OSMnx buffer -> simplify -> truncate ordering.
            G.graph["dad_crossing_evidence_version"] = EVIDENCE_VERSION
            return G
        except Exception as error:  # server down, overloaded or timed out
            failures.append(f"{url}: {error}")
    raise RuntimeError("Every Overpass endpoint failed:\n" + "\n".join(failures))


def build_graph(
    name: str, bbox: tuple[float, float, float, float], force: bool = False
) -> nx.MultiDiGraph:
    """Return the cached graph for name, downloading and caching it if needed."""
    path = cache_path(name)
    if path.exists() and not force:
        return load_graph(name)
    G = download_graph(bbox)
    G.graph["bbox"] = ",".join(str(c) for c in bbox)
    G.graph["fetched"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    path.parent.mkdir(parents=True, exist_ok=True)
    ox.save_graphml(G, path)
    return G


def load_graph(name: str = config.DEFAULT_AREA) -> nx.MultiDiGraph:
    path = cache_path(name)
    if not path.exists():
        raise FileNotFoundError(
            f"No cached graph at {path}. "
            f"Run: python -m backend.routing --area {name}"
        )
    return ox.load_graphml(path)


def graph_bbox(G: nx.MultiDiGraph) -> tuple[float, float, float, float] | None:
    raw = G.graph.get("bbox")
    if not raw:
        return None
    left, bottom, right, top = (float(c) for c in raw.split(","))
    return left, bottom, right, top


def export_edges(G: nx.MultiDiGraph, path: Path = config.EDGES_GEOJSON_PATH) -> int:
    """Write the edge GeoJSON the data pipeline scores. Returns edges written.

    The pipeline fingerprints this file's exact bytes, so scores must be
    rebuilt whenever it is rewritten from a different graph.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with path.open("w", encoding="utf-8") as handle:
        handle.write('{"type": "FeatureCollection", "features": [\n')
        for u, v, key, data in G.edges(keys=True, data=True):
            geometry = data.get("geometry")
            coordinates = (
                [list(xy) for xy in geometry.coords]
                if geometry is not None
                else [[G.nodes[n]["x"], G.nodes[n]["y"]] for n in (u, v)]
            )
            if len(set(map(tuple, coordinates))) < 2:
                continue  # zero-length edge: the pipeline rejects these
            feature = {
                "type": "Feature",
                "properties": {"u": str(u), "v": str(v), "key": str(key),
                               "osm_crossing_evidence": export_crossing_evidence(
                                   data, way_tags_complete=G.graph.get(
                                       "dad_crossing_evidence_version") == EVIDENCE_VERSION)},
                "geometry": {"type": "LineString", "coordinates": coordinates},
            }
            handle.write(("," if written else "") + json.dumps(feature) + "\n")
            written += 1
        handle.write("]}\n")
    return written
