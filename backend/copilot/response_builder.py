"""Build backward-compatible deterministic Copilot response sections."""

from __future__ import annotations

from typing import Any


def _dedupe(values: list[str], limit: int = 12) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))[:limit]


def _walk_named(payload: Any, names: set[str]) -> list[str]:
    values: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in names:
                if isinstance(value, str):
                    values.append(value)
                elif isinstance(value, list):
                    values.extend(str(item) for item in value if item)
            values.extend(_walk_named(value, names))
    elif isinstance(payload, list):
        for item in payload:
            values.extend(_walk_named(item, names))
    return _dedupe(values)


def findings_for(intent: str, payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    if intent in {"decision_compare", "demand_shock"}:
        return [item for item in payload.get("scenarios", []) if isinstance(item, dict)]
    if intent == "causal_explanation":
        return [item for item in payload.get("anomalies", []) if isinstance(item, dict)]
    if intent == "dashboard_attention":
        issues = payload.get("top_issues", payload.get("attention", []))
        return [item for item in issues if isinstance(item, dict)]
    return [payload]


def recommendation_for(intent: str, payload: Any, status: str) -> dict:
    if status in {"needs_clarification", "not_found", "unsupported"}:
        return {"action": "Clarify the request", "reason": "RetailIQ withheld analysis instead of guessing.", "human_approval_required": False}
    if status == "insufficient_data":
        return {"action": "Complete the missing source data", "reason": "The affected recommendation is withheld because required inputs are unavailable.", "human_approval_required": True}
    if intent in {"decision_compare", "demand_shock"} and isinstance(payload, dict):
        comparison = payload.get("comparison", {})
        return {"action": comparison.get("recommendation") or "No recommendation available", "reason": comparison.get("reason") or "No valid scenarios were available.", "human_approval_required": True}
    if intent == "smart_transfer" and isinstance(payload, list) and payload:
        item = payload[0]
        return {"action": f"Review transfer of {item.get('recommended_transfer_quantity')} units from {item.get('recommended_source_store_name')}", "reason": item.get("reason") or "A deterministic donor-safety check found transferable surplus.", "human_approval_required": True}
    if intent == "stockout_risk" and isinstance(payload, list) and payload:
        item = payload[0]
        quantity = item.get("recommended_reorder_qty")
        if quantity is None:
            return recommendation_for(intent, payload, "insufficient_data")
        if len(payload) > 1:
            return {"action": f"Review the highest-risk positions, starting with {item.get('product_name')}", "reason": "Reorder quantities are deterministic requirements; compare transfer availability before approving purchases.", "human_approval_required": True}
        return {"action": f"Review replenishment options for {item.get('product_name')}", "reason": f"The deterministic reorder requirement is {quantity} units; compare a safe transfer before approving a purchase.", "human_approval_required": True}
    if intent == "overstock":
        return {"action": "Review replenishment holds and redistribution options", "reason": "The deterministic inventory analysis found excess cover.", "human_approval_required": True}
    if intent == "sales_anomalies":
        return {"action": "Investigate the measured sales signal", "reason": "The dataset measures a change but does not establish its cause.", "human_approval_required": False}
    if intent == "causal_explanation":
        return {"action": "Investigate promotions, availability, competitor pricing, weather, and local events", "reason": "These are suggested checks; the available dataset cannot prove causality.", "human_approval_required": False}
    if intent == "dashboard_attention" and isinstance(payload, dict):
        top = payload.get("top_issues", payload.get("attention", []))
        if top:
            return {"action": top[0].get("recommended_action", "Review the highest-priority issue"), "reason": top[0].get("issue", top[0].get("reason", "This issue ranks first under deterministic priority rules.")), "human_approval_required": True}
    return {"action": "Review the deterministic findings", "reason": "RetailIQ provides decision support; the manager remains responsible for business actions.", "human_approval_required": False}


def next_actions_for(intent: str, status: str) -> list[str]:
    if status == "insufficient_data":
        return ["Verify the missing source fields.", "Run the analysis again after the data is complete."]
    if status in {"needs_clarification", "not_found"}:
        return ["Choose a catalog candidate or provide an exact store/product ID."]
    if status == "unsupported":
        return ["Ask about supported retail facts or use a supported demand what-if assumption."]
    return {
        "stockout_risk": ["Review the highest-risk positions first.", "Compare safe transfer and supplier reorder options before approval."],
        "overstock": ["Check replenishment plans.", "Review safe redistribution opportunities."],
        "slow_movers": ["Review replenishment and merchandising plans."],
        "sales_anomalies": ["Verify store availability and promotion history.", "Inspect competitor pricing and local demand events; these checks are not evidence of cause."],
        "smart_transfer": ["Recheck donor inventory before approval.", "Compare transfer cost with the supplier scenario."],
        "decision_compare": ["Review scenario evidence and assumptions.", "Obtain manager approval before a purchase or transfer."],
        "demand_shock": ["Review scenario evidence and assumptions.", "Treat the demand change as a what-if assumption, not a forecast."],
        "causal_explanation": ["Verify promotion history and store availability.", "Check competitor pricing, weather, and local demand events; suggested checks are not claimed causes."],
        "dashboard_attention": ["Review the highest-priority issue first.", "Recheck current inventory before approving an action."],
        "financial_summary": ["Review the underlying product-store exposures and configured logistics assumptions."],
    }.get(intent, [])


def structured_sections(intent: str, payload: Any, status: str, answer: str) -> dict:
    summary = " ".join((answer or "").split("\n\n", 1)[0].splitlines()).strip()
    return {
        "summary": summary,
        "findings": findings_for(intent, payload),
        "recommendation": recommendation_for(intent, payload, status),
        "why": _walk_named(payload, {"reason"}),
        "assumptions": _walk_named(payload, {"assumption", "assumptions", "note"}),
        "next_actions": next_actions_for(intent, status),
    }
