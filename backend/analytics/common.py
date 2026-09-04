from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from backend.services.data_service import RetailData


@dataclass(frozen=True)
class AnalyticsContext:
    products: pd.DataFrame
    stores: pd.DataFrame
    sales: pd.DataFrame
    inventory: pd.DataFrame
    latest_inventory: pd.DataFrame
    analysis_date: pd.Timestamp


def build_context(data: RetailData) -> AnalyticsContext:
    products = data.products.copy()
    stores = data.stores.copy()
    sales = data.sales.copy()
    inventory = data.inventory.copy()

    sales["date"] = pd.to_datetime(sales["date"], errors="coerce")
    inventory["date"] = pd.to_datetime(inventory["date"], errors="coerce")

    valid_dates = pd.concat(
        [sales["date"].dropna(), inventory["date"].dropna()], ignore_index=True
    )
    if valid_dates.empty:
        raise ValueError("Retail data contains no valid dates.")

    analysis_date = valid_dates.max().normalize()

    latest_inventory = (
        inventory.sort_values(["store_id", "product_id", "date"])
        .groupby(["store_id", "product_id"], as_index=False)
        .tail(1)
        .copy()
    )

    latest_inventory = latest_inventory.merge(
        products,
        on="product_id",
        how="left",
        validate="many_to_one",
    ).merge(
        stores,
        on="store_id",
        how="left",
        validate="many_to_one",
    )

    return AnalyticsContext(
        products=products,
        stores=stores,
        sales=sales,
        inventory=inventory,
        latest_inventory=latest_inventory,
        analysis_date=analysis_date,
    )


def inclusive_window_endpoints(
    analysis_date: pd.Timestamp, days: int, offset_days: int = 0
) -> tuple[pd.Timestamp, pd.Timestamp]:
    if days <= 0:
        raise ValueError("Window size must be positive.")
    end = analysis_date - pd.Timedelta(days=offset_days)
    start = end - pd.Timedelta(days=days - 1)
    return start, end


def window_sales(
    sales: pd.DataFrame,
    analysis_date: pd.Timestamp,
    days: int,
    *,
    offset_days: int = 0,
) -> pd.DataFrame:
    start, end = inclusive_window_endpoints(analysis_date, days, offset_days)
    return sales[(sales["date"] >= start) & (sales["date"] <= end)].copy()


def history_days_for_pair(
    inventory: pd.DataFrame, store_id: str, product_id: str, analysis_date: pd.Timestamp
) -> int:
    rows = inventory[
        (inventory["store_id"] == store_id)
        & (inventory["product_id"] == product_id)
        & (inventory["date"] <= analysis_date)
    ]
    return int(rows["date"].nunique())


def sales_for_pair(
    sales: pd.DataFrame, store_id: str, product_id: str
) -> pd.DataFrame:
    return sales[
        (sales["store_id"] == store_id) & (sales["product_id"] == product_id)
    ].copy()


def safe_float(value):
    if value is None or pd.isna(value):
        return None
    value = float(value)
    if not np.isfinite(value):
        return None
    return round(value, 4)


def safe_int(value):
    if value is None or pd.isna(value):
        return None
    return int(value)


def evidence_sales_ids(rows: pd.DataFrame, limit: int = 50) -> list[str]:
    if "sale_id" not in rows.columns:
        return []
    return [str(v) for v in rows["sale_id"].dropna().astype(str).tail(limit).tolist()]


def as_records(frame: pd.DataFrame, columns: Iterable[str]) -> list[dict]:
    if frame.empty:
        return []
    available = [c for c in columns if c in frame.columns]
    records = frame[available].copy()
    for col in records.columns:
        if pd.api.types.is_datetime64_any_dtype(records[col]):
            records[col] = records[col].dt.strftime("%Y-%m-%d")
    return records.where(pd.notna(records), None).to_dict(orient="records")
