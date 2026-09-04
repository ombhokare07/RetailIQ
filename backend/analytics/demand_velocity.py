from __future__ import annotations

import pandas as pd

from backend.analytics.common import (
    AnalyticsContext,
    evidence_sales_ids,
    history_days_for_pair,
    inclusive_window_endpoints,
    sales_for_pair,
)


def demand_velocity_for_pair(
    context: AnalyticsContext,
    store_id: str,
    product_id: str,
    days: int,
) -> dict:
    history_days = history_days_for_pair(
        context.inventory, store_id, product_id, context.analysis_date
    )
    pair_sales = sales_for_pair(context.sales, store_id, product_id)
    start, end = inclusive_window_endpoints(context.analysis_date, days)
    recent = pair_sales[(pair_sales["date"] >= start) & (pair_sales["date"] <= end)]

    observed_days = min(history_days, days)
    units = int(recent["units_sold"].sum()) if not recent.empty else 0

    if history_days < days:
        average = units / observed_days if observed_days else None
        complete = False
    else:
        average = units / days
        complete = True

    return {
        "window_days": int(days),
        "window_start": start.strftime("%Y-%m-%d"),
        "window_end": end.strftime("%Y-%m-%d"),
        "history_days_available": history_days,
        "observed_days": observed_days,
        "units_sold": units,
        "avg_daily_sales": round(float(average), 4) if average is not None else None,
        "complete_window": complete,
        "sale_ids": evidence_sales_ids(recent, limit=max(days, 10)),
    }
