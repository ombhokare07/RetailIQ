from __future__ import annotations

import math

import pandas as pd

from backend.analytics.common import AnalyticsContext, safe_float, safe_int
from backend.analytics.demand_velocity import demand_velocity_for_pair


def _risk_level(
    days_cover: float | None,
    lead_time_days: int | None,
    reorder_level: float | None,
    current_stock: int,
    critical_days_cover: float,
    high_days_cover: float,
) -> tuple[str, str]:
    if days_cover is None:
        return "none", "No recent demand means a stockout horizon cannot be estimated."

    if lead_time_days is not None and days_cover <= lead_time_days:
        return "critical", "Inventory cover is at or below supplier lead time."
    if days_cover <= critical_days_cover:
        return "critical", "Inventory cover is below the configured critical threshold."
    if days_cover <= high_days_cover:
        return "high", "Inventory cover is below the configured high-risk threshold."
    if reorder_level is not None and current_stock <= reorder_level:
        return "watch", "Current stock is at or below the configured reorder level."
    return "low", "Inventory cover is above the configured risk thresholds."


def calculate_stockout_risk(
    context: AnalyticsContext,
    *,
    recent_sales_days: int,
    target_inventory_days: int,
    critical_days_cover: float,
    high_days_cover: float,
) -> list[dict]:
    results: list[dict] = []

    for row in context.latest_inventory.itertuples(index=False):
        velocity = demand_velocity_for_pair(
            context, str(row.store_id), str(row.product_id), recent_sales_days
        )
        avg_daily_sales = velocity["avg_daily_sales"]
        current_stock = int(row.current_stock)
        lead_time_days = safe_int(row.lead_time_days)
        reorder_level = safe_float(row.reorder_level)
        unknown_fields: list[str] = []

        if not velocity["complete_window"]:
            results.append(
                {
                    "store_id": str(row.store_id),
                    "store_name": str(row.store_name),
                    "city": str(row.city),
                    "product_id": str(row.product_id),
                    "product_name": str(row.product_name),
                    "category": str(row.category),
                    "current_stock": current_stock,
                    "reorder_level": reorder_level,
                    "lead_time_days": lead_time_days,
                    "avg_daily_sales": avg_daily_sales,
                    "days_cover": None,
                    "risk": "unknown",
                    "recommended_reorder_qty": None,
                    "reason": "Insufficient history for the configured recent-sales window.",
                    "unknown_fields": ["recent_sales_history"],
                    "assumption": None,
                    "evidence": {
                        "inventory_id": str(row.inventory_id),
                        "inventory_date": pd.Timestamp(row.date).strftime("%Y-%m-%d"),
                        "sales_window": {
                            "start": velocity["window_start"],
                            "end": velocity["window_end"],
                            "sale_ids": velocity["sale_ids"],
                        },
                    },
                }
            )
            continue

        if pd.isna(row.reorder_level):
            unknown_fields.append("reorder_level")

        if avg_daily_sales is None or avg_daily_sales <= 0:
            days_cover = None
            reorder_qty = 0
        else:
            days_cover = current_stock / avg_daily_sales
            reorder_qty = max(
                0, math.ceil((avg_daily_sales * target_inventory_days) - current_stock)
            )

        risk, reason = _risk_level(
            days_cover,
            lead_time_days,
            reorder_level,
            current_stock,
            critical_days_cover,
            high_days_cover,
        )

        # Missing a business control used for a recommendation means we expose
        # the metric but refuse to make a final risk/reorder recommendation.
        if unknown_fields:
            risk = "unknown"
            reorder_qty = None
            reason = (
                "A required inventory control is missing, so RetailIQ will not "
                "finalize the stockout recommendation."
            )

        results.append(
            {
                "store_id": str(row.store_id),
                "store_name": str(row.store_name),
                "city": str(row.city),
                "product_id": str(row.product_id),
                "product_name": str(row.product_name),
                "category": str(row.category),
                "current_stock": current_stock,
                "reorder_level": reorder_level,
                "lead_time_days": lead_time_days,
                "avg_daily_sales": safe_float(avg_daily_sales),
                "days_cover": safe_float(days_cover),
                "risk": risk,
                "recommended_reorder_qty": safe_int(reorder_qty),
                "reason": reason,
                "unknown_fields": unknown_fields,
                "assumption": (
                    f"Recent {recent_sales_days}-day average demand continues and "
                    f"the target inventory horizon is {target_inventory_days} days."
                    if avg_daily_sales and not unknown_fields
                    else None
                ),
                "calculation": {
                    "days_cover_formula": "current_stock / avg_daily_sales",
                    "reorder_formula": "max(0, ceil(avg_daily_sales * target_inventory_days - current_stock))",
                },
                "evidence": {
                    "inventory_id": str(row.inventory_id),
                    "inventory_date": pd.Timestamp(row.date).strftime("%Y-%m-%d"),
                    "sales_window": {
                        "start": velocity["window_start"],
                        "end": velocity["window_end"],
                        "units_sold": velocity["units_sold"],
                        "sale_ids": velocity["sale_ids"],
                    },
                },
            }
        )

    rank = {"critical": 0, "high": 1, "watch": 2, "unknown": 3, "low": 4, "none": 5}
    return sorted(
        results,
        key=lambda x: (
            rank.get(x["risk"], 99),
            x["days_cover"] if x["days_cover"] is not None else float("inf"),
            x["store_id"],
            x["product_id"],
        ),
    )
