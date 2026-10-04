import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pymongo.errors import PyMongoError

from backend.api.route import error_response, router as route_router
from backend.db import get_client
from backend.routing import get_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the walking graph in the background (about 12 s) so /health answers
    # at once; a /route request arriving during the load waits for it.
    threading.Thread(target=get_store, daemon=True).start()
    yield


app = FastAPI(title="Ireland After Dark API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(route_router)


@app.exception_handler(RequestValidationError)
async def invalid_input(request: Request, error: RequestValidationError):
    first = error.errors()[0]
    field = ".".join(str(part) for part in first["loc"] if part != "body")
    return error_response(400, "INVALID_INPUT", f"{field}: {first['msg']}".lstrip(": "))


@app.exception_handler(Exception)
async def internal_error(request: Request, error: Exception):
    return error_response(500, "INTERNAL_ERROR", "Unexpected server-side failure.")


@app.get("/health")
def health() -> dict:
    mongo_connected = False
    try:
        get_client().admin.command("ping")
        mongo_connected = True
    except PyMongoError:
        mongo_connected = False

    return {"status": "ok", "mongo_connected": mongo_connected}
