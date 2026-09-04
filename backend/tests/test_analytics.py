from backend.services.analytics_service import AnalyticsService


def find(items, store_id, product_id):
    return next(
        item
        for item in items
        if item["store_id"] == store_id and item["product_id"] == product_id
    )


def test_seeded_critical_stockout_is_detected():
    service = AnalyticsService()
    item = find(service.stockout_items, "S001", "P001")

    assert item["risk"] == "critical"
    assert item["days_cover"] is not None
    assert item["days_cover"] <= item["lead_time_days"]
    assert item["recommended_reorder_qty"] > 0
    assert item["evidence"]["inventory_id"].startswith("INV-")
    assert item["evidence"]["sales_window"]["sale_ids"]


def test_missing_reorder_level_is_exposed_not_guessed():
    service = AnalyticsService()
    item = find(service.stockout_items, "S001", "P049")

    assert item["risk"] == "unknown"
    assert item["recommended_reorder_qty"] is None
    assert "reorder_level" in item["unknown_fields"]


def test_seeded_overstock_and_slow_mover_are_detected():
    service = AnalyticsService()
    overstock = find(service.overstock_items, "S001", "P003")
    slow = find(service.slow_mover_items, "S002", "P004")

    assert overstock["severity"] in {"overstock", "severe"}
    assert overstock["days_cover"] > 60
    assert slow["movement"] == "slow_moving"
    assert slow["units_sold"] <= 20


def test_seeded_zero_sales_product_is_detected():
    service = AnalyticsService()
    slow = find(service.slow_mover_items, "S002", "P007")

    assert slow["movement"] == "zero_sales"
    assert slow["units_sold"] == 0


def test_seeded_sales_spike_and_drop_are_detected():
    service = AnalyticsService()
    spike = find(service.anomaly_items, "S003", "P005")
    drop = find(service.anomaly_items, "S001", "P006")

    assert spike["anomaly_type"] == "spike"
    assert spike["percentage_change"] >= 50
    assert drop["anomaly_type"] == "drop"
    assert drop["percentage_change"] <= -50


def test_insufficient_history_is_not_forced_into_an_anomaly():
    service = AnalyticsService()
    matches = [
        item
        for item in service.anomaly_items
        if item["store_id"] == "S003" and item["product_id"] == "P050"
    ]
    stock = find(service.stockout_items, "S003", "P050")

    assert matches == []
    assert stock["risk"] == "unknown"
    assert "recent_sales_history" in stock["unknown_fields"]


def test_dashboard_summary_contains_grounded_counts():
    service = AnalyticsService()
    summary = service.dashboard_summary()

    assert summary["analysis_date"] == "2026-09-04"
    assert summary["sales"]["revenue"] > 0
    assert summary["inventory"]["stockout_risk"]["critical"] >= 1
    assert summary["sales_anomalies"]["spike"] >= 1
    assert summary["sales_anomalies"]["drop"] >= 1
    assert summary["data_quality"]["unknown_stockout_recommendations"] >= 1
