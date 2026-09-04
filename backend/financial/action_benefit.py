from __future__ import annotations

import math


def calculate_transfer_action_benefits(
    context,
    transfer_recommendations: list[dict],
    *,
    emergency_purchase_markup: float,
) -> list[dict]:
    product_lookup = {
        str(row.product_id): row for row in context.products.itertuples(index=False)
    }
    results: list[dict] = []

    for item in transfer_recommendations:
        product = product_lookup.get(str(item["product_id"]))
        cost_price = float(getattr(product, "cost_price", 0.0) or 0.0)
        selling_price = float(getattr(product, "selling_price", 0.0) or 0.0)
        qty = int(item["recommended_transfer_quantity"])
        current = int(item["recipient_current_stock"])
        avg = float(item["recipient_avg_daily_sales"])
        lead = int(item.get("supplier_lead_time_days") or 0)

        expected_demand = math.ceil(avg * lead)
        shortage_without_action = max(0, expected_demand - current)
        protected_units = min(qty, shortage_without_action)
        revenue_protected = protected_units * selling_price
        gross_margin_protected = protected_units * max(0.0, selling_price - cost_price)
        transfer_cost = float(item["estimated_transfer_cost"])
        emergency_purchase_cost = qty * cost_price * (1.0 + float(emergency_purchase_markup))
        near_term_cash_purchase_deferred = qty * cost_price
        estimated_net_operational_benefit = gross_margin_protected - transfer_cost

        results.append(
            {
                "recommendation_id": item["recommendation_id"],
                "recipient_store_id": item["recipient_store_id"],
                "recipient_store_name": item["recipient_store_name"],
                "source_store_id": item["recommended_source_store_id"],
                "source_store_name": item["recommended_source_store_name"],
                "product_id": item["product_id"],
                "product_name": item["product_name"],
                "transfer_quantity": qty,
                "estimated_shortage_units_without_action": shortage_without_action,
                "estimated_units_protected": protected_units,
                "revenue_protected": round(revenue_protected, 2),
                "gross_margin_protected": round(gross_margin_protected, 2),
                "estimated_transfer_cost": round(transfer_cost, 2),
                "near_term_cash_purchase_deferred": round(near_term_cash_purchase_deferred, 2),
                "estimated_emergency_purchase_cost": round(emergency_purchase_cost, 2),
                "estimated_net_operational_benefit": round(estimated_net_operational_benefit, 2),
                "assumptions": [
                    "Protected revenue is capped at the estimated shortage before normal replenishment.",
                    "Emergency purchase cost is a configured scenario estimate, not a live supplier quote.",
                    "Near-term purchase deferred is not permanent savings; transferred stock may need replenishment later.",
                ],
                "evidence": item.get("evidence"),
            }
        )

    return sorted(results, key=lambda x: (-x["estimated_net_operational_benefit"], x["recommendation_id"]))
