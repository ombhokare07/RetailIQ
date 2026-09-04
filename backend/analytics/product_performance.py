from __future__ import annotations

from backend.analytics.common import AnalyticsContext, evidence_sales_ids, inclusive_window_endpoints, safe_float


def calculate_product_performance(
    context: AnalyticsContext,
    product_id: str,
    *,
    store_id: str | None = None,
    period_days: int = 30,
) -> dict | None:
    product_rows = context.products[context.products["product_id"] == product_id]
    if product_rows.empty:
        return None
    product = product_rows.iloc[0]

    if store_id is not None and context.stores[context.stores["store_id"] == store_id].empty:
        return None

    sales = context.sales[context.sales["product_id"] == product_id]
    inventory = context.latest_inventory[context.latest_inventory["product_id"] == product_id]
    if store_id:
        sales = sales[sales["store_id"] == store_id]
        inventory = inventory[inventory["store_id"] == store_id]

    current_start, current_end = inclusive_window_endpoints(context.analysis_date, period_days)
    previous_start, previous_end = inclusive_window_endpoints(
        context.analysis_date, period_days, offset_days=period_days
    )

    current = sales[(sales["date"] >= current_start) & (sales["date"] <= current_end)]
    previous = sales[(sales["date"] >= previous_start) & (sales["date"] <= previous_end)]

    current_units = int(current["units_sold"].sum()) if not current.empty else 0
    previous_units = int(previous["units_sold"].sum()) if not previous.empty else 0
    current_revenue = float(current["revenue"].sum()) if not current.empty else 0.0
    previous_revenue = float(previous["revenue"].sum()) if not previous.empty else 0.0

    units_change = (
        ((current_units - previous_units) / previous_units) * 100
        if previous_units > 0
        else None
    )
    revenue_change = (
        ((current_revenue - previous_revenue) / previous_revenue) * 100
        if previous_revenue > 0
        else None
    )

    available_history_days = int(
        context.inventory[context.inventory["product_id"] == product_id]["date"].nunique()
    )
    if store_id:
        available_history_days = int(
            context.inventory[
                (context.inventory["product_id"] == product_id)
                & (context.inventory["store_id"] == store_id)
            ]["date"].nunique()
        )

    comparison_complete = available_history_days >= period_days * 2
    if not comparison_complete:
        units_change = None
        revenue_change = None

    return {
        "product_id": product_id,
        "product_name": str(product["product_name"]),
        "category": str(product["category"]),
        "store_id": store_id,
        "analysis_date": context.analysis_date.strftime("%Y-%m-%d"),
        "period": {
            "days": period_days,
            "start": current_start.strftime("%Y-%m-%d"),
            "end": current_end.strftime("%Y-%m-%d"),
        },
        "current": {
            "units_sold": current_units,
            "revenue": round(current_revenue, 2),
            "avg_units_per_day": safe_float(current_units / period_days),
            "current_stock": int(inventory["current_stock"].sum()) if not inventory.empty else None,
        },
        "previous_period": {
            "start": previous_start.strftime("%Y-%m-%d"),
            "end": previous_end.strftime("%Y-%m-%d"),
            "units_sold": previous_units,
            "revenue": round(previous_revenue, 2),
        },
        "change": {
            "units_percent": safe_float(units_change),
            "revenue_percent": safe_float(revenue_change),
        },
        "data_quality": {
            "history_days_available": available_history_days,
            "comparison_complete": comparison_complete,
            "note": (
                None
                if comparison_complete
                else "Less than two complete comparison periods are available; percentage comparisons may be withheld."
            ),
        },
        "evidence": {
            "current_sale_ids": evidence_sales_ids(current, limit=50),
            "previous_sale_ids": evidence_sales_ids(previous, limit=50),
            "inventory_ids": [str(v) for v in inventory["inventory_id"].astype(str).tolist()],
        },
    }
