from backend.services.decision_service import DecisionService


def test_seeded_transfer_opportunity_uses_mumbai_for_pune_milk():
    service = DecisionService()
    items = service.transfer_recommendations(store_id="S001", product_id="P001")
    assert len(items) == 1
    item = items[0]
    assert item["recipient_risk"] == "critical"
    assert item["recommended_source_store_id"] == "S002"
    assert item["recommended_transfer_quantity"] == 129
    assert item["recipient_after_days_cover"] >= 20.9
    assert item["donor_after_days_cover"] >= 21
    assert item["estimated_transfer_cost"] == 572.5
    assert item["evidence"]["recipient"]["inventory_id"]
    assert item["evidence"]["donor"]["inventory_id"]


def test_all_transfer_options_protect_donor_reserve():
    service = DecisionService()
    for recommendation in service.transfer_recommendations():
        for source in recommendation["alternative_sources"]:
            assert source["donor_after_stock"] >= source["donor_reserve_units"]
            if source["donor_after_days_cover"] is not None:
                assert source["donor_after_days_cover"] >= 21


def test_unknown_stockout_case_does_not_generate_transfer():
    service = DecisionService()
    assert service.transfer_recommendations(store_id="S001", product_id="P049") == []


def test_financial_risk_for_seeded_pune_milk_is_traceable():
    service = DecisionService()
    items = service.revenue_risk(store_id="S001", product_id="P001")
    assert len(items) == 1
    item = items[0]
    assert item["estimated_shortage_units"] == 10
    assert item["revenue_at_risk"] > 0
    assert item["gross_margin_at_risk"] > 0
    assert item["evidence"]["inventory_id"]


def test_overstock_capital_is_positive_for_seeded_paneer():
    service = DecisionService()
    items = service.overstock_capital(store_id="S001", product_id="P003")
    assert len(items) == 1
    item = items[0]
    assert item["severity"] in {"overstock", "severe"}
    assert item["estimated_excess_units"] > 0
    assert item["blocked_capital_at_cost"] > 0


def test_transfer_benefit_is_explicit_about_estimates():
    service = DecisionService()
    items = service.transfer_benefits(store_id="S001", product_id="P001")
    assert len(items) == 1
    item = items[0]
    assert item["estimated_units_protected"] <= item["transfer_quantity"]
    assert item["estimated_transfer_cost"] > 0
    assert item["near_term_cash_purchase_deferred"] > 0
    assert len(item["assumptions"]) >= 3


def test_financial_summary_contains_both_exposures_and_transfer_value():
    summary = DecisionService().financial_summary()
    assert summary["currency"] == "INR"
    assert summary["stockout_exposure"]["revenue_at_risk"] >= 0
    assert summary["overstock_exposure"]["blocked_capital_at_cost"] >= 0
    assert summary["smart_transfer"]["recommendations"] >= 1
    assert "scenario estimates" in summary["disclaimer"]
