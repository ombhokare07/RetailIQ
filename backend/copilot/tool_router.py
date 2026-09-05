from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from backend.services.analytics_service import AnalyticsService
from backend.services.decision_service import DecisionService
from backend.services.simulation_service import SimulationService


@dataclass(frozen=True)
class ToolResult:
    status: str
    payload: Any
    tool: str
    message: str | None = None


class ToolRouter:
    """Maps language-layer intents to deterministic Python services only."""

    def __init__(
        self,
        analytics: AnalyticsService | None = None,
        decisions: DecisionService | None = None,
        simulations: SimulationService | None = None,
    ):
        self.analytics = analytics or AnalyticsService()
        self.decisions = decisions or DecisionService(self.analytics)
        self.simulations = simulations or SimulationService(self.decisions)

    def execute(
        self,
        *,
        intent: str,
        store_id: str | None,
        product_id: str | None,
        demand_multiplier: float | None = None,
        source_store_id: str | None = None,
    ) -> ToolResult:
        if intent == "dashboard_attention":
            from backend.briefing.daily_briefing import ManagerBriefingService
            manager = ManagerBriefingService(analytics=self.analytics, decisions=self.decisions)
            return ToolResult("ok", manager.daily_briefing(store_id=store_id, product_id=product_id), "manager.daily_briefing")

        if intent == "stockout_risk":
            items = self.analytics.stockout(store_id=store_id, product_id=product_id)
            # A plural risk question should return actionable or uncertain
            # positions. A product-specific query keeps low-risk records so the
            # answer can still explain that the product is currently safe.
            if product_id is None:
                items = [item for item in items if item.get("risk") in {"critical", "high", "watch", "unknown"}]
            items = sorted(items, key=lambda x: ({"critical": 0, "high": 1, "watch": 2, "low": 3, "none": 4, "unknown": 5}.get(x.get("risk"), 9), x.get("days_cover") if x.get("days_cover") is not None else float("inf"), x.get("store_id", ""), x.get("product_id", "")))
            status = "insufficient_data" if items and all(i.get("risk") == "unknown" for i in items) else "ok"
            return ToolResult(status, items, "analytics.stockout")

        if intent == "overstock":
            items = self.analytics.overstock(store_id=store_id, product_id=product_id)
            return ToolResult("ok", items, "analytics.overstock")

        if intent == "slow_movers":
            items = self.analytics.slow_movers(store_id=store_id, product_id=product_id)
            return ToolResult("ok", items, "analytics.slow_movers")

        if intent == "sales_anomalies":
            items = self.analytics.anomalies(store_id=store_id, product_id=product_id)
            return ToolResult("ok", items, "analytics.sales_anomalies")

        if intent == "product_performance":
            if not product_id:
                return ToolResult("needs_clarification", None, "analytics.product_performance", "Which product do you mean?")
            result = self.analytics.product_performance(product_id, store_id=store_id)
            if result is None:
                return ToolResult("not_found", None, "analytics.product_performance", "No matching product performance record was found.")
            return ToolResult("ok", result, "analytics.product_performance")

        if intent == "store_performance":
            if not store_id:
                return ToolResult("needs_clarification", None, "analytics.store_performance", "Which store do you mean?")
            result = self.analytics.store_performance(store_id)
            if result is None:
                return ToolResult("not_found", None, "analytics.store_performance", "No matching store performance record was found.")
            return ToolResult("ok", result, "analytics.store_performance")

        if intent == "smart_transfer":
            items = self.decisions.transfer_recommendations(store_id=store_id, product_id=product_id)
            if source_store_id:
                items = [item for item in items if item.get("recommended_source_store_id") == source_store_id]
            return ToolResult("ok", items, "decision.smart_transfer")

        if intent == "financial_summary":
            from backend.briefing.daily_briefing import ManagerBriefingService
            manager = ManagerBriefingService(analytics=self.analytics, decisions=self.decisions)
            return ToolResult("ok", manager.financial_summary(store_id=store_id, product_id=product_id), "decision.financial_summary")

        if intent in {"decision_compare", "demand_shock"}:
            if intent == "demand_shock" and demand_multiplier is None:
                return ToolResult("needs_clarification", None, "simulation.compare", "Specify a demand increase, decrease, or multiplier for the what-if assumption.")
            if demand_multiplier is not None and (not math.isfinite(demand_multiplier) or not 0 < demand_multiplier <= 5):
                return ToolResult("unsupported", None, "simulation.compare", "The supported demand multiplier must be greater than zero and at most five.")
            if not store_id or not product_id:
                return ToolResult(
                    "needs_clarification",
                    None,
                    "simulation.compare",
                    "A store and product are required for a what-if comparison.",
                )
            result = self.simulations.compare(
                store_id=store_id,
                product_id=product_id,
                demand_multiplier=demand_multiplier,
            )
            if result.get("status") == "insufficient_data":
                known = self.analytics.stockout(store_id=store_id, product_id=product_id)
                if known:
                    result["current_state"] = {key: known[0].get(key) for key in ("current_stock", "avg_daily_sales", "days_cover", "recommended_reorder_qty", "risk")}
            return ToolResult(result.get("status", "ok"), result, "simulation.compare")

        if intent == "causal_explanation":
            if not product_id:
                return ToolResult("needs_clarification", None, "analytics.causal_guard", "Which product's sales change do you mean?")
            anomalies = self.analytics.anomalies(store_id=store_id, product_id=product_id, limit=5)
            performance = self.analytics.product_performance(product_id, store_id=store_id)
            return ToolResult(
                "ok",
                {
                    "anomalies": anomalies,
                    "performance": performance,
                    "causal_evidence_available": False,
                    "reason": "The committed dataset contains sales, inventory, products and stores, but no promotion, competitor, weather or customer-behaviour causal evidence.",
                },
                "analytics.causal_guard",
            )

        return ToolResult("unsupported", None, "none", "The request is outside the supported RetailIQ analyses.")
