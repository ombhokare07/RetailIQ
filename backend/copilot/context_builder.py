from __future__ import annotations

from typing import Any

from backend.explainability.evidence_builder import build_evidence_packet
from backend.explainability.explanation_engine import build_fact_table


def build_grounded_context(intent: str, payload: Any, unknowns: list[str]) -> tuple[dict, list[dict]]:
    packet = build_evidence_packet(intent, payload, unknowns)
    fact_table = build_fact_table(packet["facts"])
    packet["fact_count"] = len(fact_table)
    return packet, fact_table
