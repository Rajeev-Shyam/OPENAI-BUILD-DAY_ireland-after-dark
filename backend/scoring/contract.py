"""Maps the routing engine's result shape onto the frontend's contract.

Keeps Person 1's engine unchanged; all the translation lives here.
"""

from . import route_score
from .explanation import build_explanations, build_limitations

# Dated to the actual resource content, not the download date.
# Dublin City Council via Smart Dublin, CC BY 4.0.
SOURCES = [
    {
        "name": "DCC Public Lighting",
        "date": "2021-12",
        "attribution": "Dublin City Council via Smart Dublin, CC BY 4.0",
    },
    {
        "name": "DCC Pedestrian Footfall Counters",
        "date": "2026-06-02",
        "attribution": "Dublin City Council and NTA via Smart Dublin, CC BY 4.0",
    },
]


def _route_payload(kind: str, route: dict, status: str, detour: dict | None, time_slice: dict | None, fastest: dict) -> dict:
    has_scores = status != "baseline_only"
    lighting = route["lighting"]
    activity = route["activity"]

    score = route_score.compute_score(lighting["score"], activity["score"]) if has_scores else None
    confidence = route_score.compute_confidence(lighting["coverage"], activity["coverage"], has_scores)

    breakdown = []
    if has_scores:
        breakdown = [
            {
                "label": "Recorded lighting",
                "value": None if lighting["score"] is None else round(lighting["score"] * 100, 1),
                "max": 100,
            },
            {
                "label": "Historical activity",
                "value": None if activity["score"] is None else round(activity["score"] * 100, 1),
                "max": 100,
            },
        ]

    historical_activity = None
    if activity["score"] is not None:
        historical_activity = {
            "value": round(activity["score"] * 100, 1),
            "unit": "log-scaled historical footfall proxy (0-100; not a live or raw pedestrian count)",
        }

    return {
        "kind": kind,
        "geometry": route["geometry"],
        "distance_m": route["distance_m"],
        "duration_s": round(route["duration_min"] * 60),
        "lighting_coverage_pct": None if lighting["score"] is None else round(lighting["score"] * 100, 1),
        "historical_activity": historical_activity,
        "waiting": None,
        "score": score,
        "score_breakdown": breakdown,
        "confidence": confidence,
        "limitations": build_limitations(route, has_scores, time_slice),
        "explanations": build_explanations(kind, status, fastest, route, detour),
        "sources": SOURCES if has_scores else [],
    }


def build_route_response(
    area: str,
    bbox: tuple[float, float, float, float] | None,
    fastest: dict,
    time_slice: dict | None,
    alternatives: list[dict],
) -> dict:
    """alternatives: one dict per preference profile, each
    {"kind": str, "route": dict, "status": str, "detour": dict} - all
    produced against the same `fastest` baseline from backend.routing.
    """
    first_status = alternatives[0]["status"] if alternatives else "baseline_only"

    routes = [_route_payload("fastest", fastest, first_status, None, time_slice, fastest)]
    for alt in alternatives:
        routes.append(_route_payload(alt["kind"], alt["route"], alt["status"], alt["detour"], time_slice, fastest))

    description = f"Supported walking network: {area}."
    if first_status == "baseline_only":
        description += " No lighting or footfall evidence is available here."

    return {
        "mode": "walking",
        "coverage": {
            "bounds": list(bbox) if bbox else None,
            "description": description,
        },
        "routes": routes,
    }
