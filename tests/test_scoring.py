from backend.scoring.contract import build_route_response
from backend.scoring.explanation import build_explanations, build_limitations
from backend.scoring.route_score import compute_confidence, compute_score


def test_compute_score_averages_available_factors():
    assert compute_score(0.6, 0.4) == 50.0


def test_compute_score_ignores_missing_factor_instead_of_treating_as_zero():
    assert compute_score(0.6, None) == 60.0


def test_compute_score_is_none_when_no_evidence_at_all():
    assert compute_score(None, None) is None


def test_compute_confidence_is_low_without_any_matched_scores():
    assert compute_confidence(0.9, 0.9, has_scores=False) == "Low"


def test_compute_confidence_thresholds_on_weaker_coverage():
    assert compute_confidence(0.9, 0.05, has_scores=True) == "Low"
    assert compute_confidence(0.9, 0.3, has_scores=True) == "Medium"
    assert compute_confidence(0.9, 0.8, has_scores=True) == "High"


def test_build_limitations_flags_missing_evidence_without_calling_it_zero():
    route = {"lighting": {"score": None, "coverage": 0.0}, "activity": {"score": 0.4, "coverage": 0.2}}
    limitations = build_limitations(route, has_scores=True, time_slice=None)
    assert any("No lighting evidence is recorded" in item for item in limitations)
    assert not any("zero" in item.lower() for item in limitations)


def test_build_limitations_short_circuits_for_baseline_only():
    limitations = build_limitations({}, has_scores=False, time_slice=None)
    assert len(limitations) == 1
    assert "No lighting or footfall evidence" in limitations[0]


FASTEST = {"lighting": {"score": 0.5, "coverage": 0.9}, "activity": {"score": 0.3, "coverage": 0.2}}
NIGHT = {"lighting": {"score": 0.8, "coverage": 0.95}, "activity": {"score": 0.3, "coverage": 0.2}}
DETOUR = {"extra_m": 50.0, "extra_min": 2.0, "max_extra_min": 5.0, "preference_scale": 1.0}


def test_build_explanations_fastest_is_always_the_same_neutral_line():
    assert build_explanations("fastest", "ok", FASTEST, NIGHT, DETOUR) == [
        "Shortest walking distance between these points."
    ]


def test_build_explanations_night_cites_real_lighting_difference():
    [explanation] = build_explanations("night", "ok", FASTEST, NIGHT, DETOUR)
    assert "2 min longer" in explanation
    assert "30% more recorded lighting coverage" in explanation


def test_build_explanations_same_route_is_honest_not_a_fabricated_benefit():
    assert build_explanations("night", "same_route", FASTEST, FASTEST, DETOUR) == [
        "This is already the best path for your preferences — same as the fastest route."
    ]


def test_build_explanations_baseline_only_never_claims_a_night_advantage():
    assert build_explanations("night", "baseline_only", FASTEST, FASTEST, DETOUR) == [
        "No lighting or footfall evidence is available here, so this is the same as the fastest route."
    ]


FASTEST_ROUTE = {
    "geometry": {"type": "LineString", "coordinates": [[-6.26, 53.34], [-6.25, 53.35]]},
    "distance_m": 800.0,
    "duration_min": 10.0,
    "lighting": {"score": 0.5, "coverage": 0.9},
    "activity": {"score": None, "coverage": 0.0},
}
NIGHT_ROUTE = {
    "geometry": {"type": "LineString", "coordinates": [[-6.26, 53.34], [-6.24, 53.35]]},
    "distance_m": 850.0,
    "duration_min": 10.5,
    "lighting": {"score": 0.8, "coverage": 0.95},
    "activity": {"score": None, "coverage": 0.0},
}
TIME_SLICE = {"weekday": 4, "hour": 23, "timezone": "Europe/Dublin"}


def _alternatives(status="ok"):
    return [{"kind": "best_lit", "route": NIGHT_ROUTE, "status": status, "detour": DETOUR}]


def test_build_route_response_matches_the_agreed_contract_shape():
    response = build_route_response(
        "dublin", (-6.39, 53.29, -6.11, 53.41), FASTEST_ROUTE, TIME_SLICE, _alternatives()
    )

    assert response["mode"] == "walking"
    assert response["coverage"]["bounds"] == [-6.39, 53.29, -6.11, 53.41]
    assert [route["kind"] for route in response["routes"]] == ["fastest", "best_lit"]
    for route in response["routes"]:
        expected_min = 10.0 if route["kind"] == "fastest" else 10.5
        assert route["duration_s"] == round(expected_min * 60)
        assert route["confidence"] in ("Low", "Medium", "High")
        assert route["historical_activity"] is None  # no activity evidence in this fixture


def test_build_route_response_forces_low_confidence_outside_data_coverage():
    response = build_route_response(
        "tile_x", None, FASTEST_ROUTE, TIME_SLICE, _alternatives(status="baseline_only")
    )

    assert response["coverage"]["bounds"] is None
    for route in response["routes"]:
        assert route["confidence"] == "Low"
        assert route["score"] is None
        assert route["sources"] == []


def test_build_route_response_supports_three_named_alternatives():
    alternatives = [
        {"kind": "best_lit", "route": NIGHT_ROUTE, "status": "ok", "detour": DETOUR},
        {"kind": "quick_detour", "route": NIGHT_ROUTE, "status": "ok", "detour": DETOUR},
    ]
    response = build_route_response(
        "dublin", (-6.39, 53.29, -6.11, 53.41), FASTEST_ROUTE, TIME_SLICE, alternatives
    )

    assert [route["kind"] for route in response["routes"]] == ["fastest", "best_lit", "quick_detour"]
