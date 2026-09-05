"""Manager briefing over an injected, immutable deterministic dataset snapshot."""

from __future__ import annotations

from copy import deepcopy

from backend.analytics.common import inclusive_window_endpoints
from backend.briefing.briefing_builder import build_actions
from backend.briefing.priority_ranker import PRIORITY_RULES, rank_actions
from backend.core.config import SETTINGS
from backend.financial.blocked_capital import summarize_blocked_capital
from backend.services.analytics_service import AnalyticsService
from backend.services.decision_service import DecisionService


ASSUMPTIONS = [
    "Analysis date is the latest date in the selected local dataset, not a live feed or today's calendar date.",
    "Demand and inventory estimates use the existing configured deterministic analysis windows and thresholds.",
    "Financial values are scenario estimates; logistics costs are configured assumptions, not live quotes.",
    "Transfer opportunities are independent proposals, not a jointly allocated plan; recheck donor stock before each approval.",
    "Purchase cash deferred is not permanent savings and must not be added to revenue protected as profit.",
    "Missing inputs are disclosed and excluded from affected recommendations and financial estimates, not treated as zero exposure.",
    "All proposed business actions require human review and approval; this service executes no purchases or transfers.",
]


def _sum(items: list[dict], key: str) -> float:
    return round(sum(float(item[key]) for item in items if item.get(key) is not None), 2)


def _counts(items: list[dict], field: str, levels: tuple[str, ...]) -> dict:
    return {level: sum(item.get(field) == level for item in items) for level in levels}


def _trace(tool: str) -> dict:
    return {"route": "manager_briefing", "tool": tool, "deterministic": True,
            "gemini_used": False, "human_approval_required": True}


