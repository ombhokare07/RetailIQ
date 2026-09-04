from __future__ import annotations

import math


def round2(value: float) -> float:
    return round(float(value), 2)


def validate_simulation_inputs(
    *,
    current_stock: int | float | None,
    avg_daily_sales: int | float | None,
    lead_time_days: int | float | None,
    horizon_days: int,
    demand_multiplier: float,
    unknown_fields: list[str] | None = None,
) -> list[str]:
    missing = list(unknown_fields or [])
    if current_stock is None:
        missing.append("current_stock")
    if avg_daily_sales is None:
        missing.append("avg_daily_sales")
    if lead_time_days is None:
        missing.append("lead_time_days")
    if horizon_days <= 0:
        missing.append("valid_horizon_days")
    if demand_multiplier <= 0:
        missing.append("positive_demand_multiplier")
    return sorted(set(missing))


def simulate_timed_inflow(
    *,
    current_stock: float,
    avg_daily_sales: float,
    demand_multiplier: float,
    horizon_days: int,
    inflow_units: float,
    inflow_arrival_days: float,
) -> dict:
    """Simulate demand with one deterministic replenishment event.

    Demand is treated as a constant daily rate derived from recent observed sales.
    The inflow arrives after ``inflow_arrival_days``. Shortage that occurs before
    arrival is not retroactively erased by later inventory.
    """
    daily_demand = max(0.0, float(avg_daily_sales) * float(demand_multiplier))
    horizon = float(horizon_days)
    arrival = min(max(0.0, float(inflow_arrival_days)), horizon)
    opening = max(0.0, float(current_stock))
    inflow = max(0.0, float(inflow_units))

    demand_before = daily_demand * arrival
    served_before = min(opening, demand_before)
    shortage_before = max(0.0, demand_before - opening)
    stock_at_arrival = max(0.0, opening - demand_before)

    remaining_days = max(0.0, horizon - arrival)
    demand_after = daily_demand * remaining_days
    stock_after_inflow = stock_at_arrival + inflow
    served_after = min(stock_after_inflow, demand_after)
    shortage_after = max(0.0, demand_after - stock_after_inflow)
    ending_stock = max(0.0, stock_after_inflow - demand_after)

    total_demand = daily_demand * horizon
    served = served_before + served_after
    shortage = shortage_before + shortage_after
    service_level = 1.0 if total_demand <= 0 else max(0.0, min(1.0, served / total_demand))

    first_stockout_day = None
    if daily_demand > 0:
        days_opening_lasts = opening / daily_demand
        if days_opening_lasts < arrival and shortage_before > 0:
            first_stockout_day = days_opening_lasts
        elif shortage_after > 0:
            days_post_arrival_stock_lasts = stock_after_inflow / daily_demand
            first_stockout_day = arrival + days_post_arrival_stock_lasts

    ending_days_cover = None if daily_demand <= 0 else ending_stock / daily_demand

    return {
        "daily_demand": round2(daily_demand),
        "horizon_days": int(horizon_days),
        "inflow_units": int(math.floor(inflow + 1e-9)),
        "inflow_arrival_days": round2(arrival),
        "total_expected_demand": int(math.ceil(total_demand - 1e-9)),
        "served_units": round2(served),
        "unserved_units": int(math.ceil(shortage - 1e-9)),
        "ending_stock": int(math.floor(ending_stock + 1e-9)),
        "ending_days_cover": None if ending_days_cover is None else round2(ending_days_cover),
        "service_level_pct": round2(service_level * 100.0),
        "stockout_occurs": shortage > 1e-9,
        "first_stockout_day": None if first_stockout_day is None else round2(first_stockout_day),
    }
