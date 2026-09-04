from __future__ import annotations

import pandas as pd

from backend.analytics.common import AnalyticsContext, safe_float
from backend.analytics.demand_velocity import demand_velocity_for_pair


def calculate_slow_movers(
    context: AnalyticsContext,
    *,
    lookback_days: int,
    max_units_sold: int,
) -> list[dict]:
    results: list[dict] = []

    for row in context.latest_inventory.itertuples(index=False):
        velocity = demand_velocity_for_pair(
            context, str(row.store_id), str(row.product_id), lookback_days
        )

        if not velocity["complete_window"]:
            continue

        units = int(velocity["units_sold"])
        current_stock = int(row.current_stock)
        if current_stock <= 0 or units > max_units_sold:
            continue

        avg = velocity["avg_daily_sales"] or 0.0
        days_cover = (current_stock / avg) if avg > 0 else None
        movement = "zero_sales" if units == 0 else "slow_moving"

        results.append(
            {
                "store_id": str(row.store_id),
                "store_name": str(row.store_name),
                "product_id": str(row.product_id),
                "product_name": str(row.product_name),
                "category": str(row.category),
                "current_stock": current_stock,
                "units_sold": units,
                "avg_daily_sales": safe_float(avg),
                "days_cover": safe_float(days_cover),
                "movement": movement,
                "reason": (
                    f"Only {units} unit(s) sold in the last {lookback_days} days "
                    f"while {current_stock} unit(s) remain in stock."
                ),
                "assumption": f"Slow-moving threshold is <= {max_units_sold} units over {lookback_days} days.",
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

    return sorted(
        results,
        key=lambda x: (
            0 if x["movement"] == "zero_sales" else 1,
            x["units_sold"],
            -x["current_stock"],
        ),
    )
