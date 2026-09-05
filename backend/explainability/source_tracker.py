from __future__ import annotations

from collections import defaultdict
from typing import Any


def _walk(value: Any):
    if isinstance(value, dict):
        for k, v in value.items():
            yield k, v
            yield from _walk(v)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def build_source_citations(payload: Any, max_ids_per_source: int = 20) -> list[dict]:
    """Create compact traceability metadata from deterministic result IDs."""

    ids_by_source: dict[str, list[str]] = defaultdict(list)

    for key, value in _walk(payload):
        values: list[str] = []
        if key in {"inventory_id", "recommendation_id", "product_id", "store_id", "recipient_store_id", "recommended_source_store_id", "source_store_id"} and value:
            values = [str(value)]
        elif key in {"inventory_ids", "sale_ids", "current_sale_ids", "previous_sale_ids"} and isinstance(value, list):
            values = [str(v) for v in value if v]

        for record_id in values:
            if record_id.startswith("INV-"):
                source = "data/raw/inventory.csv"
            elif record_id.startswith("SALE-"):
                source = "data/raw/sales.csv"
            elif record_id.startswith("TR-"):
                source = "derived/smart-transfer-recommendation"
            elif record_id.startswith("P") and record_id[1:].isdigit():
                source = "data/raw/products.csv"
            elif record_id.startswith("S") and record_id[1:].isdigit():
                source = "data/raw/stores.csv"
            else:
                continue
            if record_id not in ids_by_source[source]:
                ids_by_source[source].append(record_id)

    citations: list[dict] = []
    for index, source in enumerate(sorted(ids_by_source), start=1):
        all_ids = ids_by_source[source]
        citations.append(
            {
                "citation_id": f"E{index}",
                "source": source,
                "record_ids": all_ids[:max_ids_per_source],
                "truncated_record_count": max(0, len(all_ids) - max_ids_per_source),
            }
        )
    return citations
