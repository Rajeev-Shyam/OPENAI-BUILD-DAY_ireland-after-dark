"""Build the cached walking graph and export its edges for the data pipeline.

    python -m backend.routing --area dublin
"""

import argparse
import time

from . import config
from .graph import build_graph, cache_path, export_edges


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--area", default=config.DEFAULT_AREA, choices=config.AREAS)
    parser.add_argument("--force", action="store_true", help="re-download and re-export")
    args = parser.parse_args()

    start = time.perf_counter()
    G = build_graph(args.area, config.AREAS[args.area], force=args.force)
    print(
        f"{args.area}: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, "
        f"{time.perf_counter() - start:.1f}s -> {cache_path(args.area)}"
    )
    if args.area == config.DEFAULT_AREA and (args.force or not config.EDGES_GEOJSON_PATH.exists()):
        written = export_edges(G)
        print(f"exported {written} edges -> {config.EDGES_GEOJSON_PATH}")


main()
