from fastapi.testclient import TestClient

from backend.api.main import app
from unittest.mock import Mock

client = TestClient(app)


def test_health_returns_ok_status(monkeypatch):
    monkeypatch.setattr('backend.api.main.get_client', lambda: Mock())
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
