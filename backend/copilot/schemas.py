from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field

IntentName = Literal[
    "dashboard_attention",
    "stockout_risk",
    "overstock",
    "slow_movers",
    "sales_anomalies",
    "product_performance",
    "store_performance",
    "smart_transfer",
    "financial_summary",
    "decision_compare",
    "demand_shock",
    "causal_explanation",
    "unknown",
]


class CopilotRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    language: Literal["en", "hi", "mr"] | None = None
    store_id: str | None = None
    product_id: str | None = None


class GeminiIntent(BaseModel):
    intent: IntentName
    store_id: str | None = None
    product_id: str | None = None
    language: Literal["en", "hi", "mr"] | None = None
    demand_multiplier: float | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class GeminiNarrative(BaseModel):
    answer: str
    used_fact_ids: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    human_action: str | None = None
