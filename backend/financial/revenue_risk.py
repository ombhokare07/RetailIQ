from __future__ import annotations

import math


def calculate_revenue_risk(context, stockout_items: list[dict]) -> list[dict]:
    product_lookup = {
        str(row.product_id): row for row in context.products.itertuples(index=False)
    }
    results: list[dict] = []

    for item in stockout_items:
        if item.get("risk") not in {"critical", "high"}:
            continue
        avg = item.get("avg_daily_sales")
        lead = item.get("lead_time_days")
        current = item.get("current_stock")
        if avg is None or lead is None or current is None or avg <= 0:
            continue

        product = product_lookup.get(str(item["product_id"]))
        selling_price = float(getattr(product, "selling_price", 0.0) or 0.0)
        cost_price = float(getattr(product, "cost_price", 0.0) or 0.0)
        expected_demand_during_lead = math.ceil(float(avg) * int(lead))
        shortage_units = max(0, expected_demand_during_lead - int(current))
        revenue_at_risk = shortage_units * selling_price
        gross_margin_at_risk = shortage_units * max(0.0, selling_price - cost_price)

        results.append(
            {
                "store_id": item["store_id"],
                "store_name": item["store_name"],
                "product_id": item["product_id"],
                "product_name": item["product_name"],
                "risk": item["risk"],
                "current_stock": int(current),
                "avg_daily_sales": float(avg),
                "lead_time_days": int(lead),
                "expected_demand_during_lead_time": int(expected_demand_during_lead),
                "estimated_shortage_units": int(shortage_units),
                "selling_price": round(selling_price, 2),
                "cost_price": round(cost_price, 2),
                "revenue_at_risk": round(revenue_at_risk, 2),
                "gross_margin_at_risk": round(gross_margin_at_risk, 2),
                "assumption": "Recent demand continues until normal supplier replenishment arrives.",
                "calculation": {
                    "shortage_units": "max(0, ceil(avg_daily_sales * lead_time_days) - current_stock)",
                    "revenue_at_risk": "estimated_shortage_units * selling_price",
                },
                "evidence": item.get("evidence"),
            }
        )

    return sorted(results, key=lambda x: (-x["revenue_at_risk"], x["store_id"], x["product_id"]))
