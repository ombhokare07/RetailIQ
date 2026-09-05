from __future__ import annotations

from typing import Any


def collect_unknowns(intent: str, payload: Any) -> list[str]:
    unknowns: list[str] = []

    if isinstance(payload, dict):
        if payload.get("status") == "insufficient_data":
            unknowns.extend(str(v) for v in payload.get("unknown_fields", []) if v)
        if payload.get("data_quality", {}).get("note"):
            unknowns.append(str(payload["data_quality"]["note"]))
    elif isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            if item.get("risk") == "unknown":
                unknowns.extend(str(v) for v in item.get("unknown_fields", []) if v)

    if intent == "causal_explanation":
        unknowns.extend(
            [
                "promotion/activity data",
                "competitor pricing data",
                "weather/external demand-driver data",
                "customer-behaviour data",
            ]
        )

    # Stable dedupe.
    return list(dict.fromkeys(unknowns))
