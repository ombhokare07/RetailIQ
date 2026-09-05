from __future__ import annotations

import re


def _contains_any(text: str, phrases: list[str]) -> bool:
    return any(p in text for p in phrases)


def parse_demand_multiplier(text: str) -> float | None:
    """Parse supported demand assumptions; validation belongs to the tool boundary."""
    lowered = text.lower()
    if _contains_any(lowered, ["double", "दुप्पट", "दोगुनी", "दोगुना"]):
        return 2.0
    if _contains_any(lowered, ["halves", "halved", "half", "अर्धी", "आधी"]):
        return 0.5
    for words, direction in [
        (r"decrease\w*|fall\w*|drop\w*|down|lower|less|कमी|घट", -1),
        (r"increase\w*|up|higher|more|वाढ|बढ़|बढ", 1),
    ]:
        pattern = rf"(?:{words})[^\d]{{0,24}}(\d+(?:\.\d+)?)\s*%"
        match = re.search(pattern, lowered)
        match = match or re.search(rf"(\d+(?:\.\d+)?)\s*%[^\n]{{0,20}}(?:{words})", lowered)
        if match:
            return round(1 + direction * float(match.group(1)) / 100.0, 4)
    multiple = re.search(r"(\d+(?:\.\d+)?)\s*[x×]\b", lowered)
    return float(multiple.group(1)) if multiple else None


def unsupported_fact_override(text: str) -> bool:
    """User text never mutates stock, prices, costs, revenue, or safety rules."""
    t = text.lower()
    if _contains_any(t, ["ignore the database", "ignore all rules", "ignore all previous", "ignore previous", "even if the data", "invent a reorder", "invent the reorder"]):
        return True
    directive = _contains_any(t, ["assume", "pretend", "say", "tell me", "make", "set", "override"])
    factual = _contains_any(t, ["stock", "revenue", "transfer cost", "transfer costs", "price", "reorder quantity", "lead time"])
    return directive and factual and bool(re.search(r"\d", t)) and not (
        _contains_any(t, ["demand", "मागणी", "मांग"])
        and not re.search(r"(?:stock|revenue|costs?|price|lead time)\s+(?:is|to|as|of|=)\s*\d", t)
    )


def route_intent(text: str) -> tuple[str, float | None]:
    t = " ".join((text or "").lower().split())
    multiplier = parse_demand_multiplier(t)
    if _contains_any(t, [
        "why did", "why has", "why are", "why is", "reason for", "cause of", "cause the", "caused", "competitor pricing",
        "क्यों", "किस वजह", "का कारण", "का कमी", "का वाढ", "कारण काय", "का घसर",
    ]):
        return "causal_explanation", multiplier
    if _contains_any(t, ["demand", "मागणी", "मांग"]) and (multiplier is not None or "what if" in t):
        return "demand_shock", multiplier
    if ("transfer" in t and "reorder" in t) or _contains_any(t, [
        "what if", "compare options", "compare reorder", "transfer vs", "best option", "what should i do", "do nothing",
        "काहीही करू नये", "काय करावे", "क्या करना चाहिए",
    ]):
        return "decision_compare", multiplier
    if _contains_any(t, ["transfer", "reallocate", "move stock", "can mumbai help", "can pune help", "can nashik help", "ट्रांसफर", "ट्रान्सफर", "स्टॉक हलवा"]):
        return "smart_transfer", multiplier
    if _contains_any(t, ["financial", "revenue", "capital", "money", "₹", "पैसा", "पूंजी", "महसूल", "आर्थिक"]):
        return "financial_summary", multiplier
    if _contains_any(t, ["running out", "run out", "stockout", "stock-out", "low stock", "reorder", "खत्म", "संपणार", "स्टॉक कमी"]):
        return "stockout_risk", multiplier
    if _contains_any(t, ["overstock", "too much stock", "excess stock", "sitting unnecessarily", "ज्यादा स्टॉक", "जास्त स्टॉक", "ओव्हरस्टॉक", "ओवरस्टॉक"]):
        return "overstock", multiplier
    if _contains_any(t, ["slow mover", "slow-moving", "dead inventory", "not selling", "not moving", "zero sales", "धीमी बिक्री", "नहीं बिक", "स्लो मूव्ह", "विकत नाही"]):
        return "slow_movers", multiplier
    if _contains_any(t, ["spike", "drop", "unusual", "असामान्य", "sales change", "sales anomaly", "sales fell", "sales increased", "बिक्री कम", "बिक्री बढ़", "विक्री कमी", "विक्री वाढ"]):
        return "sales_anomalies", multiplier
    if _contains_any(t, ["store performance", "how is pune store", "how is mumbai store", "how is nashik store", "स्टोर प्रदर्शन", "स्टोअर कामगिरी"]):
        return "store_performance", multiplier
    if _contains_any(t, ["performance", "how is", "how did", "this month", "प्रोडक्ट प्रदर्शन", "प्रॉडक्ट कामगिरी"]):
        return "product_performance", multiplier
    if _contains_any(t, ["today", "attention", "focus", "priority", "worry", "आज", "लक्ष", "ध्यान"]):
        return "dashboard_attention", multiplier
    return "unknown", multiplier
