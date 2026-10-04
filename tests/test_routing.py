"""Routing invariants on a small synthetic graph. No real-world data here."""

import json

import networkx as nx
import pytest
from shapely.geometry import LineString

from data.pipeline.edges import file_sha256

from backend.routing import config
from backend.routing import store as store_module
from backend.routing.engine import (
    NoRoute,
    OutsideCoverage,
    Preferences,
    RoutingEngine,
    SamePoint,
)
from backend.routing.scores import EdgeScore, ScoreBundle, load_edge_scores
from backend.routing.store import GraphStore, GraphUnavailable, TooFar, tile_bbox

# 1 -> 4 has a short way via 2 (400 m) and a long way via 3 (500 m).
# 5 - 6 is a separate island far from the rest.
NODES = {
    1: (53.3500, -6.2600),
    2: (53.3510, -6.2585),
    3: (53.3490, -6.2585),
    4: (53.3500, -6.2570),
    5: (53.4000, -6.2000),
    6: (53.4005, -6.2000),
}
ORIGIN, DESTINATION = NODES[1], NODES[4]
# Whole-edge lighting evidence: the short way has no recorded light near it.
SHORT_DARK_LONG_LIT = {
    (1, 2, 0): EdgeScore(lighting=0.0, lighting_coverage=1.0),
    (2, 4, 0): EdgeScore(lighting=0.0, lighting_coverage=1.0),
    (1, 3, 0): EdgeScore(lighting=1.0, lighting_coverage=1.0),
    (4, 3, 0): EdgeScore(lighting=1.0, lighting_coverage=1.0),  # reverse direction on purpose
}


def make_graph() -> nx.MultiDiGraph:
    G = nx.MultiDiGraph(crs="epsg:4326")
    for node, (lat, lon) in NODES.items():
        G.add_node(node, y=lat, x=lon)
    for u, v, length in [(1, 2, 200), (2, 4, 200), (1, 3, 250), (3, 4, 250), (5, 6, 50)]:
        G.add_edge(u, v, 0, length=float(length))
        G.add_edge(v, u, 0, length=float(length))
    return G


def nodes_of(route: dict) -> list[int]:
    segments = route["segments"]
    return [segments[0]["u"]] + [segment["v"] for segment in segments]


def test_fastest_is_shortest_by_distance():
    result = RoutingEngine(make_graph(), SHORT_DARK_LONG_LIT).route(ORIGIN, DESTINATION)
    fastest = result["fastest"]
    assert nodes_of(fastest) == [1, 2, 4]
    assert fastest["distance_m"] == 400.0
    assert fastest["distance_m"] == sum(s["length_m"] for s in fastest["segments"])
    assert fastest["duration_min"] == round(400 / config.WALK_SPEED_MPS / 60, 1)


def test_night_route_prefers_recorded_lighting_within_cap():
    result = RoutingEngine(make_graph(), SHORT_DARK_LONG_LIT).route(ORIGIN, DESTINATION)
    assert result["status"] == "ok"
    assert nodes_of(result["night"]) == [1, 3, 4]
    assert result["night"]["lighting"] == {"score": 1.0, "coverage": 1.0}
    assert result["fastest"]["lighting"] == {"score": 0.0, "coverage": 1.0}
    assert result["night"]["night_cost"] < result["fastest"]["night_cost"]
    assert result["detour"]["extra_m"] == 100.0


def test_detour_cap_is_enforced_on_physical_length():
    engine = RoutingEngine(make_graph(), SHORT_DARK_LONG_LIT)
    result = engine.route(ORIGIN, DESTINATION, max_extra_minutes=0)
    assert result["status"] == "no_alternative"
    assert nodes_of(result["night"]) == [1, 2, 4]
    assert result["detour"]["extra_m"] == 0.0

    uncapped = engine.route(ORIGIN, DESTINATION, max_extra_minutes=None)
    assert nodes_of(uncapped["night"]) == [1, 3, 4]


def test_without_scores_result_is_baseline_only():
    result = RoutingEngine(make_graph()).route(ORIGIN, DESTINATION)
    assert result["status"] == "baseline_only"
    assert nodes_of(result["night"]) == nodes_of(result["fastest"]) == [1, 2, 4]
    assert result["night"]["lighting"] == {"score": None, "coverage": 0.0}


