from __future__ import annotations

from functools import cached_property

from backend.analytics.anomalies import calculate_sales_anomalies
from backend.analytics.common import build_context, inclusive_window_endpoints
from backend.analytics.inventory_health import calculate_inventory_health
from backend.analytics.overstock import calculate_overstock
from backend.analytics.product_performance import calculate_product_performance
from backend.analytics.store_performance import calculate_store_performance
from backend.analytics.slow_movers import calculate_slow_movers
from backend.analytics.stockout import calculate_stockout_risk
from backend.core.config import ROOT_DIR, SETTINGS, THRESHOLDS
from backend.services.data_service import DataService


class AnalyticsService:
    """Facade for all deterministic Phase 2 analytics.

    The service loads only local committed CSV data. It performs no network calls
    and no LLM reasoning.
    """

    def __init__(self, data_service: DataService | None = None):
        self.data_service = data_service or DataService(ROOT_DIR / "data" / "raw")

    @cached_property
    def context(self):
        return build_context(self.data_service.load_all())

    @cached_property
    def stockout_items(self) -> list[dict]:
        recent_days = int(SETTINGS.get("analytics", {}).get("recent_sales_days", 7))
        target_days = int(
            THRESHOLDS.get("stockout", {}).get(
                "target_inventory_days",
                SETTINGS.get("analytics", {}).get("target_inventory_days", 21),
            )
        )
        return calculate_stockout_risk(
            self.context,
            recent_sales_days=recent_days,
            target_inventory_days=target_days,
            critical_days_cover=float(
                THRESHOLDS.get("stockout", {}).get("critical_days_cover", 3)
            ),
            high_days_cover=float(
                THRESHOLDS.get("stockout", {}).get("high_days_cover", 7)
            ),
        )

    @cached_property
    def overstock_items(self) -> list[dict]:
        cfg = THRESHOLDS.get("overstock", {})
        lookback = int(cfg.get("lookback_days", 30))
        return calculate_overstock(
            self.context,
            lookback_days=lookback,
            overstock_days=float(cfg.get("days_cover", 60)),
            severe_days=float(cfg.get("severe_days_cover", 120)),
        )

    @cached_property
    def slow_mover_items(self) -> list[dict]:
        cfg = THRESHOLDS.get("slow_mover", {})
        return calculate_slow_movers(
            self.context,
            lookback_days=int(cfg.get("lookback_days", 30)),
            max_units_sold=int(cfg.get("max_units_sold", 20)),
        )

    @cached_property
    def anomaly_items(self) -> list[dict]:
        cfg = THRESHOLDS.get("anomaly", {})
        return calculate_sales_anomalies(
            self.context,
            recent_days=int(cfg.get("recent_days", 7)),
            baseline_days=int(cfg.get("baseline_days", 28)),
            minimum_baseline_units=int(cfg.get("minimum_baseline_units", 14)),
            percentage_change=float(cfg.get("percentage_change", 0.50)),
        )

    @cached_property
    def health_items(self) -> list[dict]:
        return calculate_inventory_health(
            self.stockout_items, self.overstock_items, self.slow_mover_items
        )

    def _filter(
        self,
        items: list[dict],
        *,
        store_id: str | None = None,
        product_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        filtered = items
        if store_id:
            filtered = [i for i in filtered if i.get("store_id") == store_id]
        if product_id:
            filtered = [i for i in filtered if i.get("product_id") == product_id]
        if limit is not None:
            filtered = filtered[: max(0, int(limit))]
        return filtered

    def stockout(
        self, store_id: str | None = None, product_id: str | None = None, limit: int | None = None
    ) -> list[dict]:
        return self._filter(
            self.stockout_items, store_id=store_id, product_id=product_id, limit=limit
        )

    def overstock(
        self, store_id: str | None = None, product_id: str | None = None, limit: int | None = None
    ) -> list[dict]:
        return self._filter(
            self.overstock_items, store_id=store_id, product_id=product_id, limit=limit
        )

    def slow_movers(
        self, store_id: str | None = None, product_id: str | None = None, limit: int | None = None
    ) -> list[dict]:
        return self._filter(
            self.slow_mover_items, store_id=store_id, product_id=product_id, limit=limit
        )

    def anomalies(
        self, store_id: str | None = None, product_id: str | None = None, limit: int | None = None
    ) -> list[dict]:
        return self._filter(
            self.anomaly_items, store_id=store_id, product_id=product_id, limit=limit
        )

    def inventory_health(
        self, store_id: str | None = None, product_id: str | None = None, limit: int | None = None
    ) -> list[dict]:
        return self._filter(
            self.health_items, store_id=store_id, product_id=product_id, limit=limit
        )

    def product_performance(self, product_id: str, store_id: str | None = None) -> dict | None:
        return calculate_product_performance(
            self.context, product_id, store_id=store_id, period_days=30
        )

    def store_performance(self, store_id: str) -> dict | None:
        return calculate_store_performance(self.context, store_id, period_days=30)

    def dashboard_summary(self) -> dict:
        recent_start, recent_end = inclusive_window_endpoints(self.context.analysis_date, 30)
        recent_sales = self.context.sales[
            (self.context.sales["date"] >= recent_start)
            & (self.context.sales["date"] <= recent_end)
        ]

        stockout_counts = {
            level: sum(1 for i in self.stockout_items if i["risk"] == level)
            for level in ["critical", "high", "watch", "low", "none", "unknown"]
        }
        overstock_counts = {
            level: sum(1 for i in self.overstock_items if i["severity"] == level)
            for level in ["severe", "overstock", "unknown"]
        }
        anomaly_counts = {
            level: sum(1 for i in self.anomaly_items if i["anomaly_type"] == level)
            for level in ["spike", "drop"]
        }
        health_known = [i["score"] for i in self.health_items if i["score"] is not None]

        attention = []
        for item in self.stockout_items:
            if item["risk"] in {"critical", "high", "unknown"}:
                attention.append(
                    {
                        "type": "stockout",
                        "severity": item["risk"],
                        "store_id": item["store_id"],
                        "store_name": item["store_name"],
                        "product_id": item["product_id"],
                        "product_name": item["product_name"],
                        "headline_metric": item["days_cover"],
                        "headline_metric_name": "days_cover",
                        "reason": item["reason"],
                    }
                )
        for item in self.overstock_items:
            if item["severity"] in {"severe", "overstock"}:
                attention.append(
                    {
                        "type": "overstock",
                        "severity": item["severity"],
                        "store_id": item["store_id"],
                        "store_name": item["store_name"],
                        "product_id": item["product_id"],
                        "product_name": item["product_name"],
                        "headline_metric": item["days_cover"],
                        "headline_metric_name": "days_cover",
                        "reason": item["reason"],
                    }
                )
        for item in self.anomaly_items:
            attention.append(
                {
                    "type": "sales_anomaly",
                    "severity": item["anomaly_type"],
                    "store_id": item["store_id"],
                    "store_name": item["store_name"],
                    "product_id": item["product_id"],
                    "product_name": item["product_name"],
                    "headline_metric": item["percentage_change"],
                    "headline_metric_name": "percentage_change",
                    "reason": item["reason"],
                }
            )

        severity_rank = {
            "critical": 0,
            "unknown": 1,
            "high": 2,
            "severe": 3,
            "overstock": 4,
            "drop": 5,
            "spike": 6,
        }
        attention = sorted(
            attention,
            key=lambda x: (
                severity_rank.get(x["severity"], 99),
                x["store_id"],
                x["product_id"],
            ),
        )[:10]

        return {
            "analysis_date": self.context.analysis_date.strftime("%Y-%m-%d"),
            "period": {
                "start": recent_start.strftime("%Y-%m-%d"),
                "end": recent_end.strftime("%Y-%m-%d"),
                "days": 30,
            },
            "sales": {
                "revenue": round(float(recent_sales["revenue"].sum()), 2),
                "units_sold": int(recent_sales["units_sold"].sum()),
            },
            "inventory": {
                "stockout_risk": stockout_counts,
                "overstock": overstock_counts,
                "slow_movers": len(self.slow_mover_items),
                "average_health_score": (
                    round(sum(health_known) / len(health_known), 2) if health_known else None
                ),
            },
            "sales_anomalies": anomaly_counts,
            "data_quality": {
                "unknown_stockout_recommendations": stockout_counts["unknown"],
                "policy": "RetailIQ exposes missing data and withholds affected recommendations instead of guessing.",
            },
            "attention": attention,
        }

    def assumptions(self) -> dict:
        return {
            "analysis_date": self.context.analysis_date.strftime("%Y-%m-%d"),
            "settings": SETTINGS.get("analytics", {}),
            "thresholds": THRESHOLDS,
            "principle": "All metrics are deterministic and derived from local committed data; no LLM is used for calculations.",
        }
