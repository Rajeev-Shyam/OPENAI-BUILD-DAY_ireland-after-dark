from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from backend.db import get_client
from backend.routing import RoutingError, get_store
from backend.scoring import build_route_response
from backend.routing.engine import Preferences
from data.pipeline.time_scores import departure_slot

from .errors import map_routing_error
from .schemas import RouteRequest
from .geocoding import PlaceQuery, search
from .transport import stops, realtime_status
from .hospitals import attach_hospitals
from backend.routing.alternatives import add_alternatives


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_store()  # warm the graph/scores cache so the first request is fast
    yield


app = FastAPI(title="Ireland After Dark API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                   "http://localhost:4173", "http://127.0.0.1:4173",
                   "http://127.0.0.1:5174"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware('http')
async def no_store(request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.post('/geocode')
def geocode(payload: PlaceQuery):
    try:
        result = search(payload.query)
        if result is None:
            return _error_response('PLACE_NOT_FOUND', 'No matching place found in Ireland. Try latitude, longitude.', 404)
        return result
    except (ValueError, OSError):
        return _error_response('SEARCH_UNAVAILABLE', 'Place search unavailable. Try latitude, longitude.', 503)


@app.get('/transport/stops')
def transport_stops():
    try:
        return stops()
    except (OSError, ValueError, KeyError, TypeError):
        return _error_response('DATA_UNAVAILABLE', 'Luas stop snapshot is unavailable. Walking routes still work.', 503)


@app.get('/transport/status')
def transport_status():
    try:
        return realtime_status()
    except (OSError, ValueError, KeyError, TypeError):
        return {'status': 'unavailable', 'received_at_unix': None, 'age_seconds': None,
                'message': 'Saved NTA snapshot failed validation.'}


def _error_response(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0]
    field = ".".join(str(part) for part in first["loc"] if part != "body")
    return _error_response("INVALID_INPUT", f"{field}: {first['msg']}", 400)


@app.exception_handler(RoutingError)
async def handle_routing_error(request: Request, exc: RoutingError) -> JSONResponse:
    code, status, message = map_routing_error(exc)
    return _error_response(code, message, status)


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    return _error_response("INTERNAL_ERROR", "Unexpected server error.", 500)


@app.get("/health")
def health() -> dict:
    mongo_connected = False
    try:
        get_client().admin.command("ping")
        mongo_connected = True
    except PyMongoError:
        mongo_connected = False

    return {"status": "ok", "mongo_connected": mongo_connected}


@app.post("/route")
def route(payload: RouteRequest) -> dict:
    origin = (payload.origin[1], payload.origin[0])  # [lng, lat] -> (lat, lon)
    destination = (payload.destination[1], payload.destination[0])

    store = get_store()
    area, engine = store.engine_for(origin, destination)
    bbox, _ = store._engines[area]

    time_slice = store.bundle.time_slice
    activity_enabled = bool(time_slice and departure_slot(payload.departure_time) ==
                            (time_slice['weekday'], time_slice['hour']))
    prefs = Preferences(busier=0.5 if activity_enabled else 0.0)
    result = engine.route(origin, destination, prefs)
    result = add_alternatives(engine, result, prefs)
    if not activity_enabled:
        for candidate in [result['fastest'], result['night'], *result.get('alternatives', [])]:
            candidate['activity'] = {'score': None, 'coverage': 0.0}
    if all(candidate['lighting']['score'] is None and candidate['activity']['score'] is None
           for candidate in [result['fastest'], result['night'], *result.get('alternatives', [])]):
        result['status'] = 'baseline_only'
    result["area"] = area
    result["time_slice"] = store.bundle.time_slice

    response = build_route_response(area, bbox, result)
    response['activity_enabled'] = activity_enabled
    response['departure_time'] = payload.departure_time.isoformat()
    if not activity_enabled:
        for route in response['routes']:
            route['limitations'].append('Historical activity is excluded from ranking and display: no matching weekday/hour snapshot for this departure.')
    return attach_hospitals(response)
