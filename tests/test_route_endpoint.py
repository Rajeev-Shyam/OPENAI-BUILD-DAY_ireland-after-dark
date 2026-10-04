import pytest
from fastapi.testclient import TestClient

from backend.api.main import app

pytestmark = pytest.mark.skipif(
    not __import__("pathlib").Path("data/processed/edge_scores.json").exists(),
    reason="requires the local graph/edge-score bundle built per backend/routing/README.md",
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_route_returns_distinct_profiles_for_a_real_dublin_corridor(client):
    response = client.post(
        "/route",
        json={
            "origin": [-6.2497, 53.3478],
            "destination": [-6.2440, 53.3524],
            "departure_time": "2026-10-04T22:30:00.000Z",
            "timezone": "Europe/Dublin",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "walking"
    assert 1 <= len(body['routes']) <= 3
    assert body['routes'][0]['kind'] == 'fastest'
    assert len({str(r['geometry']) for r in body['routes']}) == len(body['routes'])
    from itertools import combinations
    from backend.routing.diversity import same_corridor
    assert all(not same_corridor(a, b) for a, b in combinations(body['routes'], 2))
    for route in body["routes"]:
        assert route["distance_m"] > 0
        assert route["duration_s"] > 0


def test_route_rejects_out_of_range_coordinates(client):
    response = client.post("/route", json={"origin": [-6.25, 999], "destination": [-6.24, 53.35]})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_INPUT"


def test_route_reports_unsupported_area_outside_ireland(client):
    response = client.post("/route", json={"origin": [-20.0, 53.0], "destination": [-20.01, 53.01]})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNSUPPORTED_AREA"


def test_route_reports_same_point_as_invalid_input(client):
    response = client.post(
        "/route", json={"origin": [-6.2497, 53.3478], "destination": [-6.2497, 53.3478]}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_INPUT"