class ManagerBriefingService:
    """No model, network calls, dataset mutation, or process-global briefing cache."""

    def __init__(self, analytics: AnalyticsService | None = None, decisions: DecisionService | None = None):
        if analytics is not None and decisions is not None and decisions.analytics is not analytics:
            raise ValueError("Manager briefing requires analytics and decisions from the same dataset snapshot.")
        self.decisions = decisions or DecisionService(analytics)
        self.analytics = self.decisions.analytics

    @property
    def context(self):
        return self.analytics.context

    @property
    def analysis_date(self) -> str:
        return self.context.analysis_date.strftime("%Y-%m-%d")

    def _validate_scope(self, store_id: str | None, product_id: str | None) -> None:
        if store_id and store_id not in set(self.context.stores["store_id"].astype(str)):
            raise ValueError(f"Store {store_id} was not found in the selected dataset.")
        if product_id and product_id not in set(self.context.products["product_id"].astype(str)):
            raise ValueError(f"Product {product_id} was not found in the selected dataset.")

    def _facts(self, store_id: str | None, product_id: str | None) -> dict:
        self._validate_scope(store_id, product_id)
        scope = {"store_id": store_id, "product_id": product_id}
        return {
            "stockout": self.analytics.stockout(**scope),
            "overstock": self.analytics.overstock(**scope),
            "anomalies": self.analytics.anomalies(**scope),
            "transfers": self.decisions.transfer_recommendations(**scope),
            "revenue_risk": self.decisions.revenue_risk(**scope),
            "capital": self.decisions.overstock_capital(**scope),
            "benefits": self.decisions.transfer_benefits(**scope),
        }

    @staticmethod
    def _warnings(actions: list[dict]) -> list[dict]:
        return [{
            "store_id": action["store_id"], "store_name": action["store_name"],
            "product_id": action["product_id"], "product_name": action["product_name"],
            "missing_fields": action["missing_fields"], "evidence": action["evidence"],
            "known_metrics": action["key_metrics"], "recommendation_withheld": True,
        } for action in actions if action["category"] == "missing_data"]

    @staticmethod
    def _unknowns(warnings: list[dict]) -> list[str]:
        return [f"{item['product_name']} at {item['store_name']}: {', '.join(item['missing_fields'])}."
                for item in warnings]

    def priority_actions(self, store_id: str | None = None, product_id: str | None = None,
                         limit: int | None = 20) -> dict:
        facts = self._facts(store_id, product_id)
        ranked = rank_actions(build_actions(**facts))
        items = ranked if limit is None else ranked[:max(0, limit)]
        warnings = self._warnings(ranked)
        return {
            "status": "ok", "analysis_date": self.analysis_date,
            "store_id": store_id, "product_id": product_id,
            "count": len(items), "total_count": len(ranked), "items": items,
            "count_unit": "issues; a store/product can have multiple distinct issues",
            "priority_rules": deepcopy(PRIORITY_RULES),
            "missing_data_warnings": warnings, "unknowns": self._unknowns(warnings),
            "assumptions": list(ASSUMPTIONS), "trace": _trace("manager.priority_actions"),
            "human_approval_required": True,
        }

    def _financial_summary(self, facts: dict) -> dict:
        revenue, benefits = facts["revenue_risk"], facts["benefits"]
        return {
            "analysis_date": self.analysis_date,
            "currency": SETTINGS.get("data", {}).get("currency", "INR"),
            "stockout_exposure": {
                "products": len(revenue), "revenue_at_risk": _sum(revenue, "revenue_at_risk"),
                "gross_margin_at_risk": _sum(revenue, "gross_margin_at_risk"),
            },
            "overstock_exposure": summarize_blocked_capital(facts["capital"]),
            "smart_transfer": {
                "recommendations": len(facts["transfers"]),
                "estimated_transfer_cost": _sum(benefits, "estimated_transfer_cost"),
                "estimated_revenue_protected": _sum(benefits, "revenue_protected"),
                "estimated_gross_margin_protected": _sum(benefits, "gross_margin_protected"),
                "near_term_cash_purchase_deferred": _sum(benefits, "near_term_cash_purchase_deferred"),
                "estimated_net_operational_benefit": _sum(benefits, "estimated_net_operational_benefit"),
            },
            "disclaimer": (
                "Financial values are deterministic scenario estimates from selected local product prices, "
                "inventory, demand, and configured logistics assumptions. They are not live quotes. "
                "Transfers are independent opportunities; recheck donor stock before approval. "
                "Missing-data exposure is unknown and excluded, not zero."
            ),
        }

    def financial_summary(self, store_id: str | None = None, product_id: str | None = None) -> dict:
        return {**self._financial_summary(self._facts(store_id, product_id)),
                "store_id": store_id, "product_id": product_id}

    def dashboard_summary(self, store_id: str | None = None, product_id: str | None = None) -> dict:
        """Store-scoped counterpart retaining the original dashboard field shapes."""
        self._validate_scope(store_id, product_id)
        scope = {"store_id": store_id, "product_id": product_id}
        stockout = self.analytics.stockout(**scope)
        overstock = self.analytics.overstock(**scope)
        anomalies = self.analytics.anomalies(**scope)
        health = self.analytics.inventory_health(**scope)
        start, end = inclusive_window_endpoints(self.context.analysis_date, 30)
        sales = self.context.sales
        sales = sales[(sales["date"] >= start) & (sales["date"] <= end)]
        if store_id:
            sales = sales[sales["store_id"] == store_id]
        if product_id:
            sales = sales[sales["product_id"] == product_id]
        scores = [item["score"] for item in health if item["score"] is not None]
        stockout_counts = _counts(stockout, "risk", ("critical", "high", "watch", "low", "none", "unknown"))
        return {
            "analysis_date": self.analysis_date, "store_id": store_id, "product_id": product_id,
            "period": {"start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d"), "days": 30},
            "sales": {"revenue": round(float(sales["revenue"].sum()), 2), "units_sold": int(sales["units_sold"].sum())},
            "inventory": {
                "stockout_risk": stockout_counts,
                "overstock": _counts(overstock, "severity", ("severe", "overstock", "unknown")),
                "slow_movers": len(self.analytics.slow_movers(**scope)),
                "average_health_score": round(sum(scores) / len(scores), 2) if scores else None,
            },
            "sales_anomalies": _counts(anomalies, "anomaly_type", ("spike", "drop")),
            "data_quality": {
                "unknown_stockout_recommendations": stockout_counts["unknown"],
                "policy": "Missing data is exposed and affected recommendations are withheld.",
            },
            "attention": self.priority_actions(store_id, product_id, limit=10)["items"],
        }

    def daily_briefing(self, store_id: str | None = None, product_id: str | None = None,
                       limit: int = 5) -> dict:
        facts = self._facts(store_id, product_id)
        ranked = rank_actions(build_actions(**facts))
        top = ranked[:max(0, limit)]
        warnings = self._warnings(ranked)
        stockout = _counts(facts["stockout"], "risk", ("critical", "high", "watch", "low", "none", "unknown"))
        stockout.update({"immediate_attention": stockout["critical"] + stockout["high"],
                         "total_positions": len(facts["stockout"])})
        overstock = _counts(facts["overstock"], "severity", ("severe", "overstock", "unknown"))
        overstock["total_positions"] = len(facts["overstock"])
        anomalies = _counts(facts["anomalies"], "anomaly_type", ("drop", "spike"))
        summary = (
            f"{stockout['immediate_attention']} product-store positions require immediate inventory attention "
            f"({stockout['critical']} critical, {stockout['high']} high). "
            f"{len(facts['transfers'])} safe stock-transfer opportunities were identified. "
            f"{overstock['severe']} positions have severe overstock; "
            f"{len(facts['anomalies'])} sales signals and {len(warnings)} missing-data warnings need review."
        )
        if ranked:
            first = ranked[0]
            summary += f" Highest priority: {first['product_name']} at {first['store_name']}. {first['recommended_action']}"
        else:
            summary += " No manager actions were identified in the selected scope."
        stores = {}
        for item in ranked:
            entry = stores.setdefault(item["store_id"], {
                "store_id": item["store_id"], "store_name": item["store_name"],
                "top_action_id": item["action_id"], "highest_priority_score": item["priority_score"],
                "action_count": 0,
            })
            entry["action_count"] += 1
        return deepcopy({
            "status": "ok", "analysis_date": self.analysis_date,
            "store_id": store_id, "product_id": product_id,
            "summary": summary, "top_issues": top, "recommended_manager_actions": top,
            "total_actions": len(ranked), "store_priorities": list(stores.values()),
            "stockout_summary": stockout, "overstock_summary": overstock,
            "sales_anomalies": {**anomalies, "total": len(facts["anomalies"]), "items": facts["anomalies"][:limit]},
            "transfer_opportunities": {"count": len(facts["transfers"]), "items": facts["transfers"][:limit]},
            "financial_exposure": self._financial_summary(facts),
            "missing_data_warnings": warnings, "unknowns": self._unknowns(warnings),
            "assumptions": list(ASSUMPTIONS), "human_approval_required": True,
            "count_unit": "product-store positions, not unique products across stores",
            "evidence": facts,
            "priority_rules": PRIORITY_RULES, "trace": _trace("manager.daily_briefing"),
        })
