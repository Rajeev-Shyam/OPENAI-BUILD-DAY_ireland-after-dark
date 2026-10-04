from pymongo import MongoClient
from pymongo.database import Database

from backend.settings import settings

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=1500, connectTimeoutMS=1500)
    return _client


def get_db() -> Database:
    return get_client()[settings.mongodb_db_name]
