"""POST /route: the routing engine behind docs/api-contract.md.

Routes, distances and times come from backend.routing. The score breakdown,
data confidence and explanation below are provisional: they restate measured
route facts only, until backend/scoring (Person 4) defines the real rules.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime, BaseModel, Field

from backend.routing import Preferences, RoutingError, get_route, get_store
from backend.routing import config as routing_config

router = APIRouter()
LOCAL_ZONE = ZoneInfo("Europe/Dublin")
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Routing error code -> (HTTP status, contract error code).
ROUTING_ERRORS = {
    "outside_coverage": (422, "OUT_OF_AREA"),
    "too_far": (422, "OUT_OF_AREA"),
    "same_point": (400, "INVALID_INPUT"),
    "no_route": (404, "NO_ROUTE"),
    "graph_unavailable": (503, "INTERNAL_ERROR"),
}


class Point(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class RoutePreferences(BaseModel):
    max_detour_minutes: float = Field(routing_config.DEFAULT_MAX_EXTRA_MIN, ge=0, le=60)
    well_lit: float = Field(0.5, ge=0, le=1)
    busier: float = Field(0.5, ge=0, le=1)
    less_walking: float = Field(0.5, ge=0, le=1)
    less_waiting: float = Field(0.5, ge=0, le=1)  # transit only; unused while walking-only
    avoid_nightlife: bool = False


class RouteRequest(BaseModel):
    origin: Point
    destination: Point
    departure_time: AwareDatetime | None = None
    preferences: RoutePreferences = RoutePreferences()


def error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"routes": None, "error": {"code": code, "message": message}}, status)


def engine_preferences(prefs: RoutePreferences, use_activity: bool) -> Preferences:
    """Contract weights (0 to 1, default 0.5) to engine strengths.

    A weight of 0.5 gives the engine's own default for that factor.
    less_walking scales every factor: 0.5 leaves them alone, 1 switches them off.
    """
    strength = 2 * (1 - prefs.less_walking)
    return Preferences(
        well_lit=2 * prefs.well_lit * strength,
        busier=prefs.busier * strength if use_activity else 0.0,
        crossings=strength,
    )


def percent(share: float | None) -> int | None:
    return None if share is None else round(share * 100)


def build_response(result: dict, prefs: RoutePreferences, use_activity: bool) -> dict:
    fastest, night = result["fastest"], result["night"]
    status, time_slice = result["status"], result["time_slice"]
    lighting = percent(night["lighting"]["score"])
    activity = percent(night["activity"]["score"]) if use_activity else None
    lighting_cover = percent(night["lighting"]["coverage"])
    activity_cover = percent(night["activity"]["coverage"]) if use_activity else 0

    # Provisional confidence: coverage alone never justifies "high".
    level = "medium" if status != "baseline_only" and lighting_cover >= 50 else "low"
    reasons = [
        f"Lighting data covers {lighting_cover}% of the Night Route's length."
        if lighting_cover
        else "No lighting data covers this route.",
        f"Recorded footfall data covers {activity_cover}% of the Night Route's length."
        if activity_cover
        else "Recorded footfall is unknown for this route at this time.",
    ]

    if status == "baseline_only":
        explanation = [
            "Only the fastest route is available here: no lighting or footfall "
            "data covers this area, so no Night Route was calculated."
        ]
    elif status == "same_route":
        explanation = [
            "Both options follow the same route: the fastest route already "
            "best matches these preferences."
        ]
    elif status == "no_alternative":
        explanation = [
            f"No alternative fits within the {prefs.max_detour_minutes:g} minute "
            "detour limit, so the fastest route is shown for both options."
        ]
    else:
        extra_m = round(night["distance_m"] - fastest["distance_m"])
        explanation = [
            f"Night Route is {extra_m} m longer than the fastest route "
            f"({night['duration_min']} min against {fastest['duration_min']} min)."
        ]
        if lighting is not None and fastest["lighting"]["score"] is not None:
            explanation.append(
                f"Night Route has lighting coverage on {lighting}% of its length; "
                f"the fastest route has {percent(fastest['lighting']['score'])}%."
            )

    warnings = []
    if time_slice and not use_activity:
        warnings.append(
            f"Recorded footfall is only available for {WEEKDAYS[time_slice['weekday']]} "
            f"{time_slice['hour']:02}:00, so activity was not used for this departure time."
        )
    if not lighting_cover:
        warnings.append("This route is outside the area with lighting data.")
    if prefs.avoid_nightlife:
        warnings.append("avoid_nightlife is not supported yet and was ignored.")

    def route(source: dict) -> dict:
        return {
            "geometry": source["geometry"],
            "distance_metres": source["distance_m"],
            "duration_minutes": source["duration_min"],
            "route_score": None,  # pending backend/scoring
        }

    return {
        "routes": {"fastest": route(fastest), "night": route(night)},
        "score_breakdown": {
            "lighting": lighting,
            "activity": activity,
            "crossings": None,
            "waiting": None,
        },
        "data_confidence": {"level": level, "reasons": reasons},
        "explanation": explanation,
        "warnings": warnings,
    }


@router.post("/route")
def post_route(request: RouteRequest):
    local = (request.departure_time or datetime.now(LOCAL_ZONE)).astimezone(LOCAL_ZONE)
    try:
        # Footfall scores exist for one weekday and hour; use them only then.
        time_slice = get_store().bundle.time_slice
        use_activity = bool(
            time_slice
            and (time_slice["weekday"], time_slice["hour"]) == (local.weekday(), local.hour)
        )
        result = get_route(
            (request.origin.lat, request.origin.lng),
            (request.destination.lat, request.destination.lng),
            engine_preferences(request.preferences, use_activity),
            request.preferences.max_detour_minutes,
        )
    except RoutingError as error:
        status, code = ROUTING_ERRORS.get(error.code, (500, "INTERNAL_ERROR"))
        return error_response(status, code, str(error))
    return build_response(result, request.preferences, use_activity)
