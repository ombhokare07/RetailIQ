from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_decision_twin_compare_endpoint():
    response = client.get(
        "/api/simulation/compare",
        params={"store_id": "S001", "product_id": "P001"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["comparison"]["recommended_scenario_id"] == "smart_transfer"
    assert len(body["scenarios"]) == 3


def test_decision_twin_demand_shock_endpoint():
    response = client.get(
        "/api/simulation/demand-shock",
        params={"store_id": "S001", "product_id": "P001", "demand_multiplier": 1.5},
    )
    assert response.status_code == 200
    assert response.json()["demand_assumption"]["demand_multiplier"] == 1.5


def test_decision_twin_incomplete_data_is_graceful():
    response = client.get(
        "/api/simulation/compare",
        params={"store_id": "S001", "product_id": "P049"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "insufficient_data"
    assert body["scenarios"] == []


def test_decision_twin_invalid_pair_is_404():
    response = client.get(
        "/api/simulation/compare",
        params={"store_id": "BAD", "product_id": "P001"},
    )
    assert response.status_code == 404
