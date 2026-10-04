"""Maps the routing engine's result shape onto frontend/API_CONTRACT_PROPOSED.md.

Keeps both Person 1's engine and the frontend's adapter unchanged; all the
translation lives here.
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


def _route_payload(kind: str, route: dict, status: str, detour: dict, time_slice: dict | None, siblings: dict) -> dict:
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
        "explanations": build_explanations(kind, status, siblings["fastest"], siblings["night"], detour),
        "sources": SOURCES if has_scores else [],
    }


def build_route_response(area: str, bbox: tuple[float, float, float, float] | None, engine_result: dict) -> dict:
    """engine_result is backend.routing.get_route()'s return value, plus the
    area's bbox (left, bottom, right, top) from the GraphStore."""
    fastest = engine_result["fastest"]
    night = engine_result["night"]
    status = engine_result["status"]
    detour = engine_result["detour"]
    time_slice = engine_result.get("time_slice")
    siblings = {"fastest": fastest, "night": night}

    routes = [
        _route_payload("fastest", fastest, status, detour, time_slice, siblings),
        _route_payload("night", night, status, detour, time_slice, siblings),
    ]

    description = f"Supported walking network: {area}."
    if status == "baseline_only":
        description += " No lighting or footfall evidence is available here."

    return {
        "mode": "walking",
        "coverage": {
            "bounds": list(bbox) if bbox else None,
            "description": description,
        },
        "routes": routes,
    }
