from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from backend.db import get_client
from backend.routing import RoutingError, get_store
from backend.scoring import build_route_response

from .errors import map_routing_error
from .schemas import RouteRequest


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_store()  # warm the graph/scores cache so the first request is fast
    yield


app = FastAPI(title="Ireland After Dark API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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

    result = engine.route(origin, destination)
    result["area"] = area
    result["time_slice"] = store.bundle.time_slice

    return build_route_response(area, bbox, result)
