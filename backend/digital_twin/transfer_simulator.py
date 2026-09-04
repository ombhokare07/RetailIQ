from __future__ import annotations

from backend.digital_twin.scenario_builder import round2, simulate_timed_inflow


def simulate_transfer(
    *,
    current_stock: int,
    avg_daily_sales: float,
    horizon_days: int,
    demand_multiplier: float,
    transfer_quantity: int,
    transfer_arrival_days: int,
    transfer_cost: float,
    selling_price: float,
    cost_price: float,
    source_store_id: str,
    source_store_name: str,
    donor_after_days_cover: float | None,
) -> dict:
    quantity = max(0, int(transfer_quantity))
    outcome = simulate_timed_inflow(
        current_stock=current_stock,
        avg_daily_sales=avg_daily_sales,
        demand_multiplier=demand_multiplier,
        horizon_days=horizon_days,
        inflow_units=quantity,
        inflow_arrival_days=transfer_arrival_days,
    )
    shortage = int(outcome["unserved_units"])
    margin = max(0.0, float(selling_price) - float(cost_price))
    revenue_lost = shortage * float(selling_price)
    gross_margin_lost = shortage * margin
    execution = max(0.0, float(transfer_cost))
    return {
        "scenario_id": "smart_transfer",
        "label": "Smart Inter-Store Transfer",
        "action": "transfer",
        **outcome,
        "action_quantity": quantity,
        "transfer_arrival_days": int(transfer_arrival_days),
        "source_store_id": source_store_id,
        "source_store_name": source_store_name,
        "donor_after_days_cover": donor_after_days_cover,
        "cash_committed": 0.0,
        "execution_cost": round2(execution),
        "estimated_revenue_lost": round2(revenue_lost),
        "estimated_gross_margin_lost": round2(gross_margin_lost),
        "estimated_operational_loss": round2(gross_margin_lost + execution),
        "assumptions": [
            "The transfer arrives within the configured internal-transfer arrival time.",
            "The donor store keeps its configured demand reserve after the transfer.",
            "Transfer cost is a configured estimate, not a live carrier quote.",
            "Recent average demand continues after applying the selected demand multiplier.",
        ],
    }
