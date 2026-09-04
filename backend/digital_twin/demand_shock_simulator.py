from __future__ import annotations


def build_demand_shock_summary(
    *,
    baseline_avg_daily_sales: float,
    demand_multiplier: float,
    horizon_days: int,
) -> dict:
    shocked = float(baseline_avg_daily_sales) * float(demand_multiplier)
    return {
        "baseline_avg_daily_sales": round(float(baseline_avg_daily_sales), 2),
        "demand_multiplier": round(float(demand_multiplier), 2),
        "simulated_avg_daily_sales": round(shocked, 2),
        "horizon_days": int(horizon_days),
        "demand_change_pct": round((float(demand_multiplier) - 1.0) * 100.0, 2),
        "note": "This is a what-if assumption, not a forecast claim.",
    }
