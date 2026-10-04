"""Protect conservative crossing evidence against simplification false positives."""
import json

import networkx as nx
import osmnx as ox
import pytest

from backend.routing.graph import download_graph, export_edges
from data.pipeline.crossings import (
    EVIDENCE_VERSION, classify_way, export_crossing_evidence,
)

SIGNAL = {"highway": "footway", "footway": "crossing", "crossing:signals": "yes"}


@pytest.mark.parametrize("tags,expected", [
    (SIGNAL, "signal"),
    ({"highway": "footway", "footway": "crossing", "crossing": "traffic_signals"}, "signal"),
    ({**SIGNAL, "crossing": "uncontrolled"}, None),
    ({**SIGNAL, "crossing:signals": "no", "crossing": "traffic_signals"}, None),
    ({**SIGNAL, "highway": "residential"}, None),
    ({"highway": "traffic_signals"}, None),
    ({"highway": "footway", "footway": "crossing"}, None),
    ({**SIGNAL, "crossing:signals": ["yes", "no"]}, None),
    ({}, None),
])
def test_only_explicit_consistent_pedestrian_way(tags, expected):
    assert classify_way(tags) == expected


def make_graph(second_tags):
    graph = nx.MultiDiGraph(crs="EPSG:4326", dad_crossing_evidence_version=EVIDENCE_VERSION)
    for node, lon in ((1, -6.26), (2, -6.2599), (3, -6.2598)):
        graph.add_node(node, x=lon, y=53.34)
    for u, v, tags in ((1, 2, SIGNAL), (2, 3, second_tags)):
        for start, end in ((u, v), (v, u)):
            data = dict(tags, length=10.0, osmid=100 + u)
            graph.add_edge(start, end, **data)
    return graph



@pytest.mark.parametrize("second_tags", [SIGNAL, {"highway": "footway"}])
def test_simplified_aggregate_is_unknown_after_graphml_roundtrip(tmp_path, second_tags):
    simplified = ox.simplification.simplify_graph(make_graph(second_tags))
    path = tmp_path / "graph.graphml"
    ox.save_graphml(simplified, path)
    restored = ox.load_graphml(path)
    output = tmp_path / "edges.geojson"
    assert export_edges(restored, output) == 2
    for feature in json.loads(output.read_text())["features"]:
        evidence = feature["properties"]["osm_crossing_evidence"]
        assert evidence["classification"] is None
        assert evidence["evidence_available"] is False
        assert "crossing" not in feature["properties"]


def test_original_way_tags_survive_graphml_export(tmp_path):
    graph = make_graph(SIGNAL)
    path = tmp_path / "graph.graphml"
    ox.save_graphml(graph, path)
    restored = ox.load_graphml(path)
    output = tmp_path / "edges.geojson"
    assert export_edges(restored, output) == 4
    for feature in json.loads(output.read_text())["features"]:
        evidence = feature["properties"]["osm_crossing_evidence"]
        assert evidence["classification"] == "signal"
        assert evidence["scope"] == "original_way"


def test_old_cache_and_aggregate_way_ids_are_unknown():
    assert export_crossing_evidence(dict(SIGNAL, osmid=123))["classification"] is None
    assert export_crossing_evidence(dict(SIGNAL, osmid=[123, 456]), way_tags_complete=True)["classification"] is None


def test_download_retains_upstream_buffer_simplify_truncate_order(monkeypatch):
    graph = make_graph(SIGNAL)
    graph.graph.pop("dad_crossing_evidence_version")
    calls = []
    def upstream(**kwargs):
        calls.append(kwargs)
        return graph
    monkeypatch.setattr(ox, "graph_from_bbox", upstream)
    # Any second simplification after bbox truncation is a topology regression.
    def invalid_simplification(*args, **kwargs):
        pytest.fail("must let graph_from_bbox simplify before bbox truncation")
    monkeypatch.setattr(ox.simplification, "simplify_graph", invalid_simplification)
    bbox = (-6.3, 53.3, -6.2, 53.4)
    downloaded = download_graph(bbox)
    assert calls == [{"bbox": bbox, "network_type": "walk", "simplify": True, "retain_all": False}]
    assert downloaded is graph
    assert set(downloaded.edges(keys=True)) == {(1, 2, 0), (2, 1, 0), (2, 3, 0), (3, 2, 0)}
    assert downloaded.graph["dad_crossing_evidence_version"] == EVIDENCE_VERSION
