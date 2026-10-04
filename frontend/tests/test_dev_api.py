import copy
import importlib.util
import json
import threading
import urllib.error
import urllib.request
from types import SimpleNamespace
from http.server import HTTPServer
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("dev_api", Path(__file__).parents[1] / "dev_api.py")
bridge_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge_module)


def request_document():
    return {"origin": [-6.2479, 53.3489], "destination": [-6.2470, 53.3531],
            "departure_time": "2026-10-04T19:00:00Z", "timezone": "Europe/Dublin"}


def engine_result():
    route = {"geometry": {"type": "LineString", "coordinates": [[-6.2479, 53.3489], [-6.2470, 53.3531]]},
             "distance_m": 600, "duration_min": 7.7, "lighting": {"score": 0.6, "coverage": 0.6},
             "activity": {"score": 0.42, "coverage": 0.1}}
    return {"status": "same_route", "fastest": route, "night": copy.deepcopy(route)}


def test_coordinates_and_dublin_time_conversion():
    origin, destination, departure = bridge_module.parse_request(request_document())
    assert origin == (53.3489, -6.2479)
    assert destination == (53.3531, -6.2470)
    assert departure.hour == 20
    assert departure.weekday() == 6


@pytest.mark.parametrize("change", [{"origin": [True, 53]}, {"origin": [float("nan"), 53]},
                                    {"destination": [181, 53]}, {"timezone": "UTC"},
                                    {"departure_time": "2026-10-04T19:00:00"}, {"preferences": {}}])
def test_invalid_request_rejected(change):
    with pytest.raises(bridge_module.InputError):
        bridge_module.parse_request(request_document() | change)


def test_units_null_scores_and_time_mismatch():
    response = bridge_module.normalize_result(engine_result(), [-6.39, 53.29, -6.11, 53.41],
                                              {"weekday": 4, "hour": 23}, [], False)
    route = response["routes"][0]
    assert route["duration_s"] == 462
    assert route["lighting_coverage_pct"] == 60
    assert route["historical_activity"] is None
    assert route["score"] is None
    assert route["confidence"] is None
    assert route["waiting"] is None
    assert any("excluded" in warning for warning in route["limitations"])


def test_no_evidence_is_low_baseline_without_fabricated_zeroes():
    result = engine_result()
    for kind in ("fastest", "night"):
        result[kind]["lighting"] = {"score": None, "coverage": 0}
        result[kind]["activity"] = {"score": None, "coverage": 0}
    response = bridge_module.normalize_result(result, None, None, [], False)
    assert response["comparison_status"] == "baseline_only"
    for route in response["routes"]:
        assert route["confidence"] == "Low"
        assert route["lighting_coverage_pct"] is None
        assert route["historical_activity"] is None
        assert route["distance_m"] == 600


def test_real_zero_activity_is_not_unknown():
    result = engine_result()
    result["fastest"]["activity"]["score"] = 0
    response = bridge_module.normalize_result(result, None, {"weekday": 6, "hour": 20}, [], True)
    assert response["routes"][0]["historical_activity"]["value"] == 0
    assert "index" in response["routes"][0]["historical_activity"]["unit"]


@pytest.mark.parametrize("hour,expected_weight", [(20, 0.5), (18, 0.0)])
def test_engine_activity_weight_matches_requested_time(hour, expected_weight):
    captured = []

    def run_route(origin, destination, preferences):
        captured.append(preferences.busier)
        return engine_result()

    engine = SimpleNamespace(route=run_route, G=SimpleNamespace(graph={}))
    bridge = bridge_module.RoutingBridge.__new__(bridge_module.RoutingBridge)
    bridge.store = SimpleNamespace(bundle=SimpleNamespace(time_slice={"weekday": 6, "hour": hour}),
                                   engine_for=lambda origin, destination: ("test", engine))
    bridge.metadata = {}
    bridge.bounds = [-6.39, 53.29, -6.11, 53.41]
    response = bridge.route(request_document())
    assert captured == [expected_weight]
    assert (response["routes"][0]["historical_activity"] is not None) == bool(expected_weight)


def test_http_errors_cors_and_real_json_transport():
    from backend.routing.engine import NoRoute, OutsideCoverage

    class FakeBridge:
        area = "test-only"
        bounds = [-6.39, 53.29, -6.11, 53.41]

        def route(self, document):
            bridge_module.parse_request(document)
            if document["origin"][0] == 0:
                raise OutsideCoverage("test")
            if document["destination"][0] == 0:
                raise NoRoute("test")
            return bridge_module.normalize_result(engine_result(), self.bounds, None, [], False)

    server = HTTPServer(("127.0.0.1", 0), bridge_module.handler_for(FakeBridge()))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    url = f"http://127.0.0.1:{server.server_port}/route"
    headers = {"Content-Type": "application/json", "Origin": "http://127.0.0.1:5173"}
    try:
        request = urllib.request.Request(url, method="OPTIONS", headers={**headers, "Access-Control-Request-Method": "POST"})
        with urllib.request.urlopen(request) as response:
            assert response.status == 204
            assert response.headers["Access-Control-Allow-Origin"] == headers["Origin"]
        request = urllib.request.Request(url, data=json.dumps(request_document()).encode(), headers=headers)
        with urllib.request.urlopen(request) as response:
            assert len(json.load(response)["routes"]) == 2
        for change, status, code in [({"origin": [0, 53]}, 422, "UNSUPPORTED_AREA"),
                                     ({"destination": [0, 53]}, 404, "NO_ROUTE"),
                                     ({"origin": [200, 53]}, 400, "INVALID_INPUT")]:
            request = urllib.request.Request(url, data=json.dumps(request_document() | change).encode(), headers=headers)
            with pytest.raises(urllib.error.HTTPError) as failure:
                urllib.request.urlopen(request)
            assert failure.value.code == status
            assert json.load(failure.value)["error"]["code"] == code
        request = urllib.request.Request(url, data=json.dumps(request_document()).encode(), headers={**headers, "Origin": "https://unapproved.example"})
        with pytest.raises(urllib.error.HTTPError) as failure:
            urllib.request.urlopen(request)
        assert failure.value.code == 403
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
