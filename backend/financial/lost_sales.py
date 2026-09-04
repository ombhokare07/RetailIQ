from __future__ import annotations


def estimate_lost_sales_units(*, avg_daily_sales: float, current_stock: int, horizon_days: int) -> int:
    expected_units = max(0, int(round(float(avg_daily_sales) * int(horizon_days))))
    return max(0, expected_units - int(current_stock))
