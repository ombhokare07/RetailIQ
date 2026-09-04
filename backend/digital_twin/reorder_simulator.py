from __future__ import annotations

from backend.digital_twin.scenario_builder import round2, simulate_timed_inflow


def simulate_reorder(
    *,
    current_stock: int,
    avg_daily_sales: float,
    horizon_days: int,
    demand_multiplier: float,
    reorder_quantity: int,
    lead_time_days: int,
    selling_price: float,
    cost_price: float,
) -> dict:
    quantity = max(0, int(reorder_quantity))
    outcome = simulate_timed_inflow(
        current_stock=current_stock,
        avg_daily_sales=avg_daily_sales,
        demand_multiplier=demand_multiplier,
        horizon_days=horizon_days,
        inflow_units=quantity,
        inflow_arrival_days=lead_time_days,
    )
    shortage = int(outcome["unserved_units"])
    margin = max(0.0, float(selling_price) - float(cost_price))
    revenue_lost = shortage * float(selling_price)
    gross_margin_lost = shortage * margin
    purchase_cash = quantity * float(cost_price)
    return {
        "scenario_id": "supplier_reorder",
        "label": "Supplier Reorder",
        "action": "reorder",
        **outcome,
        "action_quantity": quantity,
        "supplier_lead_time_days": int(lead_time_days),
        "cash_committed": round2(purchase_cash),
        "execution_cost": 0.0,
        "estimated_revenue_lost": round2(revenue_lost),
        "estimated_gross_margin_lost": round2(gross_margin_lost),
        "estimated_operational_loss": round2(gross_margin_lost),
        "assumptions": [
            "The supplier order arrives after the committed product lead time.",
            "Purchase cash is reported separately because purchased inventory remains an asset rather than an immediate operating loss.",
            "Recent average demand continues after applying the selected demand multiplier.",
        ],
    }
