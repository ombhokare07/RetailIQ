from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.multilingual.terminology import PRODUCT_ALIASES, STORE_ALIASES


@dataclass(frozen=True)
class EntityResolution:
    store_id: str | None
    product_id: str | None
    ambiguous_products: list[dict]
    ambiguous_stores: list[dict]
    source_store_id: str | None = None
    unknown_products: list[str] = field(default_factory=list)
    unknown_stores: list[str] = field(default_factory=list)


def _boundary_match(text: str, alias: str) -> bool:
    if re.search(r"[\u0900-\u097F]", alias):
        return alias in text
    return re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", text) is not None


def _product_record(row) -> dict:
    return {"product_id": str(row["product_id"]), "product_name": str(row["product_name"]), "category": str(row.get("category", ""))}


def resolve_entities(text: str, products, stores, *, explicit_store_id: str | None = None, explicit_product_id: str | None = None) -> EntityResolution:
    lowered = " ".join((text or "").lower().split())
    valid_stores = set(stores["store_id"].astype(str))
    valid_products = set(products["product_id"].astype(str))
    # IDs are normalized only when this identifies one exact catalog entry.
    def normalize(value, catalog):
        if value is None:
            return None
        return next((item for item in sorted(catalog) if item.casefold() == value.casefold()), value)
    explicit_store_id = normalize(explicit_store_id, valid_stores)
    explicit_product_id = normalize(explicit_product_id, valid_products)
    unknown_stores = [explicit_store_id] if explicit_store_id and explicit_store_id not in valid_stores else []
    unknown_products = [explicit_product_id] if explicit_product_id and explicit_product_id not in valid_products else []
    unknown_stores += [v.upper() for v in re.findall(r"\bs\d{3,}\b", lowered) if v.upper() not in valid_stores]
    unknown_products += [v.upper() for v in re.findall(r"\bp\d{3,}\b", lowered) if v.upper() not in valid_products]
    store_id = explicit_store_id if explicit_store_id in valid_stores else None
    product_id = explicit_product_id if explicit_product_id in valid_products else None
    source_store_id = None
    ambiguous_stores, ambiguous_products = [], []
    store_matches = {}
    aliases_by_store = {}
    demo_cities = {"S001": "pune", "S002": "mumbai", "S003": "nashik"}
    for _, row in stores.iterrows():
        sid = str(row["store_id"])
        aliases = {sid.lower(), str(row["store_name"]).lower(), str(row["city"]).lower()}
        if str(row["city"]).lower() == demo_cities.get(sid):
            aliases.update(k for k, v in STORE_ALIASES.items() if v == sid)
            if sid == "S001":
                aliases.add("पुण्यात")
        aliases_by_store[sid] = aliases
        if any(_boundary_match(lowered, alias) for alias in aliases if alias):
            store_matches[sid] = {"store_id": sid, "store_name": str(row["store_name"]), "city": str(row["city"])}
    if not store_id and len(store_matches) == 1:
        store_id = next(iter(store_matches))
    elif len(store_matches) > 1:
        # Explicit direction resolves donor/recipient; listing two stores alone does not.
        for donor in store_matches:
            for recipient in store_matches:
                if donor == recipient:
                    continue
                for a in aliases_by_store[donor]:
                    for b in aliases_by_store[recipient]:
                        if re.search(rf"\bcan\s+{re.escape(a)}\s+help\s+{re.escape(b)}\b", lowered) or re.search(rf"\bfrom\s+{re.escape(a)}(?:\s+store)?\s+to\s+{re.escape(b)}\b", lowered):
                            source_store_id = donor
                            store_id = explicit_store_id or recipient
        if not store_id:
            ambiguous_stores = sorted(store_matches.values(), key=lambda item: item["store_id"])

    if product_id is None:
        exact = {}
        matched_aliases = {}
        # Tie translated demo aliases to product names, not reused custom IDs.
        demo_names = {"P001": "amul milk", "P003": "paneer", "P004": "butter", "P005": "cheese slices", "P006": "brown bread", "P011": "cola", "P021": "shampoo"}
        for _, row in products.iterrows():
            pid, name = str(row["product_id"]), str(row["product_name"]).lower()
            aliases = {pid.lower(), name}
            if name.startswith(demo_names.get(pid, "\0")):
                aliases.update(k for k, v in PRODUCT_ALIASES.items() if v == pid)
            matches = {a for a in aliases if a and _boundary_match(lowered, a)}
            if matches:
                exact[pid] = _product_record(row)
                matched_aliases[pid] = matches
        # A fully named Peanut Butter wins over the contained word Butter.
        exact = {pid: value for pid, value in exact.items() if not all(
            any(alias != other and alias in other for oid, others in matched_aliases.items() if oid != pid for other in others)
            for alias in matched_aliases[pid]
        )}
        if len(exact) == 1:
            product_id = next(iter(exact))
        elif len(exact) > 1:
            ambiguous_products = sorted(exact.values(), key=lambda item: item["product_id"])
        else:
            broad = {}
            for _, row in products.iterrows():
                words = [w for w in re.split(r"[^a-z0-9]+", str(row["product_name"]).lower()) if len(w) >= 4 and not w.isdigit()]
                score = sum(_boundary_match(lowered, word) for word in words)
                if score:
                    broad[str(row["product_id"])] = (_product_record(row), score)
            if len(broad) == 1:
                product_id = next(iter(broad))
            elif broad:
                ambiguous_products = [v[0] for v in sorted(broad.values(), key=lambda v: (-v[1], v[0]["product_id"]))]

    if not store_id and not ambiguous_stores and not unknown_stores:
        place = re.search(r"\b(?:in|at)\s+([a-z]+)(?:\s+store)?\s*[?.!]*$", lowered)
        if place and place.group(1) not in {"stock", "sales", "inventory", "mind", "risk", "cost", "all", "stores"}:
            unknown_stores.append(place.group(1))
    if not product_id and not ambiguous_products and not unknown_products:
        product = re.search(r"\b(?:how is|how are|performance of|demand for|do about|reorder quantity for)\s+(.+?)(?=\s+(?:in|at|doing|increases?|decreases?)\b|[?.!]|$)", lowered)
        product = product or re.search(r"\bwill\s+(.+?)\s+run out\b", lowered)
        if product and product.group(1) not in {"products", "the products", "stock", "demand", "it", "this", "sales", "inventory"}:
            unknown_products.append(product.group(1))
    return EntityResolution(store_id, product_id, ambiguous_products, ambiguous_stores, source_store_id, list(dict.fromkeys(unknown_products)), list(dict.fromkeys(unknown_stores)))
