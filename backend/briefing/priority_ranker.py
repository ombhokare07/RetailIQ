"""Public, deterministic manager-attention policy; see docs/priority_rules.md."""

from __future__ import annotations

from copy import deepcopy


PRIORITY_SCORES = {
    "critical_stockout": 100,
    "high_stockout": 80,
    "severe_overstock": 60,
    "reorder_watch": 50,
    "overstock": 40,
    "sales_drop": 30,
    "sales_spike": 20,
    "missing_data": 10,
}

PRIORITY_RULES = {
    "version": "1.0",
    "method": "Fixed business-rule weights; this is not a probability or AI confidence score.",
    "category_scores": PRIORITY_SCORES,
    "tie_breakers": [
        "Higher category score first.",
        "For replenishment, lower known days of cover first; unknown cover last.",
        "Higher known revenue at risk or blocked capital first; unavailable exposure last.",
        "Larger absolute measured sales change first.",
        "Store ID, product ID, and category ascending for stable final ties.",
    ],
    "deduplication": "Safe transfer and revenue exposure enrich the stockout action rather than create duplicate inventory tasks.",
    "scope": "Filter store/product before assigning ordinal priorities; limit never changes totals.",
    "unknown_policy": "Missing-data tasks remain visible and recommendations using missing controls are withheld.",
}


def priority_sort_key(item: dict) -> tuple:
    metrics = item["key_metrics"]
    cover = metrics.get("days_cover")
    if item["category"] not in {"critical_stockout", "high_stockout", "reorder_watch"}:
        cover = None
    exposure = metrics.get("revenue_at_risk", metrics.get("blocked_capital_at_cost"))
    change = metrics.get("percentage_change")
    return (
        -PRIORITY_SCORES[item["category"]],
        float(cover) if cover is not None else float("inf"),
        -float(exposure) if exposure is not None else float("inf"),
        -abs(float(change)) if change is not None else 0,
        item["store_id"],
        item["product_id"],
        item["category"],
    )


def rank_actions(items: list[dict]) -> list[dict]:
    ranked = sorted(deepcopy(items), key=priority_sort_key)
    for rank, item in enumerate(ranked, start=1):
        item["priority"] = rank
        item["priority_score"] = PRIORITY_SCORES[item["category"]]
    return ranked
