import os

from fastapi.testclient import TestClient

from backend.api.copilot import get_copilot_service
from backend.main import app

client = TestClient(app)


def setup_function():
    os.environ.pop("GEMINI_API_KEY", None)
    get_copilot_service.cache_clear()


def test_copilot_status_endpoint():
    response = client.get("/api/copilot/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["startup_network_calls"] is False


def test_copilot_query_endpoint_normal_case():
    response = client.post(
        "/api/copilot/query",
        json={"message": "Which products may run out in Pune?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "stockout_risk"
    assert body["data"]
    assert body["evidence"]


def test_copilot_query_endpoint_difficult_case():
    response = client.post(
        "/api/copilot/query",
        json={"message": "Why did Brown Bread sales fall in Pune?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "causal_explanation"
    assert body["data"]["causal_evidence_available"] is False
    assert body["unknowns"]


def test_copilot_query_empty_message_is_validation_error():
    response = client.post("/api/copilot/query", json={"message": ""})
    assert response.status_code == 422
