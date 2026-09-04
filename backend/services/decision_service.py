from __future__ import annotations

from functools import cached_property

from backend.core.config import SETTINGS, THRESHOLDS
from backend.financial.action_benefit import calculate_transfer_action_benefits
from backend.financial.blocked_capital import summarize_blocked_capital
from backend.financial.overstock_value import calculate_overstock_value
from backend.financial.revenue_risk import calculate_revenue_risk
from backend.services.analytics_service import AnalyticsService
from backend.stock_transfer.transfer_engine import calculate_transfer_recommendations


class DecisionService:
    """Deterministic Phase 3 decision and financial-impact facade."""

    def __init__(self, analytics_service: AnalyticsService | None = None):
        self.analytics = analytics_service or AnalyticsService()

    @property
    def context(self):
        return self.analytics.context

    @cached_property
    def transfer_recommendation_items(self) -> list[dict]:
        cfg = THRESHOLDS.get("transfer", {})
        return calculate_transfer_recommendations(
            self.context,
            self.analytics.stockout_items,
            donor_min_days_cover=float(cfg.get("donor_min_days_cover", 21)),
            minimum_transfer_units=int(cfg.get("minimum_transfer_units", 5)),
            fixed_transfer_cost=float(cfg.get("fixed_transfer_cost", 250)),
            per_unit_transfer_cost=float(cfg.get("per_unit_transfer_cost", 2.5)),
        )

    @cached_property
    def revenue_risk_items(self) -> list[dict]:
        return calculate_revenue_risk(self.context, self.analytics.stockout_items)

    @cached_property
    def overstock_capital_items(self) -> list[dict]:
        cfg = THRESHOLDS.get("financial", {})
        return calculate_overstock_value(
            self.context,
            self.analytics.overstock_items,
            allowed_days_cover=float(
                cfg.get(
                    "allowed_overstock_days",
                    THRESHOLDS.get("overstock", {}).get("days_cover", 60),
                )
            ),
        )

    @cached_property
    def transfer_benefit_items(self) -> list[dict]:
        cfg = THRESHOLDS.get("financial", {})
        return calculate_transfer_action_benefits(
            self.context,
            self.transfer_recommendation_items,
            emergency_purchase_markup=float(cfg.get("emergency_purchase_markup", 0.15)),
        )

    @staticmethod
    def _filter(
        items: list[dict],
        *,
        store_id: str | None = None,
        product_id: str | None = None,
        limit: int | None = None,
        store_keys: tuple[str, ...] = ("store_id", "recipient_store_id"),
    ) -> list[dict]:
        filtered = items
        if store_id:
            filtered = [
                item
                for item in filtered
                if any(item.get(key) == store_id for key in store_keys)
            ]
        if product_id:
            filtered = [i for i in filtered if i.get("product_id") == product_id]
        if limit is not None:
            filtered = filtered[: max(0, int(limit))]
        return filtered

    def transfer_recommendations(
        self,
        *,
        store_id: str | None = None,
        product_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        return self._filter(
            self.transfer_recommendation_items,
            store_id=store_id,
            product_id=product_id,
            limit=limit,
        )

    def revenue_risk(
        self,
        *,
        store_id: str | None = None,
        product_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        return self._filter(
            self.revenue_risk_items,
            store_id=store_id,
            product_id=product_id,
            limit=limit,
            store_keys=("store_id",),
        )

    def overstock_capital(
        self,
        *,
        store_id: str | None = None,
        product_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        return self._filter(
            self.overstock_capital_items,
            store_id=store_id,
            product_id=product_id,
            limit=limit,
            store_keys=("store_id",),
        )

    def transfer_benefits(
        self,
        *,
        store_id: str | None = None,
        product_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        return self._filter(
            self.transfer_benefit_items,
            store_id=store_id,
            product_id=product_id,
            limit=limit,
        )

    def financial_summary(self) -> dict:
        revenue_risk = round(
            sum(float(i.get("revenue_at_risk", 0)) for i in self.revenue_risk_items), 2
        )
        gross_margin_risk = round(
            sum(float(i.get("gross_margin_at_risk", 0)) for i in self.revenue_risk_items), 2
        )
        blocked = summarize_blocked_capital(self.overstock_capital_items)
        transfer_cost = round(
            sum(float(i.get("estimated_transfer_cost", 0)) for i in self.transfer_benefit_items), 2
        )
        revenue_protected = round(
            sum(float(i.get("revenue_protected", 0)) for i in self.transfer_benefit_items), 2
        )
        gross_margin_protected = round(
            sum(float(i.get("gross_margin_protected", 0)) for i in self.transfer_benefit_items), 2
        )
        cash_deferred = round(
            sum(float(i.get("near_term_cash_purchase_deferred", 0)) for i in self.transfer_benefit_items), 2
        )
        net_operational_benefit = round(
            sum(float(i.get("estimated_net_operational_benefit", 0)) for i in self.transfer_benefit_items), 2
        )

        return {
            "analysis_date": self.context.analysis_date.strftime("%Y-%m-%d"),
            "currency": SETTINGS.get("data", {}).get("currency", "INR"),
            "stockout_exposure": {
                "products": len(self.revenue_risk_items),
                "revenue_at_risk": revenue_risk,
                "gross_margin_at_risk": gross_margin_risk,
            },
            "overstock_exposure": blocked,
            "smart_transfer": {
                "recommendations": len(self.transfer_recommendation_items),
                "estimated_transfer_cost": transfer_cost,
                "estimated_revenue_protected": revenue_protected,
                "estimated_gross_margin_protected": gross_margin_protected,
                "near_term_cash_purchase_deferred": cash_deferred,
                "estimated_net_operational_benefit": net_operational_benefit,
            },
            "disclaimer": (
                "Financial values are deterministic scenario estimates from committed product prices, "
                "inventory, demand, and configured logistics assumptions. They are not live supplier or carrier quotes."
            ),
        }
