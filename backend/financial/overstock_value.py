from __future__ import annotations

import math


def calculate_overstock_value(
    context,
    overstock_items: list[dict],
    *,
    allowed_days_cover: float,
) -> list[dict]:
    product_lookup = {
        str(row.product_id): row for row in context.products.itertuples(index=False)
    }
    results: list[dict] = []

    for item in overstock_items:
        if item.get("severity") not in {"overstock", "severe"}:
            continue
        product = product_lookup.get(str(item["product_id"]))
        cost_price = float(getattr(product, "cost_price", 0.0) or 0.0)
        selling_price = float(getattr(product, "selling_price", 0.0) or 0.0)
        current_stock = int(item.get("current_stock") or 0)
        avg = item.get("avg_daily_sales")

        if avg is None or avg <= 0:
            allowed_units = 0
            excess_units = current_stock
            formula_note = "No demand was observed, so all on-hand stock is treated as excess for this estimate."
        else:
            allowed_units = math.ceil(float(avg) * float(allowed_days_cover))
            excess_units = max(0, current_stock - allowed_units)
            formula_note = "Excess stock is inventory above the configured allowed days of cover."

        results.append(
            {
                "store_id": item["store_id"],
                "store_name": item["store_name"],
                "product_id": item["product_id"],
                "product_name": item["product_name"],
                "severity": item["severity"],
                "current_stock": current_stock,
                "avg_daily_sales": avg,
                "allowed_days_cover": float(allowed_days_cover),
                "allowed_units": int(allowed_units),
                "estimated_excess_units": int(excess_units),
                "cost_price": round(cost_price, 2),
                "selling_price": round(selling_price, 2),
                "blocked_capital_at_cost": round(excess_units * cost_price, 2),
                "retail_value_of_excess": round(excess_units * selling_price, 2),
                "assumption": formula_note,
                "calculation": {
                    "allowed_units": "ceil(avg_daily_sales * allowed_days_cover)",
                    "blocked_capital": "estimated_excess_units * cost_price",
                },
                "evidence": item.get("evidence"),
            }
        )

    return sorted(results, key=lambda x: (-x["blocked_capital_at_cost"], x["store_id"], x["product_id"]))
