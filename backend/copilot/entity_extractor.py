from __future__ import annotations

import re
from dataclasses import dataclass

from backend.multilingual.terminology import PRODUCT_ALIASES, STORE_ALIASES


@dataclass(frozen=True)
class EntityResolution:
    store_id: str | None
    product_id: str | None
    ambiguous_products: list[dict]
    ambiguous_stores: list[dict]


def _boundary_match(text: str, alias: str) -> bool:
    if re.search(r"[\u0900-\u097F]", alias):
        return alias in text
    pattern = r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])"
    return re.search(pattern, text) is not None


def _product_record(row) -> dict:
    return {
        "product_id": str(row["product_id"]),
        "product_name": str(row["product_name"]),
        "category": str(row.get("category", "")),
    }


def resolve_entities(
    text: str,
    products,
    stores,
    *,
    explicit_store_id: str | None = None,
    explicit_product_id: str | None = None,
) -> EntityResolution:
    lowered = (text or "").lower()

    valid_store_ids = set(stores["store_id"].astype(str))
    valid_product_ids = set(products["product_id"].astype(str))

    store_id = explicit_store_id if explicit_store_id in valid_store_ids else None
    product_id = explicit_product_id if explicit_product_id in valid_product_ids else None
    ambiguous_stores: list[dict] = []
    ambiguous_products: list[dict] = []

    if store_id is None:
        candidates: dict[str, dict] = {}
        for _, row in stores.iterrows():
            sid = str(row["store_id"])
            aliases = {sid.lower(), str(row["store_name"]).lower(), str(row["city"]).lower()}
            aliases.update(k for k, v in STORE_ALIASES.items() if v == sid)
            if any(_boundary_match(lowered, a) for a in aliases if a):
                candidates[sid] = {
                    "store_id": sid,
                    "store_name": str(row["store_name"]),
                    "city": str(row["city"]),
                }
        if len(candidates) == 1:
            store_id = next(iter(candidates))
        elif len(candidates) > 1:
            ambiguous_stores = list(candidates.values())

    if product_id is None:
        # Pass 1: exact catalog names / IDs / curated multilingual aliases.
        exact: dict[str, dict] = {}
        for _, row in products.iterrows():
            pid = str(row["product_id"])
            aliases = {pid.lower(), str(row["product_name"]).lower()}
            aliases.update(k for k, v in PRODUCT_ALIASES.items() if v == pid)
            if any(_boundary_match(lowered, a) for a in aliases if a):
                exact[pid] = _product_record(row)

        if len(exact) == 1:
            product_id = next(iter(exact))
        elif len(exact) > 1:
            ambiguous_products = sorted(exact.values(), key=lambda x: x["product_id"])
        else:
            # Pass 2: broader catalog words. Multiple matches intentionally become
            # a clarification rather than a hidden guess (e.g. "bread").
            broad: dict[str, dict] = {}
            for _, row in products.iterrows():
                pid = str(row["product_id"])
                words = [
                    w
                    for w in re.split(r"[^a-z0-9]+", str(row["product_name"]).lower())
                    if len(w) >= 4 and not w.isdigit()
                ]
                if any(_boundary_match(lowered, word) for word in words):
                    broad[pid] = _product_record(row)
            if len(broad) == 1:
                product_id = next(iter(broad))
            elif len(broad) > 1:
                ambiguous_products = sorted(broad.values(), key=lambda x: x["product_id"])

    return EntityResolution(
        store_id=store_id,
        product_id=product_id,
        ambiguous_products=ambiguous_products,
        ambiguous_stores=ambiguous_stores,
    )
