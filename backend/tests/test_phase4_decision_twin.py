from backend.services.simulation_service import SimulationService


def test_seeded_milk_decision_twin_compares_three_scenarios():
    result = SimulationService().compare(store_id="S001", product_id="P001")
    assert result["status"] == "ok"
    ids = {scenario["scenario_id"] for scenario in result["scenarios"]}
    assert ids == {"no_action", "supplier_reorder", "smart_transfer"}
    assert result["comparison"]["recommended_scenario_id"] == "smart_transfer"


def test_smart_transfer_prevents_seeded_milk_shortage_better_than_reorder():
    result = SimulationService().compare(store_id="S001", product_id="P001")
    scenarios = {s["scenario_id"]: s for s in result["scenarios"]}
    assert scenarios["smart_transfer"]["unserved_units"] == 0
    assert scenarios["supplier_reorder"]["unserved_units"] > 0
    assert scenarios["no_action"]["unserved_units"] > scenarios["supplier_reorder"]["unserved_units"]
    assert scenarios["smart_transfer"]["donor_after_days_cover"] >= 21


def test_demand_shock_changes_simulated_demand_without_claiming_forecast():
    result = SimulationService().compare(
        store_id="S001", product_id="P001", demand_multiplier=1.5
    )
    assumption = result["demand_assumption"]
    assert assumption["demand_multiplier"] == 1.5
    assert assumption["simulated_avg_daily_sales"] > assumption["baseline_avg_daily_sales"]
    assert "what-if" in assumption["note"]


def test_unknown_seeded_case_refuses_decision_simulation():
    result = SimulationService().compare(store_id="S001", product_id="P049")
    assert result["status"] == "insufficient_data"
    assert result["scenarios"] == []
    assert "reorder_level" in result["unknown_fields"]
    assert result["comparison"]["recommended_scenario_id"] is None


def test_missing_pair_returns_not_found_result():
    result = SimulationService().compare(store_id="NOPE", product_id="P001")
    assert result["status"] == "not_found"
