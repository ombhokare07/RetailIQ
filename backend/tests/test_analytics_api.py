from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_stockout_endpoint_returns_evidence_backed_results():
    response = client.get("/api/inventory/stockout-risk?store_id=S001&product_id=P001")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["count"] == 1
    assert body["items"][0]["risk"] == "critical"
    assert "evidence" in body["items"][0]


def test_dashboard_summary_endpoint():
    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["analysis_date"] == "2026-09-04"
    assert "attention" in body


def test_sales_anomaly_filter_endpoint():
    response = client.get("/api/sales/anomalies?store_id=S003&product_id=P005")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["anomaly_type"] == "spike"


def test_assumptions_endpoint_exposes_rules():
    response = client.get("/api/dashboard/assumptions")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["thresholds"]["stockout"]["target_inventory_days"] == 21


def test_product_performance_endpoint_supports_problem_statement_question():
    response = client.get("/api/products/P001/performance?store_id=S001")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["product_id"] == "P001"
    assert body["current"]["units_sold"] > 0
    assert body["evidence"]["current_sale_ids"]


def test_store_performance_endpoint():
    response = client.get("/api/stores/S001/performance")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["store_id"] == "S001"
    assert body["current"]["revenue"] > 0


def test_unknown_product_returns_404_instead_of_guessing():
    response = client.get("/api/products/DOES-NOT-EXIST/performance")
    assert response.status_code == 404
