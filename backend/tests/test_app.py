from fastapi.testclient import TestClient
from backend.main import app


def test_health():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "RetailIQ"


def test_api_health():
    client = TestClient(app)
    assert client.get("/api/health").status_code == 200
