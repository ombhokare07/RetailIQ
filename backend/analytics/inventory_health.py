from __future__ import annotations


def calculate_inventory_health(
    stockout_items: list[dict],
    overstock_items: list[dict],
    slow_movers: list[dict],
) -> list[dict]:
    """Create a transparent 0-100 inventory health score per store/product.

    This score is deliberately rule-based and explainable. It is not produced by
    an LLM or opaque ML model.
    """

    keys = {
        (item["store_id"], item["product_id"]): item for item in stockout_items
    }
    over_map = {(i["store_id"], i["product_id"]): i for i in overstock_items}
    slow_map = {(i["store_id"], i["product_id"]): i for i in slow_movers}

    results: list[dict] = []
    for key, stock in keys.items():
        if stock["risk"] == "unknown":
            results.append(
                {
                    "store_id": stock["store_id"],
                    "store_name": stock["store_name"],
                    "product_id": stock["product_id"],
                    "product_name": stock["product_name"],
                    "score": None,
                    "status": "unknown",
                    "reason": "Health score withheld because required source data is incomplete.",
                    "components": {"stockout": "unknown"},
                }
            )
            continue

        score = 100
        penalties: list[dict] = []

        stockout_penalty = {
            "critical": 50,
            "high": 30,
            "watch": 15,
            "low": 0,
            "none": 0,
        }.get(stock["risk"], 0)
        if stockout_penalty:
            score -= stockout_penalty
            penalties.append({"reason": f"stockout_{stock['risk']}", "points": stockout_penalty})

        over = over_map.get(key)
        if over:
            over_penalty = {"severe": 45, "overstock": 30, "unknown": 0}.get(
                over["severity"], 0
            )
            if over_penalty:
                score -= over_penalty
                penalties.append({"reason": f"overstock_{over['severity']}", "points": over_penalty})

        slow = slow_map.get(key)
        if slow:
            slow_penalty = 25 if slow["movement"] == "zero_sales" else 20
            score -= slow_penalty
            penalties.append({"reason": slow["movement"], "points": slow_penalty})

        score = max(0, min(100, score))
        if score >= 80:
            status = "healthy"
        elif score >= 60:
            status = "watch"
        elif score >= 40:
            status = "poor"
        else:
            status = "critical"

        results.append(
            {
                "store_id": stock["store_id"],
                "store_name": stock["store_name"],
                "product_id": stock["product_id"],
                "product_name": stock["product_name"],
                "score": score,
                "status": status,
                "penalties": penalties,
                "components": {
                    "stockout_risk": stock["risk"],
                    "overstock": over["severity"] if over else "none",
                    "movement": slow["movement"] if slow else "normal",
                },
                "calculation": "100 minus transparent rule penalties; clamped to 0-100",
            }
        )

    return sorted(
        results,
        key=lambda x: (x["score"] is None, x["score"] if x["score"] is not None else 999),
    )
