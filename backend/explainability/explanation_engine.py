from __future__ import annotations

import re
from typing import Any


def build_fact_table(payload: Any, max_facts: int = 60) -> list[dict]:
    """Flatten scalar deterministic facts into IDs Gemini can cite."""

    facts: list[dict] = []

    def walk(value: Any, path: str = "result") -> None:
        if len(facts) >= max_facts:
            return

        if isinstance(value, dict):
            for key, child in value.items():
                if key in {
                    "sale_ids",
                    "current_sale_ids",
                    "previous_sale_ids",
                    "inventory_ids",
                    "alternative_sources",
                }:
                    continue

                walk(child, f"{path}.{key}")

        elif isinstance(value, list):
            for index, child in enumerate(value[:5]):
                walk(child, f"{path}[{index}]")

        elif isinstance(value, (str, int, float, bool)) or value is None:
            facts.append(
                {
                    "fact_id": f"F{len(facts)+1}",
                    "path": path,
                    "value": value,
                }
            )

    walk(payload)
    return facts


def numeric_guard(
    answer: str,
    fact_table: list[dict],
    source_payload: Any | None = None,
) -> tuple[bool, list[str]]:
    """Reject model answers that introduce numbers absent from deterministic data.

    fact_table stays compact because it is sent to Gemini.

    source_payload is the complete deterministic Python result. It is used only
    by this local validator so valid numbers omitted from the compact Gemini
    prompt are not incorrectly rejected.
    """

    allowed: set[str] = set()

    def add_value(value: Any) -> None:
        if isinstance(value, bool) or value is None:
            return

        if isinstance(value, (int, float)):
            allowed.add(str(value))

            if isinstance(value, float):
                allowed.add(f"{value:.1f}")
                allowed.add(f"{value:.2f}")

            return

        if isinstance(value, str):
            allowed.update(
                re.findall(r"\d+(?:\.\d+)?", value)
            )

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for child in value.values():
                walk(child)

        elif isinstance(value, list):
            for child in value:
                walk(child)

        else:
            add_value(value)

    # Numbers Gemini was explicitly shown.
    for fact in fact_table:
        add_value(fact.get("value"))

    # Complete deterministic Python result.
    if source_payload is not None:
        walk(source_payload)

    unexpected = []

    for token in re.findall(r"\d+(?:\.\d+)?", answer or ""):

        if token in allowed:
            continue

        try:
            token_float = float(token)

            if any(
                _numeric_equal(token_float, allowed_value)
                for allowed_value in allowed
            ):
                continue

        except ValueError:
            pass

        unexpected.append(token)

    return (
        len(unexpected) == 0,
        list(dict.fromkeys(unexpected)),
    )


def _numeric_equal(token: float, allowed_value: str) -> bool:
    try:
        return abs(token - float(allowed_value)) < 1e-6
    except (TypeError, ValueError):
        return False