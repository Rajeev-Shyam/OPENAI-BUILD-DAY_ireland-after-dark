"""Routing defaults. Preference weights are strengths, not risk coefficients."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
# Handoff with the data pipeline (docs/edge-data-contract.md).
EDGES_GEOJSON_PATH = RAW_DIR / "walking_edges.geojson"
EDGE_SCORES_PATH = PROCESSED_DIR / "edge_scores.json"

# (left, bottom, right, top) in WGS84 degrees: the order OSMnx 2.x expects.
AREAS = {
    "dublin-centre": (-6.300, 53.330, -6.220, 53.365),
    "dublin": (-6.390, 53.290, -6.110, 53.410),
}
DEFAULT_AREA = "dublin"
IRELAND_BBOX = (-10.75, 51.35, -5.30, 55.45)

# Tried in order; public Overpass servers are often overloaded. Set
# OVERPASS_URL to put another endpoint first.
OVERPASS_URLS = [
    url
    for url in (
        os.environ.get("OVERPASS_URL"),
        "https://lz4.overpass-api.de/api",
        "https://overpass-api.de/api",
        "https://overpass.openstreetmap.fr/api",
    )
    if url
]
OVERPASS_TIMEOUT_S = 90

METRIC_CRS = "EPSG:2157"  # Irish Transverse Mercator: metres across the island
WALK_SPEED_MPS = 1.3  # estimate only; not individual ability or terrain
MAX_SNAP_M = 100.0  # reject rather than hide large endpoint displacements
DEFAULT_MAX_EXTRA_MIN = 5.0

# On-demand tiles for requests outside the cached areas.
TILE_MARGIN_M = 1000.0
MAX_ON_DEMAND_KM = 15.0  # straight-line origin to destination

# Score used for costing when an edge has no data for a source. The edge is
# still reported as unknown; this only stops missing data counting as zero.
NEUTRAL_SCORE = 0.5

# Extra metres added per crossing edge, before the crossings weight.
CROSSING_PENALTY_M = {
    "signal": 10.0,
    "minor": 20.0,
    "major_unsignalised": 80.0,
}
