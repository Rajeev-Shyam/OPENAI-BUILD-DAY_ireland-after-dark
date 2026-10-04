"""POST /route against docs/api-contract.md, on the synthetic routing graph."""

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.route import RoutePreferences, engine_preferences
from backend.routing import Preferences
from backend.routing import store as store_module
from backend.routing.scores import ScoreBundle
from test_routing import NODES, SHORT_DARK_LONG_LIT, make_graph

client = TestClient(app)  # no lifespan: the store is supplied by the fixtures
FRIDAY_23 = {"weekday": 4, "hour": 23, "timezone": "Europe/Dublin"}
ON_SLICE = "2026-10-09T23:30:00+01:00"  # a Friday, 23:30 in Dublin
OFF_SLICE = "2026-10-04T21:30:00+01:00"  # a Sunday


def use_store(monkeypatch, scores):
    def fake_build_graph(name, bbox):
        G = make_graph()
        G.graph["bbox"] = ",".join(str(c) for c in bbox)
        return G

    monkeypatch.setattr(store_module, "build_graph", fake_build_graph)
    monkeypatch.setattr(store_module, "load_edge_scores", lambda: ScoreBundle(scores, FRIDAY_23))
    monkeypatch.setattr(store_module, "_store", store_module.GraphStore())


@pytest.fixture
def scored(monkeypatch):
    use_store(monkeypatch, SHORT_DARK_LONG_LIT)


def body(origin=1, destination=4, **extra):
    points = {
        name: {"lat": NODES[node][0], "lng": NODES[node][1]}
        for name, node in (("origin", origin), ("destination", destination))
    }
    return {**points, **extra}


def test_success_matches_the_contract(scored):
    response = client.post("/route", json=body(departure_time=ON_SLICE))
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"routes", "score_breakdown", "data_confidence", "explanation", "warnings"}

    fastest, night = data["routes"]["fastest"], data["routes"]["night"]
    assert set(fastest) == {"geometry", "distance_metres", "duration_minutes", "route_score"}
    assert fastest["geometry"]["type"] == "LineString"
    assert fastest["geometry"]["coordinates"][0] == [NODES[1][1], NODES[1][0]]  # [lng, lat]
    assert (fastest["distance_metres"], night["distance_metres"]) == (400.0, 500.0)
    assert fastest["route_score"] is None and night["route_score"] is None

    assert data["score_breakdown"] == {
        "lighting": 100, "activity": None, "crossings": None, "waiting": None,
    }
    assert data["data_confidence"]["level"] == "medium"
    assert data["data_confidence"]["reasons"][0] == "Lighting data covers 100% of the Night Route's length."
    assert data["explanation"] == [
        "Night Route is 100 m longer than the fastest route (6.4 min against 5.1 min).",
        "Night Route has lighting coverage on 100% of its length; the fastest route has 0%.",
    ]
    assert data["warnings"] == []


def test_footfall_is_only_used_for_its_own_weekday_and_hour(scored):
    data = client.post("/route", json=body(departure_time=OFF_SLICE)).json()
    assert data["warnings"] == [
        "Recorded footfall is only available for Friday 23:00, "
        "so activity was not used for this departure time."
    ]
    assert engine_preferences(RoutePreferences(), use_activity=False).busier == 0.0


def test_default_weights_give_the_engine_defaults():
    assert engine_preferences(RoutePreferences(), use_activity=True) == Preferences()
    off = engine_preferences(RoutePreferences(less_walking=1.0), use_activity=True)
    assert (off.well_lit, off.busier, off.crossings) == (0.0, 0.0, 0.0)


def test_preferences_change_the_outcome(scored):
    capped = client.post("/route", json=body(
        departure_time=ON_SLICE, preferences={"max_detour_minutes": 0})).json()
    assert capped["routes"]["night"]["distance_metres"] == 400.0
    assert capped["explanation"] == [
        "No alternative fits within the 0 minute detour limit, "
        "so the fastest route is shown for both options."
    ]

    direct = client.post("/route", json=body(
        departure_time=ON_SLICE, preferences={"less_walking": 1.0, "avoid_nightlife": True})).json()
    assert direct["routes"]["night"]["distance_metres"] == 400.0
    assert direct["explanation"][0].startswith("Both options follow the same route")
    assert direct["warnings"] == ["avoid_nightlife is not supported yet and was ignored."]


def test_without_scores_confidence_is_low_and_says_why(monkeypatch):
    use_store(monkeypatch, {})
    data = client.post("/route", json=body(departure_time=ON_SLICE)).json()
    assert data["data_confidence"] == {
        "level": "low",
        "reasons": [
            "No lighting data covers this route.",
            "Recorded footfall is unknown for this route at this time.",
        ],
    }
    assert data["score_breakdown"]["lighting"] is None
    assert data["explanation"][0].startswith("Only the fastest route is available here")
    assert "This route is outside the area with lighting data." in data["warnings"]


@pytest.mark.parametrize("payload, field", [
    ({"origin": {"lat": 123, "lng": -6.26}, "destination": {"lat": 53.35, "lng": -6.25}}, "origin.lat"),
    ({"origin": {"lat": 53.35, "lng": -6.26}}, "destination"),
    (body(departure_time="2026-10-04T21:30:00"), "departure_time"),  # no timezone offset
    (body(preferences={"well_lit": 2}), "preferences.well_lit"),
])
def test_invalid_input_uses_the_contract_error_shape(scored, payload, field):
    response = client.post("/route", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["routes"] is None
    assert data["error"]["code"] == "INVALID_INPUT"
    assert data["error"]["message"].startswith(field)


def test_routing_errors_map_to_contract_codes(scored):
    london = {"origin": {"lat": 51.5074, "lng": -0.1278}, "destination": {"lat": 51.51, "lng": -0.13}}
    for payload, status, code in [
        (london, 422, "OUT_OF_AREA"),
        (body(origin=1, destination=1), 400, "INVALID_INPUT"),
        (body(origin=1, destination=5), 404, "NO_ROUTE"),  # node 5 is on an island
    ]:
        response = client.post("/route", json=payload)
        assert (response.status_code, response.json()["error"]["code"]) == (status, code)
        assert response.json()["routes"] is None
