from __future__ import annotations


def summarize_blocked_capital(items: list[dict]) -> dict:
    return {
        "products": len(items),
        "blocked_capital_at_cost": round(sum(float(i.get("blocked_capital_at_cost", 0)) for i in items), 2),
        "retail_value_of_excess": round(sum(float(i.get("retail_value_of_excess", 0)) for i in items), 2),
    }
