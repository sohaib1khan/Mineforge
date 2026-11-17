"""Health endpoint smoke tests."""

from app.main import create_app
from fastapi.testclient import TestClient


def test_health_returns_ok() -> None:
    """Liveness endpoint reports status ok and the display name."""

    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["app"] == "MineForge"