def test_unknown_is_reported_as_unknown_not_zero():
    # 80% of the first 200 m edge is near a recorded light; nothing else is known.
    scores = {(1, 2, 0): EdgeScore(lighting=0.8, lighting_coverage=0.8)}
    fastest = RoutingEngine(make_graph(), scores).route(ORIGIN, DESTINATION)["fastest"]
    assert [s["lighting"] for s in fastest["segments"]] == [0.8, None]
    assert fastest["lighting"] == {"score": 0.4, "coverage": 0.4}  # 160 m of 400 m
    assert fastest["activity"] == {"score": None, "coverage": 0.0}


def test_partial_evidence_never_costs_more_than_unknown():
    # A few recorded lights on the short way must not push the route onto an
    # unknown way: no evidence is not the same as dark.
    scores = {(1, 2, 0): EdgeScore(lighting=0.1, lighting_coverage=0.1)}
    result = RoutingEngine(make_graph(), scores).route(ORIGIN, DESTINATION)
    assert result["status"] == "same_route"
    assert nodes_of(result["night"]) == [1, 2, 4]


def test_activity_is_averaged_over_the_part_near_a_counter():
    scores = {(1, 2, 0): EdgeScore(activity=0.6, activity_coverage=0.5)}
    fastest = RoutingEngine(make_graph(), scores).route(ORIGIN, DESTINATION)["fastest"]
    assert fastest["activity"] == {"score": 0.6, "coverage": 0.25}  # 100 m of 400 m


def test_same_route_when_preferences_do_not_change_the_path():
    engine = RoutingEngine(make_graph(), SHORT_DARK_LONG_LIT)
    result = engine.route(ORIGIN, DESTINATION, Preferences(less_walking=1.0))
    assert result["status"] == "same_route"
    assert nodes_of(result["night"]) == [1, 2, 4]


def test_crossing_penalty_can_change_the_route():
    scores = {(1, 2, 0): EdgeScore(crossing="major_unsignalised")}
    engine = RoutingEngine(make_graph(), scores)
    prefs = Preferences(well_lit=0, busier=0, crossings=2.0)
    result = engine.route(ORIGIN, DESTINATION, prefs)
    assert nodes_of(result["night"]) == [1, 3, 4]
    assert result["fastest"]["crossings"]["major_unsignalised"] == 1
    assert result["night"]["crossings"]["major_unsignalised"] == 0


def test_geometry_is_lon_lat_and_follows_direction_of_travel():
    G = make_graph()
    bend = (-6.2590, 53.3508)
    # Stored backwards (2 -> 1) on the 1 -> 2 edge.
    G.edges[1, 2, 0]["geometry"] = LineString([NODES[2][::-1], bend, NODES[1][::-1]])
    coordinates = RoutingEngine(G).route(ORIGIN, DESTINATION)["fastest"]["geometry"]["coordinates"]
    assert coordinates == [
        list(NODES[1][::-1]),
        list(bend),
        list(NODES[2][::-1]),
        list(NODES[4][::-1]),
    ]


def test_parallel_edges_use_the_cheaper_one():
    G = make_graph()
    G.add_edge(1, 2, 1, length=120.0)
    fastest = RoutingEngine(G).route(ORIGIN, DESTINATION)["fastest"]
    assert fastest["segments"][0]["key"] == 1
    assert fastest["distance_m"] == 320.0


def test_snap_reports_distance_and_rejects_far_points():
    engine = RoutingEngine(make_graph())
    node, distance = engine.snap((53.35005, -6.2600))  # 5.6 m north of node 1
    assert node == 1
    assert 3.0 < distance < 5.6  # measured to the path, not to the node

    # Midway along a path: about 75 m from either node, but on the path itself.
    node, distance = engine.snap((53.3505, -6.25925))
    assert node in (1, 2)
    assert distance < 1.0

    with pytest.raises(OutsideCoverage):
        engine.snap((53.3600, -6.2600))  # about 1 km from any node
    with pytest.raises(OutsideCoverage):
        engine.snap((float("nan"), -6.26))


def test_same_point_and_disconnected_points_raise():
    engine = RoutingEngine(make_graph())
    with pytest.raises(SamePoint):
        engine.route(ORIGIN, ORIGIN)
    with pytest.raises(NoRoute):
        engine.route(ORIGIN, NODES[5])


