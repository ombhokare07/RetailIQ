from __future__ import annotations

from backend.digital_twin.scenario_builder import round2, simulate_timed_inflow


def simulate_no_action(
    *,
    current_stock: int,
    avg_daily_sales: float,
    horizon_days: int,
    demand_multiplier: float,
    selling_price: float,
    cost_price: float,
) -> dict:
    outcome = simulate_timed_inflow(
        current_stock=current_stock,
        avg_daily_sales=avg_daily_sales,
        demand_multiplier=demand_multiplier,
        horizon_days=horizon_days,
        inflow_units=0,
        inflow_arrival_days=horizon_days,
    )
    shortage = int(outcome["unserved_units"])
    margin = max(0.0, float(selling_price) - float(cost_price))
    revenue_lost = shortage * float(selling_price)
    gross_margin_lost = shortage * margin
    return {
        "scenario_id": "no_action",
        "label": "No Action",
        "action": "no_action",
        **outcome,
        "action_quantity": 0,
        "cash_committed": 0.0,
        "execution_cost": 0.0,
        "estimated_revenue_lost": round2(revenue_lost),
        "estimated_gross_margin_lost": round2(gross_margin_lost),
        "estimated_operational_loss": round2(gross_margin_lost),
        "assumptions": [
            "No stock is replenished during the simulation horizon.",
            "Recent average demand continues after applying the selected demand multiplier.",
        ],
    }
