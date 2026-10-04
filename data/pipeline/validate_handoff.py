"""Reproduce a real graph → edge scores → routing acceptance check offline."""
from __future__ import annotations

import argparse
import json
import tempfile
import time
from datetime import datetime
from pathlib import Path

from backend.routing import config
from backend.routing.engine import RoutingEngine
from backend.routing.graph import export_edges, load_graph
from backend.routing.scores import load_edge_scores
from data.pipeline.build import atomic_json
from data.pipeline.edges import file_sha256


def validate(graph_name, edges_path, bundle_path, origin, destination, departure_time=None):
    start = time.perf_counter()
    graph = load_graph(graph_name)
    # The bundle/export fingerprint alone does not prove that the GraphML being
    # routed is the graph that was exported. Re-export that actual cached graph.
    with tempfile.TemporaryDirectory() as directory:
        exported = Path(directory) / "edges.geojson"
        count = export_edges(graph, exported)
        if file_sha256(exported) != file_sha256(edges_path):
            raise ValueError("Cached graph does not reproduce the scored edge export; export and rebuild")
    bundle = load_edge_scores(Path(bundle_path), Path(edges_path), departure_time=departure_time)
    if not bundle.scores or len(bundle.scores) != count:
        raise ValueError("A complete, nonempty score bundle is required for acceptance")
    engine = RoutingEngine(graph, bundle.scores)
    if not set(bundle.scores).issubset(set(graph.edges(keys=True))):
        raise ValueError("Scored identities do not exist in the routing graph")
    prepared = time.perf_counter()
    result = engine.route(tuple(origin), tuple(destination))
    routed = time.perf_counter()
    for name in ("fastest", "night"):
        route = result[name]
        if not route["segments"] or route["distance_m"] <= 0:
            raise ValueError("Routing returned an empty journey")
        for segment in route["segments"]:
            identity = tuple(segment[key] for key in ("u", "v", "key"))
            if identity not in bundle.scores:
                raise ValueError("Route traverses an edge missing from the verified bundle")
            score = bundle.scores[identity]
            if (segment["lighting"] != score.lighting or segment["activity"] != score.activity
                    or segment["lighting_coverage"] != score.lighting_coverage
                    or segment["activity_coverage"] != score.activity_coverage):
                raise ValueError("Routing did not preserve the validated edge observations")
    return {
        "graph_name": graph_name, "graph_nodes": graph.number_of_nodes(),
        "graph_edges": graph.number_of_edges(), "exported_edges": count,
        "edge_export_sha256": file_sha256(edges_path),
        "bundle_sha256": file_sha256(bundle_path), "time_slice": bundle.time_slice,
        "prepare_seconds": round(prepared - start, 3),
        "route_seconds": round(routed - prepared, 3),
        "origin": list(origin), "destination": list(destination), "result": result,
        "limitations": ["Offline data/routing acceptance, not POST /route or frontend acceptance.",
                        "No on-the-ground validation of lighting, access or pedestrian activity."],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", default="dublin")
    parser.add_argument("--edges", type=Path, default=config.EDGES_GEOJSON_PATH)
    parser.add_argument("--bundle", type=Path, default=config.EDGE_SCORES_PATH)
    parser.add_argument("--departure-time", type=datetime.fromisoformat,
                        help="Optional offset-aware ISO instant; recompute activity offline")
    parser.add_argument("--origin", type=float, nargs=2, default=(53.3339, -6.2632), metavar=("LAT", "LON"))
    parser.add_argument("--destination", type=float, nargs=2, default=(53.3440, -6.2577), metavar=("LAT", "LON"))
    parser.add_argument("--output", type=Path, default=config.PROCESSED_DIR / "handoff-validation.json")
    args = parser.parse_args()
    protected = {args.edges.resolve(), args.bundle.resolve(),
                 (config.PROCESSED_DIR / f"graph_{args.graph}.graphml").resolve()}
    if args.output.resolve() in protected:
        parser.error("Output must not overwrite acceptance inputs")
    report = validate(args.graph, args.edges, args.bundle, args.origin, args.destination,
                      args.departure_time)
    atomic_json(args.output, report)
    print(json.dumps({key: value for key, value in report.items() if key != "result"}))
    print(json.dumps({"status": report["result"]["status"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