def bundle_row(u, v, key, **overrides) -> dict:
    """One edge record with no evidence, in the pipeline's bundle format."""
    row = {
        "u": str(u), "v": str(v), "key": str(key),
        "lighting_score": None, "lighting_data_coverage_fraction": 0.0,
        "footfall_score": None, "footfall_coverage_fraction": 0.0,
    }
    return {**row, **overrides}


def write_bundle(tmp_path, rows, graph_sha=None):
    edges_path = tmp_path / "walking_edges.geojson"
    edges_path.write_text('{"type": "FeatureCollection", "features": []}')
    bundle_path = tmp_path / "edge_scores.json"
    bundle_path.write_text(json.dumps({
        "schema_version": 1,
        "graph": {"sha256": graph_sha or file_sha256(edges_path)},
        "time_slice": {"weekday": 4, "hour": 23, "timezone": "Europe/Dublin"},
        "edges": rows,
    }))
    return bundle_path, edges_path


def test_load_edge_scores_reads_the_pipeline_bundle(tmp_path):
    rows = [
        bundle_row(1, 2, 0, lighting_score=70.0, lighting_data_coverage_fraction=0.7),
        bundle_row(2, 4, 0, footfall_score=45.0, footfall_coverage_fraction=0.5,
                   crossing="signal"),
        bundle_row(1, 3, 0),
    ]
    bundle = load_edge_scores(*write_bundle(tmp_path, rows))
    assert bundle.time_slice["weekday"] == 4 and bundle.time_slice["hour"] == 23
    assert bundle.scores == {
        (1, 2, 0): EdgeScore(lighting=0.7, lighting_coverage=0.7),
        (2, 4, 0): EdgeScore(activity=0.45, activity_coverage=0.5, crossing="signal"),
        (1, 3, 0): EdgeScore(),
    }


def test_load_edge_scores_refuses_a_bundle_for_another_graph(tmp_path):
    assert load_edge_scores(tmp_path / "missing.json", tmp_path / "edges.geojson") == ScoreBundle()

    with pytest.raises(ValueError, match="different graph"):
        load_edge_scores(*write_bundle(tmp_path, [], graph_sha="0" * 64))
    with pytest.raises(ValueError, match="crossing"):
        load_edge_scores(*write_bundle(tmp_path, [bundle_row(1, 2, 0, crossing="bridge")]))


# --- choosing a graph for a request (no network: build_graph is replaced) ---

GALWAY = ((53.2743, -9.0490), (53.2700, -9.0540))


@pytest.fixture
def built(monkeypatch):
    """Records which graphs the store asks for; hands back the synthetic graph."""
    calls = []

    def fake_build_graph(name, bbox):
        calls.append(name)
        G = make_graph()
        G.graph["bbox"] = ",".join(str(c) for c in bbox)
        return G

    monkeypatch.setattr(store_module, "build_graph", fake_build_graph)
    monkeypatch.setattr(store_module, "load_edge_scores", ScoreBundle)
    return calls


def test_store_uses_cached_area_then_fetches_a_tile_once(built):
    store = GraphStore()
    assert store.engine_for(ORIGIN, DESTINATION)[0] == "dublin"
    assert built == ["dublin"]

    name, _ = store.engine_for(*GALWAY)
    assert name == "tile_-9.07_53.26_-9.03_53.29"
    store.engine_for(*GALWAY)
    assert built == ["dublin", name]  # second request reuses the tile


def test_tile_covers_both_points_with_margin():
    left, bottom, right, top = tile_bbox(*GALWAY)
    for lat, lon in GALWAY:
        assert left < lon - 0.01 and lon + 0.01 < right
        assert bottom < lat - 0.008 and lat + 0.008 < top


def test_store_rejects_unsupported_requests(built, monkeypatch):
    store = GraphStore()
    with pytest.raises(OutsideCoverage):
        store.engine_for((51.5074, -0.1278), (51.5100, -0.1300))  # London
    with pytest.raises(TooFar):
        store.engine_for(ORIGIN, GALWAY[0])
    with pytest.raises(OutsideCoverage):
        GraphStore(allow_download=False).engine_for(*GALWAY)

    def failing_build_graph(name, bbox):
        raise RuntimeError("Every Overpass endpoint failed")

    monkeypatch.setattr(store_module, "build_graph", failing_build_graph)
    with pytest.raises(GraphUnavailable):
        store.engine_for(*GALWAY)
