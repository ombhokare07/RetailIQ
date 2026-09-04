from __future__ import annotations

from backend.analytics.common import (
    AnalyticsContext,
    evidence_sales_ids,
    history_days_for_pair,
    inclusive_window_endpoints,
    safe_float,
    sales_for_pair,
)


def calculate_sales_anomalies(
    context: AnalyticsContext,
    *,
    recent_days: int,
    baseline_days: int,
    minimum_baseline_units: int,
    percentage_change: float,
) -> list[dict]:
    results: list[dict] = []
    required_history = recent_days + baseline_days

    recent_start, recent_end = inclusive_window_endpoints(context.analysis_date, recent_days)
    baseline_start, baseline_end = inclusive_window_endpoints(
        context.analysis_date, baseline_days, offset_days=recent_days
    )

    for row in context.latest_inventory.itertuples(index=False):
        store_id = str(row.store_id)
        product_id = str(row.product_id)
        history_days = history_days_for_pair(
            context.inventory, store_id, product_id, context.analysis_date
        )
        if history_days < required_history:
            continue

        pair_sales = sales_for_pair(context.sales, store_id, product_id)
        recent = pair_sales[
            (pair_sales["date"] >= recent_start) & (pair_sales["date"] <= recent_end)
        ]
        baseline = pair_sales[
            (pair_sales["date"] >= baseline_start) & (pair_sales["date"] <= baseline_end)
        ]

        recent_units = int(recent["units_sold"].sum()) if not recent.empty else 0
        baseline_units = int(baseline["units_sold"].sum()) if not baseline.empty else 0

        if baseline_units < minimum_baseline_units:
            continue

        recent_daily = recent_units / recent_days
        baseline_daily = baseline_units / baseline_days
        if baseline_daily <= 0:
            continue

        change = (recent_daily - baseline_daily) / baseline_daily
        if change >= percentage_change:
            anomaly_type = "spike"
        elif change <= -percentage_change:
            anomaly_type = "drop"
        else:
            continue

        results.append(
            {
                "store_id": store_id,
                "store_name": str(row.store_name),
                "product_id": product_id,
                "product_name": str(row.product_name),
                "category": str(row.category),
                "anomaly_type": anomaly_type,
                "recent_units": recent_units,
                "baseline_units": baseline_units,
                "recent_avg_daily_sales": safe_float(recent_daily),
                "baseline_avg_daily_sales": safe_float(baseline_daily),
                "percentage_change": safe_float(change * 100),
                "reason": (
                    f"Recent daily sales are {abs(change) * 100:.1f}% "
                    f"{'above' if change > 0 else 'below'} the prior baseline."
                ),
                "assumption": (
                    "The immediately preceding baseline window is a reasonable "
                    "reference for recent demand."
                ),
                "thresholds": {
                    "recent_days": recent_days,
                    "baseline_days": baseline_days,
                    "minimum_baseline_units": minimum_baseline_units,
                    "percentage_change": percentage_change,
                },
                "evidence": {
                    "recent_window": {
                        "start": recent_start.strftime("%Y-%m-%d"),
                        "end": recent_end.strftime("%Y-%m-%d"),
                        "sale_ids": evidence_sales_ids(recent, limit=max(recent_days, 10)),
                    },
                    "baseline_window": {
                        "start": baseline_start.strftime("%Y-%m-%d"),
                        "end": baseline_end.strftime("%Y-%m-%d"),
                        "sale_ids": evidence_sales_ids(baseline, limit=max(baseline_days, 30)),
                    },
                },
            }
        )

    return sorted(results, key=lambda x: -abs(x["percentage_change"]))
