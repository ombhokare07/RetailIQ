"""Build reviewable actions from existing deterministic service results."""

from __future__ import annotations


def pair(item: dict) -> tuple[str, str]:
    return item.get("store_id", item.get("recipient_store_id")), item["product_id"]


def _metrics(source: dict, names: tuple[str, ...]) -> dict:
    return {name: source.get(name) for name in names}


def _action(item: dict, category: str, severity: str, issue: str, text: str, action: str) -> dict:
    return {
        "action_id": f"ACT-{item['store_id']}-{item['product_id']}-{category}",
        "category": category,
        "categories": [category],
        "severity": severity,
        "store_id": item["store_id"],
        "store_name": item["store_name"],
        "product_id": item["product_id"],
        "product_name": item["product_name"],
        "store": {"id": item["store_id"], "name": item["store_name"]},
        "product": {"id": item["product_id"], "name": item["product_name"]},
        "issue": issue,
        "recommended_action": text,
        "recommendation": {"action": action, "quantity": None, "human_approval_required": True},
        "why": [item["reason"]],
        "key_metrics": {},
        "evidence": {},
        "supporting_facts": {},
        "assumptions": [],
        "unknowns": list(item.get("unknown_fields", [])),
        "human_approval_required": True,
    }


def _support(action: dict, name: str, fact: dict | None) -> None:
    if fact is None:
        return
    action["supporting_facts"][name] = fact
    action["evidence"][name] = fact.get("evidence", {})
    assumptions = fact.get("assumptions", []) + ([fact["assumption"]] if fact.get("assumption") else [])
    for value in assumptions:
        if value not in action["assumptions"]:
            action["assumptions"].append(value)


def build_actions(stockout: list[dict], overstock: list[dict], anomalies: list[dict],
                  transfers: list[dict], revenue_risk: list[dict], capital: list[dict],
                  benefits: list[dict]) -> list[dict]:
    transfer_map = {pair(item): item for item in transfers}
    revenue_map = {pair(item): item for item in revenue_risk}
    capital_map = {pair(item): item for item in capital}
    benefit_map = {pair(item): item for item in benefits}
    actions = []
    missing = {}
    for item in stockout:
        risk = item["risk"]
        if risk == "unknown":
            missing[pair(item)] = [("stockout", item)]
            continue
        if risk not in {"critical", "high", "watch"}:
            continue
        category = {"critical": "critical_stockout", "high": "high_stockout", "watch": "reorder_watch"}[risk]
        quantity = item["recommended_reorder_qty"]
        text = (f"Review a supplier reorder of {quantity} units and compare available scenarios."
                if quantity else "Review the reorder threshold and monitor demand; no additional quantity is recommended.")
        result = _action(item, category, risk, f"{risk.title()} stockout attention", text,
                         "review_reorder" if quantity else "review_inventory")
        result["recommendation"]["quantity"] = quantity
        result["key_metrics"] = _metrics(item, (
            "current_stock", "avg_daily_sales", "days_cover", "lead_time_days", "reorder_level", "recommended_reorder_qty"))
        _support(result, "stockout", item)
        revenue = revenue_map.get(pair(item))
        if revenue:
            result["key_metrics"].update(_metrics(revenue, ("revenue_at_risk", "gross_margin_at_risk", "estimated_shortage_units")))
            _support(result, "revenue_risk", revenue)
        transfer = transfer_map.get(pair(item))
        if transfer:
            quantity = transfer["recommended_transfer_quantity"]
            result["categories"].append("safe_transfer")
            result["recommended_action"] = (
                f"Review a transfer of {quantity} units from {transfer['recommended_source_store_name']}; "
                "compare transfer and supplier scenarios before approval."
            )
            result["recommendation"].update({
                "action": "review_transfer", "quantity": quantity,
                "source_store_id": transfer["recommended_source_store_id"],
                "source_store_name": transfer["recommended_source_store_name"],
            })
            result["why"].append(transfer["reason"])
            result["key_metrics"].update(_metrics(transfer, (
                "recommended_transfer_quantity", "donor_after_days_cover", "recipient_after_days_cover", "estimated_transfer_cost")))
            _support(result, "transfer", transfer)
            benefit = benefit_map.get(pair(item))
            if benefit:
                result["key_metrics"].update(_metrics(benefit, (
                    "revenue_protected", "near_term_cash_purchase_deferred", "estimated_net_operational_benefit")))
                _support(result, "transfer_benefit", benefit)
        actions.append(result)

    for item in overstock:
        severity = item["severity"]
        if severity == "unknown":
            missing.setdefault(pair(item), []).append(("overstock", item))
            continue
        if severity not in {"severe", "overstock"}:
            continue
        category = "severe_overstock" if severity == "severe" else "overstock"
        result = _action(item, category, severity, "Excess inventory ties up capital",
                         "Review replenishment holds and redistribution opportunities; verify local demand before changing orders.",
                         "review_excess_inventory")
        result["key_metrics"] = _metrics(item, ("current_stock", "avg_daily_sales", "days_cover"))
        _support(result, "overstock", item)
        value = capital_map.get(pair(item))
        if value:
            result["key_metrics"].update(_metrics(value, ("blocked_capital_at_cost", "estimated_excess_units", "allowed_days_cover")))
            _support(result, "overstock_capital", value)
        actions.append(result)

    for item in anomalies:
        anomaly = item["anomaly_type"]
        if anomaly not in {"drop", "spike"}:
            continue
        result = _action(item, f"sales_{anomaly}", anomaly, f"Measured sales {anomaly}",
                         "Investigate availability, promotion history, competitor pricing, and local demand events; these are checks, not established causes.",
                         "investigate_sales_signal")
        result["key_metrics"] = _metrics(item, ("recent_avg_daily_sales", "baseline_avg_daily_sales", "percentage_change", "recent_units", "baseline_units"))
        result["unknowns"] = ["Causality cannot be established: promotion history, competitor prices, weather, and customer behaviour are unavailable."]
        _support(result, "sales_anomaly", item)
        actions.append(result)

    for entries in missing.values():
        item = entries[0][1]
        fields = sorted({field for _, entry in entries for field in entry.get("unknown_fields", [])})
        result = _action(item, "missing_data", "unknown", "Required analysis data is incomplete",
                         "Verify the missing source fields or history before requesting an affected recommendation.", "complete_source_data")
        result["unknowns"] = fields
        result["missing_fields"] = fields
        result["key_metrics"] = _metrics(item, ("current_stock", "avg_daily_sales", "days_cover"))
        result["key_metrics"]["recommended_reorder_qty"] = None
        result["recommendation"]["withheld"] = True
        for name, source in entries:
            _support(result, name, source)
        actions.append(result)
    return actions
