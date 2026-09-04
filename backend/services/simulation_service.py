from __future__ import annotations

from backend.core.config import THRESHOLDS
from backend.digital_twin.simulator import simulate_decision
from backend.services.decision_service import DecisionService


class SimulationService:
    """Facade for deterministic Retail Decision Twin scenarios."""

    def __init__(self, decision_service: DecisionService | None = None):
        self.decision = decision_service or DecisionService()

    @property
    def context(self):
        return self.decision.context

    @property
    def config(self) -> dict:
        return THRESHOLDS.get("simulation", {})

    def _stockout_item(self, store_id: str, product_id: str) -> dict | None:
        for item in self.decision.analytics.stockout_items:
            if item.get("store_id") == store_id and item.get("product_id") == product_id:
                return item
        return None

    def _product(self, product_id: str):
        matches = self.context.products[self.context.products["product_id"] == product_id]
        if matches.empty:
            return None
        return next(matches.itertuples(index=False))

    def compare(
        self,
        *,
        store_id: str,
        product_id: str,
        horizon_days: int | None = None,
        demand_multiplier: float | None = None,
    ) -> dict:
        stockout_item = self._stockout_item(store_id, product_id)
        product = self._product(product_id)
        if stockout_item is None or product is None:
            return {
                "status": "not_found",
                "store_id": store_id,
                "product_id": product_id,
                "message": "No matching store/product pair exists in the committed RetailIQ data.",
            }

        default_horizon = int(self.config.get("default_horizon_days", 14))
        max_horizon = int(self.config.get("max_horizon_days", 60))
        horizon = default_horizon if horizon_days is None else int(horizon_days)
        horizon = max(1, min(max_horizon, horizon))
        multiplier = (
            float(self.config.get("default_demand_multiplier", 1.0))
            if demand_multiplier is None
            else float(demand_multiplier)
        )

        transfers = self.decision.transfer_recommendations(
            store_id=store_id, product_id=product_id, limit=1
        )
        transfer = transfers[0] if transfers else None
        return simulate_decision(
            stockout_item=stockout_item,
            product=product,
            transfer_recommendation=transfer,
            horizon_days=horizon,
            demand_multiplier=multiplier,
            transfer_arrival_days=int(self.config.get("transfer_arrival_days", 1)),
        )
