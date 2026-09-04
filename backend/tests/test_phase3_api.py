from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_transfer_recommendations_endpoint():
    response = client.get(
        "/api/transfers/recommendations",
        params={"store_id": "S001", "product_id": "P001"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["count"] == 1
    assert body["items"][0]["recommended_source_store_id"] == "S002"


def test_financial_summary_endpoint():
    response = client.get("/api/financial/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["currency"] == "INR"
    assert body["smart_transfer"]["recommendations"] >= 1


def test_financial_detail_endpoints():
    urls = [
        "/api/financial/revenue-risk?store_id=S001&product_id=P001",
        "/api/financial/overstock-capital?store_id=S001&product_id=P003",
        "/api/financial/transfer-benefits?store_id=S001&product_id=P001",
    ]
    for url in urls:
        response = client.get(url)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["count"] >= 1
