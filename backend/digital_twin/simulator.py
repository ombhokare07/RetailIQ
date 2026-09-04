from __future__ import annotations

from backend.digital_twin.demand_shock_simulator import build_demand_shock_summary
from backend.digital_twin.no_action_simulator import simulate_no_action
from backend.digital_twin.reorder_simulator import simulate_reorder
from backend.digital_twin.scenario_builder import validate_simulation_inputs
from backend.digital_twin.scenario_comparator import compare_scenarios
from backend.digital_twin.transfer_simulator import simulate_transfer


def simulate_decision(
    *,
    stockout_item: dict,
    product: object,
    transfer_recommendation: dict | None,
    horizon_days: int,
    demand_multiplier: float,
    transfer_arrival_days: int,
) -> dict:
    unknown = validate_simulation_inputs(
        current_stock=stockout_item.get("current_stock"),
        avg_daily_sales=stockout_item.get("avg_daily_sales"),
        lead_time_days=stockout_item.get("lead_time_days"),
        horizon_days=horizon_days,
        demand_multiplier=demand_multiplier,
        unknown_fields=stockout_item.get("unknown_fields"),
    )
    if stockout_item.get("recommended_reorder_qty") is None:
        unknown.append("recommended_reorder_qty")
    unknown = sorted(set(unknown))

    base = {
        "store_id": stockout_item.get("store_id"),
        "store_name": stockout_item.get("store_name"),
        "product_id": stockout_item.get("product_id"),
        "product_name": stockout_item.get("product_name"),
        "analysis_date": stockout_item.get("evidence", {}).get("inventory_date"),
        "horizon_days": int(horizon_days),
        "demand_multiplier": round(float(demand_multiplier), 2),
    }

    if unknown:
        return {
            **base,
            "status": "insufficient_data",
            "unknown_fields": unknown,
            "scenarios": [],
            "comparison": compare_scenarios([]),
            "message": "RetailIQ cannot run a reliable decision simulation because required input data is missing or uncertain.",
            "evidence": stockout_item.get("evidence"),
        }

    current_stock = int(stockout_item["current_stock"])
    avg = float(stockout_item["avg_daily_sales"])
    lead = int(stockout_item["lead_time_days"])
    reorder_qty = int(stockout_item["recommended_reorder_qty"])
    selling_price = float(getattr(product, "selling_price", 0.0) or 0.0)
    cost_price = float(getattr(product, "cost_price", 0.0) or 0.0)

    scenarios = [
        simulate_no_action(
            current_stock=current_stock,
            avg_daily_sales=avg,
            horizon_days=horizon_days,
            demand_multiplier=demand_multiplier,
            selling_price=selling_price,
            cost_price=cost_price,
        ),
        simulate_reorder(
            current_stock=current_stock,
            avg_daily_sales=avg,
            horizon_days=horizon_days,
            demand_multiplier=demand_multiplier,
            reorder_quantity=reorder_qty,
            lead_time_days=lead,
            selling_price=selling_price,
            cost_price=cost_price,
        ),
    ]

    if transfer_recommendation:
        scenarios.append(
            simulate_transfer(
                current_stock=current_stock,
                avg_daily_sales=avg,
                horizon_days=horizon_days,
                demand_multiplier=demand_multiplier,
                transfer_quantity=int(transfer_recommendation["recommended_transfer_quantity"]),
                transfer_arrival_days=transfer_arrival_days,
                transfer_cost=float(transfer_recommendation["estimated_transfer_cost"]),
                selling_price=selling_price,
                cost_price=cost_price,
                source_store_id=str(transfer_recommendation["recommended_source_store_id"]),
                source_store_name=str(transfer_recommendation["recommended_source_store_name"]),
                donor_after_days_cover=transfer_recommendation.get("donor_after_days_cover"),
            )
        )

    return {
        **base,
        "status": "ok",
        "current_state": {
            "risk": stockout_item.get("risk"),
            "current_stock": current_stock,
            "avg_daily_sales": avg,
            "days_cover": stockout_item.get("days_cover"),
            "supplier_lead_time_days": lead,
            "recommended_reorder_qty": reorder_qty,
            "selling_price": round(selling_price, 2),
            "cost_price": round(cost_price, 2),
        },
        "demand_assumption": build_demand_shock_summary(
            baseline_avg_daily_sales=avg,
            demand_multiplier=demand_multiplier,
            horizon_days=horizon_days,
        ),
        "scenarios": scenarios,
        "comparison": compare_scenarios(scenarios),
        "evidence": stockout_item.get("evidence"),
        "principle": "The Decision Twin simulates scenarios with deterministic business logic; no LLM calculates outcomes or chooses the recommendation.",
    }
