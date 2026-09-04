from __future__ import annotations

import pandas as pd

from backend.analytics.common import AnalyticsContext, safe_float
from backend.analytics.demand_velocity import demand_velocity_for_pair


def calculate_overstock(
    context: AnalyticsContext,
    *,
    lookback_days: int,
    overstock_days: float,
    severe_days: float,
) -> list[dict]:
    results: list[dict] = []

    for row in context.latest_inventory.itertuples(index=False):
        velocity = demand_velocity_for_pair(
            context, str(row.store_id), str(row.product_id), lookback_days
        )
        current_stock = int(row.current_stock)
        avg = velocity["avg_daily_sales"]

        if not velocity["complete_window"]:
            severity = "unknown"
            days_cover = None
            reason = "Insufficient history for overstock analysis."
            unknown_fields = ["sales_history"]
        elif avg is None or avg <= 0:
            severity = "severe" if current_stock > 0 else "none"
            days_cover = None
            reason = (
                "No units sold in the analysis window while stock remains on hand."
                if current_stock > 0
                else "No stock on hand."
            )
            unknown_fields = []
        else:
            days_cover = current_stock / avg
            unknown_fields = []
            if days_cover > severe_days:
                severity = "severe"
                reason = "Inventory cover exceeds the severe overstock threshold."
            elif days_cover > overstock_days:
                severity = "overstock"
                reason = "Inventory cover exceeds the overstock threshold."
            else:
                severity = "none"
                reason = "Inventory cover is within the configured overstock threshold."

        if severity in {"overstock", "severe", "unknown"}:
            results.append(
                {
                    "store_id": str(row.store_id),
                    "store_name": str(row.store_name),
                    "product_id": str(row.product_id),
                    "product_name": str(row.product_name),
                    "category": str(row.category),
                    "current_stock": current_stock,
                    "avg_daily_sales": safe_float(avg),
                    "days_cover": safe_float(days_cover),
                    "severity": severity,
                    "reason": reason,
                    "unknown_fields": unknown_fields,
                    "assumption": (
                        f"Recent {lookback_days}-day demand continues."
                        if velocity["complete_window"]
                        else None
                    ),
                    "thresholds": {
                        "overstock_days": overstock_days,
                        "severe_days": severe_days,
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

    rank = {"severe": 0, "overstock": 1, "unknown": 2}
    return sorted(
        results,
        key=lambda x: (
            rank.get(x["severity"], 9),
            -(x["days_cover"] or 0),
            x["store_id"],
            x["product_id"],
        ),
    )
