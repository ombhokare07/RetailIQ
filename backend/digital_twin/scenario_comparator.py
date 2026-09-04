from __future__ import annotations


def _rank_key(item: dict) -> tuple:
    """Service protection dominates economics; ties prefer lower operating loss."""
    return (
        int(item.get("unserved_units", 10**9)),
        1 if item.get("stockout_occurs") else 0,
        float(item.get("estimated_operational_loss", 10**12)),
        float(item.get("execution_cost", 10**12)),
        float(item.get("cash_committed", 10**12)),
        str(item.get("scenario_id", "")),
    )


def compare_scenarios(scenarios: list[dict]) -> dict:
    if not scenarios:
        return {
            "recommended_scenario_id": None,
            "recommendation": None,
            "ranking": [],
            "reason": "No valid scenarios were available for comparison.",
        }

    ranked = sorted(scenarios, key=_rank_key)
    best = ranked[0]
    ranking = [
        {
            "rank": idx + 1,
            "scenario_id": item["scenario_id"],
            "label": item["label"],
            "unserved_units": item["unserved_units"],
            "service_level_pct": item["service_level_pct"],
            "estimated_operational_loss": item["estimated_operational_loss"],
            "execution_cost": item["execution_cost"],
            "cash_committed": item["cash_committed"],
        }
        for idx, item in enumerate(ranked)
    ]
    return {
        "recommended_scenario_id": best["scenario_id"],
        "recommendation": best["label"],
        "ranking": ranking,
        "reason": (
            "RetailIQ first minimizes expected unserved demand and stockout exposure, then compares "
            "estimated operating loss, execution cost, and cash commitment. The ranking is deterministic."
        ),
        "human_decision_note": (
            "This is a decision-support recommendation. A store manager remains responsible for approving purchases or transfers."
        ),
    }
