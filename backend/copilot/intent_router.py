from __future__ import annotations

import re


def _contains_any(text: str, phrases: list[str]) -> bool:
    return any(p in text for p in phrases)


def parse_demand_multiplier(text: str) -> float | None:
    lowered = text.lower()
    pct = re.search(r"(?:increase|increases|increased|up|वाढ|बढ़|बढ)[^\d]{0,20}(\d+(?:\.\d+)?)\s*%", lowered)
    if pct:
        return round(1 + float(pct.group(1)) / 100.0, 4)
    pct2 = re.search(r"(\d+(?:\.\d+)?)\s*%[^\n]{0,20}(?:increase|higher|more|वाढ|बढ़|बढ)", lowered)
    if pct2:
        return round(1 + float(pct2.group(1)) / 100.0, 4)
    mult = re.search(r"(\d+(?:\.\d+)?)\s*[x×]", lowered)
    if mult:
        value = float(mult.group(1))
        return value if 0 < value <= 5 else None
    return None


def route_intent(text: str) -> tuple[str, float | None]:
    t = " ".join((text or "").lower().split())
    multiplier = parse_demand_multiplier(t)

    causal = _contains_any(
        t,
        [
            "why did", "why has", "why are sales", "reason for", "cause of",
            "क्यों", "किस वजह", "का कारण", "क्यों कम", "क्यों बढ़",
            "का कमी", "का वाढ", "कारण काय", "का घसर", "का वाढली",
        ],
    )
    if causal:
        return "causal_explanation", multiplier

    if multiplier is not None and _contains_any(t, ["what if", "if demand", "demand", "मागणी", "मांग"]):
        return "demand_shock", multiplier

    if _contains_any(t, ["what if", "compare options", "compare reorder", "transfer vs", "best option", "what should i do", "काय करावे", "क्या करना चाहिए"]):
        return "decision_compare", multiplier

    if _contains_any(t, ["transfer", "reallocate", "move stock", "ट्रांसफर", "ट्रान्सफर", "स्टॉक हलवा"]):
        return "smart_transfer", multiplier

    if _contains_any(t, ["financial", "revenue at risk", "capital blocked", "money at risk", "₹", "पैसा", "पूंजी", "महसूल", "आर्थिक"]):
        return "financial_summary", multiplier

    if _contains_any(t, ["running out", "run out", "stockout", "stock-out", "low stock", "खत्म", "संपणार", "स्टॉक कमी", "स्टॉक खत्म"]):
        return "stockout_risk", multiplier

    if _contains_any(t, ["overstock", "too much stock", "excess stock", "ज्यादा स्टॉक", "जास्त स्टॉक", "ओव्हरस्टॉक", "ओवरस्टॉक"]):
        return "overstock", multiplier

    if _contains_any(t, ["slow mover", "slow-moving", "not selling", "not moving", "zero sales", "धीमी बिक्री", "नहीं बिक", "स्लो मूव्ह", "विकत नाही"]):
        return "slow_movers", multiplier

    if _contains_any(t, ["spike", "drop", "sales change", "sales changed", "sales anomaly", "sales fell", "sales increased", "बिक्री कम", "बिक्री बढ़", "विक्री कमी", "विक्री वाढ"]):
        return "sales_anomalies", multiplier

    if _contains_any(t, ["product performance", "how is", "how did", "this month", "performance of product", "प्रोडक्ट प्रदर्शन", "प्रॉडक्ट कामगिरी"]):
        return "product_performance", multiplier

    if _contains_any(t, ["store performance", "how is pune store", "how is mumbai store", "how is nashik store", "स्टोर प्रदर्शन", "स्टोअर कामगिरी"]):
        return "store_performance", multiplier

    if _contains_any(t, ["today", "attention", "focus", "priority", "needs attention", "आज", "लक्ष", "ध्यान"]):
        return "dashboard_attention", multiplier

    return "unknown", multiplier
