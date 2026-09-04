from __future__ import annotations

from backend.analytics.common import AnalyticsContext, evidence_sales_ids, inclusive_window_endpoints, safe_float


def calculate_store_performance(
    context: AnalyticsContext,
    store_id: str,
    *,
    period_days: int = 30,
) -> dict | None:
    store_rows = context.stores[context.stores["store_id"] == store_id]
    if store_rows.empty:
        return None
    store = store_rows.iloc[0]

    sales = context.sales[context.sales["store_id"] == store_id]
    inventory = context.latest_inventory[context.latest_inventory["store_id"] == store_id]

    current_start, current_end = inclusive_window_endpoints(context.analysis_date, period_days)
    previous_start, previous_end = inclusive_window_endpoints(
        context.analysis_date, period_days, offset_days=period_days
    )
    current = sales[(sales["date"] >= current_start) & (sales["date"] <= current_end)]
    previous = sales[(sales["date"] >= previous_start) & (sales["date"] <= previous_end)]

    current_units = int(current["units_sold"].sum())
    previous_units = int(previous["units_sold"].sum())
    current_revenue = float(current["revenue"].sum())
    previous_revenue = float(previous["revenue"].sum())

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

    active_products = int(current.loc[current["units_sold"] > 0, "product_id"].nunique())

    product_summary = (
        current.groupby("product_id", as_index=False)
        .agg(units_sold=("units_sold", "sum"), revenue=("revenue", "sum"))
        .sort_values(["revenue", "units_sold"], ascending=False)
        .head(5)
        .merge(context.products[["product_id", "product_name"]], on="product_id", how="left")
    )

    return {
        "store_id": store_id,
        "store_name": str(store["store_name"]),
        "city": str(store["city"]),
        "analysis_date": context.analysis_date.strftime("%Y-%m-%d"),
        "period": {
            "days": period_days,
            "start": current_start.strftime("%Y-%m-%d"),
            "end": current_end.strftime("%Y-%m-%d"),
        },
        "current": {
            "units_sold": current_units,
            "revenue": round(current_revenue, 2),
            "active_products": active_products,
            "current_stock_units": int(inventory["current_stock"].sum()),
        },
        "previous_period": {
            "units_sold": previous_units,
            "revenue": round(previous_revenue, 2),
        },
        "change": {
            "units_percent": safe_float(units_change),
            "revenue_percent": safe_float(revenue_change),
        },
        "top_products": [
            {
                "product_id": str(row.product_id),
                "product_name": str(row.product_name),
                "units_sold": int(row.units_sold),
                "revenue": round(float(row.revenue), 2),
            }
            for row in product_summary.itertuples(index=False)
        ],
        "evidence": {
            "current_sale_ids": evidence_sales_ids(current, limit=50),
            "previous_sale_ids": evidence_sales_ids(previous, limit=50),
            "latest_inventory_ids": [str(v) for v in inventory["inventory_id"].astype(str).tolist()],
        },
    }
