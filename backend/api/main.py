from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo.errors import PyMongoError

from backend.db import get_client

app = FastAPI(title="Ireland After Dark API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    mongo_connected = False
    try:
        get_client().admin.command("ping")
        mongo_connected = True
    except PyMongoError:
        mongo_connected = False

    return {"status": "ok", "mongo_connected": mongo_connected}
