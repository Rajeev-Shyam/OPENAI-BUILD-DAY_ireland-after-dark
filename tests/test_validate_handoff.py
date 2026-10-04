"""Acceptance must bind the actual routed graph to the validated score export."""
import networkx as nx
import pytest

from backend.routing.graph import export_edges
from data.pipeline.build import atomic_json, build_bundle
from data.pipeline import validate_handoff
from test_build import raw_sources


@pytest.fixture
def handoff(raw_sources, tmp_path, monkeypatch):
    graph = nx.MultiDiGraph(crs="EPSG:4326")
    graph.add_node(1, x=-6.25982, y=53.34662)
    graph.add_node(2, x=-6.25882, y=53.34662)
    graph.add_edge(1, 2, length=66.0)
    graph.add_edge(2, 1, length=66.0)
    edges, bundle = tmp_path / "edges.geojson", tmp_path / "scores.json"
    export_edges(graph, edges)
    atomic_json(bundle, build_bundle(edges, raw_sources, weekday=3, hour=0))
    monkeypatch.setattr(validate_handoff, "load_graph", lambda name: graph)
    return graph, edges, bundle


def test_acceptance_runs_actual_routing_with_validated_observations(handoff):
    graph, edges, bundle = handoff
    report = validate_handoff.validate("fixture", edges, bundle,
                                       (53.34662, -6.25982), (53.34662, -6.25882))
    assert report["exported_edges"] == 2
    assert report["result"]["fastest"]["segments"][0]["lighting"] is not None
    assert report["result"]["fastest"]["distance_m"] == 66.0


def test_changed_cached_graph_rejected_even_with_valid_bundle_hash(handoff):
    graph, edges, bundle = handoff
    graph.nodes[2]["x"] += 0.001
    with pytest.raises(ValueError, match="Cached graph"):
        validate_handoff.validate("fixture", edges, bundle,
                                  (53.34662, -6.25982), (53.34662, -6.25882))


def test_route_must_preserve_partial_coverage(handoff, monkeypatch):
    _, edges, bundle = handoff
    original = validate_handoff.RoutingEngine.route

    def corrupt_coverage(self, *args):
        result = original(self, *args)
        result["fastest"]["segments"][0]["lighting_coverage"] = 1.0
        return result

    monkeypatch.setattr(validate_handoff.RoutingEngine, "route", corrupt_coverage)
    with pytest.raises(ValueError, match="observations"):
        validate_handoff.validate("fixture", edges, bundle,
                                  (53.34662, -6.25982), (53.34662, -6.25882))
