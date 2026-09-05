from __future__ import annotations

from typing import Any


def _fmt(value: Any, decimals: int = 2) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, float):
        return f"{value:.{decimals}f}".rstrip("0").rstrip(".")
    return str(value)


def _first(items: list[dict]) -> dict | None:
    return items[0] if items else None


def localize_fallback(intent: str, payload: Any, language: str, unknowns: list[str] | None = None) -> str:
    """Deterministic multilingual fallback used when Gemini is unavailable/fails."""

    unknowns = unknowns or []
    lang = language if language in {"en", "hi", "mr"} else "en"

    if intent == "stockout_risk":
        item = _first(payload if isinstance(payload, list) else [])
        if not item:
            return {
                "en": "No matching stock-out risk record was found in the available data.",
                "hi": "उपलब्ध डेटा में कोई मिलान करने वाला स्टॉक-आउट जोखिम रिकॉर्ड नहीं मिला।",
                "mr": "उपलब्ध डेटामध्ये जुळणारी स्टॉक-आउट जोखीम नोंद सापडली नाही.",
            }[lang]
        if item.get("risk") == "unknown":
            field_text = ", ".join(item.get("unknown_fields") or ["required fields"])
            return {
                "en": f"I cannot calculate a reliable recommendation for {item['product_name']} at {item['store_name']} because {field_text} is missing. I will not guess.",
                "hi": f"{item['store_name']} में {item['product_name']} के लिए भरोसेमंद सिफारिश नहीं दी जा सकती क्योंकि {field_text} उपलब्ध नहीं है। मैं अनुमान नहीं लगाऊंगा।",
                "mr": f"{item['store_name']} मधील {item['product_name']} साठी विश्वासार्ह शिफारस देता येत नाही कारण {field_text} उपलब्ध नाही. मी अंदाज लावणार नाही.",
            }[lang]
        return {
            "en": (
                f"{item['product_name']} at {item['store_name']} has {_fmt(item['current_stock'])} units in stock. "
                f"Recent average demand is {_fmt(item['avg_daily_sales'])} units/day, giving {_fmt(item['days_cover'])} days of cover versus a {_fmt(item['lead_time_days'])}-day supplier lead time. "
                f"Risk is {str(item['risk']).upper()}. Recommended reorder quantity: {_fmt(item['recommended_reorder_qty'])} units."
            ),
            "hi": (
                f"{item['store_name']} में {item['product_name']} का मौजूदा स्टॉक {_fmt(item['current_stock'])} यूनिट है। "
                f"हाल की औसत मांग {_fmt(item['avg_daily_sales'])} यूनिट/दिन है, इसलिए स्टॉक कवरेज {_fmt(item['days_cover'])} दिन है जबकि सप्लायर लीड टाइम {_fmt(item['lead_time_days'])} दिन है। "
                f"जोखिम {str(item['risk']).upper()} है। सुझाई गई रीऑर्डर मात्रा: {_fmt(item['recommended_reorder_qty'])} यूनिट।"
            ),
            "mr": (
                f"{item['store_name']} मध्ये {item['product_name']} चा सध्याचा स्टॉक {_fmt(item['current_stock'])} युनिट आहे. "
                f"अलीकडील सरासरी मागणी {_fmt(item['avg_daily_sales'])} युनिट/दिवस आहे, त्यामुळे स्टॉक कव्हर {_fmt(item['days_cover'])} दिवस आहे आणि सप्लायर लीड टाइम {_fmt(item['lead_time_days'])} दिवस आहे. "
                f"जोखीम {str(item['risk']).upper()} आहे. सुचवलेली रीऑर्डर मात्रा: {_fmt(item['recommended_reorder_qty'])} युनिट."
            ),
        }[lang]

    if intent == "overstock":
        item = _first(payload if isinstance(payload, list) else [])
        if not item:
            return {"en": "No matching overstock finding was found.", "hi": "कोई मिलान करने वाला ओवरस्टॉक निष्कर्ष नहीं मिला।", "mr": "जुळणारा ओव्हरस्टॉक निष्कर्ष सापडला नाही."}[lang]
        return {
            "en": f"{item['product_name']} at {item['store_name']} has {_fmt(item['current_stock'])} units and about {_fmt(item['days_cover'])} days of cover. Severity: {str(item['severity']).upper()}. {item['reason']}",
            "hi": f"{item['store_name']} में {item['product_name']} का स्टॉक {_fmt(item['current_stock'])} यूनिट है और लगभग {_fmt(item['days_cover'])} दिनों का कवरेज है। स्थिति: {str(item['severity']).upper()}।",
            "mr": f"{item['store_name']} मध्ये {item['product_name']} चा स्टॉक {_fmt(item['current_stock'])} युनिट आहे आणि सुमारे {_fmt(item['days_cover'])} दिवसांचे कव्हर आहे. स्थिती: {str(item['severity']).upper()}.",
        }[lang]

    if intent == "slow_movers":
        items = payload if isinstance(payload, list) else []
        if not items:
            return {"en": "No slow-moving items match the request.", "hi": "कोई धीमी बिक्री वाला मिलान करने वाला आइटम नहीं मिला।", "mr": "जुळणारा स्लो-मूव्हिंग आयटम सापडला नाही."}[lang]
        names = ", ".join(i.get("product_name", i.get("product_id", "item")) for i in items[:5])
        return {"en": f"Slow-moving items needing attention include: {names}.", "hi": f"धीमी बिक्री वाले प्रमुख आइटम: {names}।", "mr": f"लक्ष देण्यासारखे स्लो-मूव्हिंग आयटम: {names}."}[lang]

    if intent == "sales_anomalies":
        item = _first(payload if isinstance(payload, list) else [])
        if not item:
            return {"en": "No matching sales spike or drop was detected.", "hi": "कोई मिलान करने वाला बिक्री स्पाइक या ड्रॉप नहीं मिला।", "mr": "जुळणारा विक्री स्पाइक किंवा ड्रॉप आढळला नाही."}[lang]
        return {
            "en": f"{item['product_name']} at {item['store_name']} shows a {item['anomaly_type']} of {_fmt(item['percentage_change'])}% versus its prior baseline. Recent average: {_fmt(item['recent_avg_daily_sales'])}/day; baseline: {_fmt(item['baseline_avg_daily_sales'])}/day.",
            "hi": f"{item['store_name']} में {item['product_name']} की बिक्री में पिछले बेसलाइन की तुलना में {_fmt(item['percentage_change'])}% का {item['anomaly_type']} है। हाल का औसत {_fmt(item['recent_avg_daily_sales'])}/दिन और बेसलाइन {_fmt(item['baseline_avg_daily_sales'])}/दिन है।",
            "mr": f"{item['store_name']} मध्ये {item['product_name']} च्या विक्रीत आधीच्या बेसलाइनच्या तुलनेत {_fmt(item['percentage_change'])}% {item['anomaly_type']} आहे. अलीकडील सरासरी {_fmt(item['recent_avg_daily_sales'])}/दिवस आणि बेसलाइन {_fmt(item['baseline_avg_daily_sales'])}/दिवस आहे.",
        }[lang]

    if intent == "smart_transfer":
        item = _first(payload if isinstance(payload, list) else [])
        if not item:
            return {"en": "No safe inter-store transfer recommendation matches the request.", "hi": "कोई सुरक्षित इंटर-स्टोर ट्रांसफर सिफारिश नहीं मिली।", "mr": "सुरक्षित इंटर-स्टोअर ट्रान्सफर शिफारस सापडली नाही."}[lang]
        return {
            "en": f"Recommended transfer: {_fmt(item['recommended_transfer_quantity'])} units of {item['product_name']} from {item['recommended_source_store_name']} to {item['recipient_store_name']}. Recipient cover rises from {_fmt(item['recipient_days_cover'])} to {_fmt(item['recipient_after_days_cover'])} days while the donor remains at {_fmt(item['donor_after_days_cover'])} days of cover.",
            "hi": f"सुझाव: {item['product_name']} की {_fmt(item['recommended_transfer_quantity'])} यूनिट {item['recommended_source_store_name']} से {item['recipient_store_name']} भेजें। रिसीविंग स्टोर का कवरेज {_fmt(item['recipient_days_cover'])} से बढ़कर {_fmt(item['recipient_after_days_cover'])} दिन होगा और डोनर के पास {_fmt(item['donor_after_days_cover'])} दिन का कवरेज रहेगा।",
            "mr": f"शिफारस: {item['product_name']} चे {_fmt(item['recommended_transfer_quantity'])} युनिट {item['recommended_source_store_name']} येथून {item['recipient_store_name']} येथे ट्रान्सफर करा. रिसीव्हिंग स्टोअरचे कव्हर {_fmt(item['recipient_days_cover'])} वरून {_fmt(item['recipient_after_days_cover'])} दिवस होईल आणि डोनरकडे {_fmt(item['donor_after_days_cover'])} दिवसांचे कव्हर राहील.",
        }[lang]

    if intent in {"decision_compare", "demand_shock"} and isinstance(payload, dict):
        if payload.get("status") == "insufficient_data":
            missing = ", ".join(payload.get("unknown_fields") or unknowns or ["required data"])
            return {
                "en": f"I cannot run this what-if reliably because {missing} is missing. No scenario recommendation was generated.",
                "hi": f"यह what-if विश्लेषण भरोसेमंद तरीके से नहीं चल सकता क्योंकि {missing} उपलब्ध नहीं है। कोई परिदृश्य सिफारिश नहीं बनाई गई।",
                "mr": f"हे what-if विश्लेषण विश्वासार्हपणे चालवता येत नाही कारण {missing} उपलब्ध नाही. कोणतीही परिदृश्य शिफारस तयार केली नाही.",
            }[lang]
        comp = payload.get("comparison") or {}
        state = payload.get("current_state") or {}
        return {
            "en": f"Decision Twin recommends {comp.get('recommendation', 'no action')} for {payload.get('product_name')} at {payload.get('store_name')}. Current cover is {_fmt(state.get('days_cover'))} days. This ranking is deterministic and compares service protection, unserved demand, operating loss, execution cost, and cash commitment.",
            "hi": f"Decision Twin {payload.get('store_name')} में {payload.get('product_name')} के लिए {comp.get('recommendation', 'no action')} की सिफारिश करता है। मौजूदा स्टॉक कवरेज {_fmt(state.get('days_cover'))} दिन है। यह रैंकिंग deterministic है।",
            "mr": f"Decision Twin {payload.get('store_name')} मधील {payload.get('product_name')} साठी {comp.get('recommendation', 'no action')} ची शिफारस करतो. सध्याचे स्टॉक कव्हर {_fmt(state.get('days_cover'))} दिवस आहे. ही रँकिंग deterministic आहे.",
        }[lang]

    if intent == "financial_summary" and isinstance(payload, dict):
        stockout = payload.get("stockout_exposure", {})
        over = payload.get("overstock_exposure", {})
        return {
            "en": f"Estimated revenue at risk from stockouts is ₹{_fmt(stockout.get('revenue_at_risk'))}. Estimated capital blocked in excess inventory at cost is ₹{_fmt(over.get('blocked_capital_at_cost'))}. These are deterministic scenario estimates, not live quotes.",
            "hi": f"स्टॉक-आउट से अनुमानित राजस्व जोखिम ₹{_fmt(stockout.get('revenue_at_risk'))} है। अतिरिक्त इन्वेंट्री में लागत पर फंसी अनुमानित पूंजी ₹{_fmt(over.get('blocked_capital_at_cost'))} है। ये deterministic अनुमान हैं, लाइव कोट नहीं।",
            "mr": f"स्टॉक-आउटमुळे अंदाजित महसूल जोखीम ₹{_fmt(stockout.get('revenue_at_risk'))} आहे. अतिरिक्त इन्व्हेंटरीमध्ये खर्चावर अडकलेले अंदाजित भांडवल ₹{_fmt(over.get('blocked_capital_at_cost'))} आहे. हे deterministic अंदाज आहेत, लाइव्ह कोट नाहीत.",
        }[lang]

    if intent == "causal_explanation":
        base = {
            "en": "The available retail data can show what changed, but it does not contain promotion, competitor, weather, or customer-behaviour evidence needed to prove why the change happened. I will not invent a cause.",
            "hi": "उपलब्ध रिटेल डेटा यह दिखा सकता है कि क्या बदला, लेकिन इसमें प्रमोशन, प्रतियोगी, मौसम या ग्राहक-व्यवहार का ऐसा प्रमाण नहीं है जिससे कारण साबित हो सके। मैं कारण का अनुमान नहीं लगाऊंगा।",
            "mr": "उपलब्ध रिटेल डेटा काय बदलले ते दाखवू शकतो, पण प्रमोशन, स्पर्धक, हवामान किंवा ग्राहक-वर्तनाचा पुरावा नसल्यामुळे बदलाचे कारण सिद्ध करता येत नाही. मी कारणाचा अंदाज लावणार नाही.",
        }[lang]
        item = _first(payload.get("anomalies", []) if isinstance(payload, dict) else [])
        if item:
            if lang == "en":
                return f"{item['product_name']} shows a {item['anomaly_type']} of {_fmt(item['percentage_change'])}% versus the prior baseline. " + base
            if lang == "hi":
                return f"{item['product_name']} में पिछले बेसलाइन की तुलना में {_fmt(item['percentage_change'])}% का {item['anomaly_type']} दिखता है। " + base
            return f"{item['product_name']} मध्ये आधीच्या बेसलाइनच्या तुलनेत {_fmt(item['percentage_change'])}% {item['anomaly_type']} दिसतो. " + base
        return base

    if intent == "dashboard_attention" and isinstance(payload, dict):
        inv = payload.get("inventory", {})
        so = inv.get("stockout_risk", {})
        an = payload.get("sales_anomalies", {})
        return {
            "en": f"Today's data shows {so.get('critical', 0)} critical stockout risks, {so.get('high', 0)} high risks, {inv.get('slow_movers', 0)} slow movers, {an.get('spike', 0)} sales spikes, and {an.get('drop', 0)} sales drops. Review the highest-priority attention items first.",
            "hi": f"आज के डेटा में {so.get('critical', 0)} critical स्टॉक-आउट जोखिम, {so.get('high', 0)} high जोखिम, {inv.get('slow_movers', 0)} slow movers, {an.get('spike', 0)} sales spikes और {an.get('drop', 0)} sales drops हैं। पहले सबसे उच्च प्राथमिकता वाले आइटम देखें।",
            "mr": f"आजच्या डेटामध्ये {so.get('critical', 0)} critical स्टॉक-आउट जोखीम, {so.get('high', 0)} high जोखीम, {inv.get('slow_movers', 0)} slow movers, {an.get('spike', 0)} sales spikes आणि {an.get('drop', 0)} sales drops आहेत. आधी सर्वाधिक प्राधान्याच्या आयटमकडे लक्ष द्या.",
        }[lang]

    if intent == "product_performance" and isinstance(payload, dict):
        cur = payload.get("current", {})
        chg = payload.get("change", {})
        return {
            "en": f"{payload.get('product_name')} sold {_fmt(cur.get('units_sold'))} units and generated ₹{_fmt(cur.get('revenue'))} in the current {payload.get('period', {}).get('days', 30)}-day period. Unit sales changed {_fmt(chg.get('units_percent'))}% versus the previous period.",
            "hi": f"{payload.get('product_name')} ने मौजूदा {payload.get('period', {}).get('days', 30)} दिनों में {_fmt(cur.get('units_sold'))} यूनिट बेचीं और ₹{_fmt(cur.get('revenue'))} राजस्व बनाया। पिछले पीरियड की तुलना में यूनिट बिक्री {_fmt(chg.get('units_percent'))}% बदली।",
            "mr": f"{payload.get('product_name')} ने सध्याच्या {payload.get('period', {}).get('days', 30)} दिवसांत {_fmt(cur.get('units_sold'))} युनिट विकले आणि ₹{_fmt(cur.get('revenue'))} महसूल केला. मागील कालावधीच्या तुलनेत युनिट विक्री {_fmt(chg.get('units_percent'))}% बदलली.",
        }[lang]

    if intent == "store_performance" and isinstance(payload, dict):
        current = payload.get("current", {})
        return {
            "en": f"{payload.get('store_name')} generated ₹{_fmt(current.get('revenue'))} revenue and sold {_fmt(current.get('units_sold'))} units in the current period.",
            "hi": f"{payload.get('store_name')} ने मौजूदा अवधि में ₹{_fmt(current.get('revenue'))} राजस्व और {_fmt(current.get('units_sold'))} यूनिट बिक्री की।",
            "mr": f"{payload.get('store_name')} ने सध्याच्या कालावधीत ₹{_fmt(current.get('revenue'))} महसूल आणि {_fmt(current.get('units_sold'))} युनिट विक्री केली.",
        }[lang]

    return {
        "en": "I could not map that request to a supported RetailIQ analysis without guessing. Try asking about stock-out risk, overstock, slow movers, sales changes, store/product performance, transfers, financial impact, or a what-if scenario.",
        "hi": "मैं इस अनुरोध को बिना अनुमान लगाए किसी समर्थित RetailIQ विश्लेषण से नहीं जोड़ सका। स्टॉक-आउट, ओवरस्टॉक, धीमी बिक्री, बिक्री बदलाव, स्टोर/प्रोडक्ट प्रदर्शन, ट्रांसफर, वित्तीय प्रभाव या what-if के बारे में पूछें।",
        "mr": "अंदाज न लावता हा प्रश्न समर्थित RetailIQ विश्लेषणाशी जोडता आला नाही. स्टॉक-आउट, ओव्हरस्टॉक, स्लो मूव्हर्स, विक्री बदल, स्टोअर/प्रॉडक्ट कामगिरी, ट्रान्सफर, आर्थिक परिणाम किंवा what-if बद्दल विचारा.",
    }[lang]
