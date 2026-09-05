from __future__ import annotations

from functools import cached_property
import math
import re
from time import perf_counter

from backend.copilot.context_builder import build_grounded_context
from backend.copilot.entity_extractor import resolve_entities
from backend.copilot.intent_router import route_intent, unsupported_fact_override
from backend.copilot.llm import GeminiService
from backend.copilot.response_builder import structured_sections
from backend.copilot.tool_router import ToolRouter
from backend.explainability.explanation_engine import numeric_guard
from backend.explainability.uncertainty import collect_unknowns
from backend.multilingual.language_detector import detect_language
from backend.multilingual.response_localizer import localize_fallback
from backend.services.analytics_service import AnalyticsService


class CopilotService:
    def __init__(self, analytics: AnalyticsService | None = None):
        self.analytics = analytics or AnalyticsService()
        self.tools = ToolRouter(analytics=self.analytics)
        self.gemini = GeminiService()

    @cached_property
    def catalogs(self) -> dict:
        ctx = self.analytics.context
        return {
            "stores": [
                {
                    "store_id": str(row.store_id),
                    "store_name": str(row.store_name),
                    "city": str(row.city),
                }
                for row in ctx.stores.itertuples(index=False)
            ],
            "products": [
                {
                    "product_id": str(row.product_id),
                    "product_name": str(row.product_name),
                    "category": str(row.category),
                }
                for row in ctx.products.itertuples(index=False)
            ],
        }

    def status(self) -> dict:
        status = self.gemini.status()
        return {
            "status": "ok",
            "gemini_configured": status.configured,
            "google_genai_installed": status.dependency_available,
            "model": status.model,
            "supported_languages": ["en", "hi", "mr"],
            "startup_network_calls": False,
            "fallback": "deterministic multilingual response",
            "principle": "Gemini handles language/explanation; Python owns all retail facts, calculations, simulations and recommendations.",
        }

    def ask(
        self,
        *,
        message: str,
        preferred_language: str | None = None,
        explicit_store_id: str | None = None,
        explicit_product_id: str | None = None,
    ) -> dict:
        started = perf_counter()
        gemini_seconds = 0.0
        gemini_used = False
        numeric_guard_passed = True
        gemini_status = self.gemini.status()
        language = detect_language(message, preferred_language)
        intent, demand_multiplier = route_intent(message)
        routing_confidence = "high" if intent != "unknown" else "low"
        entity = resolve_entities(
            message,
            self.analytics.context.products,
            self.analytics.context.stores,
            explicit_store_id=explicit_store_id,
            explicit_product_id=explicit_product_id,
        )
        store_id = entity.store_id
        product_id = entity.product_id
        intent_mode = "deterministic"
        gemini_notes: list[str] = []

        def finish(response: dict) -> dict:
            return self._finalize_response(
                response,
                started=started,
                gemini_seconds=gemini_seconds,
                gemini_used=gemini_used,
                numeric_guard_passed=numeric_guard_passed,
                configured_model=gemini_status.model,
                routing_confidence=routing_confidence,
            )

        if unsupported_fact_override(message):
            return finish(self._fact_override_guardrail(language, intent, entity))

        if entity.unknown_products or entity.unknown_stores:
            return finish(self._not_found_for_entities(language, intent, entity))

        if entity.ambiguous_products or entity.ambiguous_stores:
            return finish(self._clarification_for_ambiguity(language, entity, intent))

        # A quantity is store-specific. Asking for one exact reorder number
        # without both entities would silently combine unlike inventory records.
        if self._is_reorder_quantity_request(message) and (not store_id or not product_id):
            missing = []
            if not product_id:
                missing.append("product")
            if not store_id:
                missing.append("store")
            answer = self._localized_scope_request(language, missing)
            return finish({
                "status": "needs_clarification",
                "mode": "deterministic_guardrail",
                "intent_mode": intent_mode,
                "intent": intent,
                "language": language,
                "entities": self._entities(entity, demand_multiplier),
                "answer": answer,
                "tool": "entity.resolve",
                "data": None,
                "evidence": [],
                "unknowns": missing,
                "gemini_notes": [],
                "human_review_required": True,
                "candidates": {"products": [], "stores": []},
            })

        # Gemini is used only to resolve an otherwise unknown request. Strong
        # deterministic routes stay deterministic to reduce latency and preserve
        # predictable tool selection.
        if intent == "unknown" and gemini_status.configured:
            gemini_started = perf_counter()
            try:
                parsed = self.gemini.classify_intent(
                    message=message,
                    language=language,
                    catalogs=self.catalogs,
                )
                intent = parsed.intent
                if preferred_language is None and parsed.language:
                    language = parsed.language
                valid_stores = {item["store_id"] for item in self.catalogs["stores"]}
                valid_products = {item["product_id"] for item in self.catalogs["products"]}
                if not store_id and parsed.store_id in valid_stores:
                    store_id = parsed.store_id
                elif parsed.store_id and parsed.store_id not in valid_stores:
                    gemini_notes.append("Gemini returned a store ID outside the selected catalog; it was ignored.")
                if not product_id and parsed.product_id in valid_products:
                    product_id = parsed.product_id
                elif parsed.product_id and parsed.product_id not in valid_products:
                    gemini_notes.append("Gemini returned a product ID outside the selected catalog; it was ignored.")
                if parsed.demand_multiplier is not None and math.isfinite(parsed.demand_multiplier):
                    demand_multiplier = parsed.demand_multiplier
                intent_mode = "gemini_structured_intent"
                gemini_used = True
                routing_confidence = "high" if parsed.confidence >= 0.8 else "medium" if parsed.confidence >= 0.5 else "low"
            except Exception as exc:
                gemini_notes.append(f"Gemini intent classification failed safely: {type(exc).__name__}.")
            finally:
                gemini_seconds += perf_counter() - gemini_started

        tool_result = self.tools.execute(
            intent=intent,
            store_id=store_id,
            product_id=product_id,
            demand_multiplier=demand_multiplier,
            source_store_id=entity.source_store_id,
        )

        if isinstance(tool_result.payload, dict) and self._is_no_action_question(message):
            tool_result.payload["requested_scenario_id"] = "no_action"

        if tool_result.status in {"needs_clarification", "not_found", "unsupported"}:
            return finish({
                "status": tool_result.status,
                "mode": "deterministic_guardrail",
                "intent_mode": intent_mode,
                "intent": intent,
                "language": language,
                "entities": {
                    "store_id": store_id,
                    "source_store_id": entity.source_store_id,
                    "product_id": product_id,
                    "demand_multiplier": demand_multiplier,
                },
                "answer": tool_result.message
                or localize_fallback("unknown", None, language),
                "tool": tool_result.tool,
                "data": tool_result.payload,
                "evidence": [],
                "unknowns": [],
                "gemini_notes": gemini_notes,
                "human_review_required": True,
                "candidates": {"products": [], "stores": []},
            })

        unknowns = collect_unknowns(intent, tool_result.payload)
        fact_packet, fact_table = build_grounded_context(intent, tool_result.payload, unknowns)
        answer = localize_fallback(intent, tool_result.payload, language, unknowns)
        response_mode = "deterministic_fallback"
        human_action = None

        # One optional Gemini call produces a grounded explanation after the
        # deterministic tool has finished. It never gets authority to execute or
        # calculate the retail decision.
        # Causal and insufficient-data answers stay fully deterministic because
        # unsupported qualitative claims cannot be caught by a numeric guard.
        if gemini_status.configured and tool_result.status == "ok" and intent != "causal_explanation":
            gemini_started = perf_counter()
            try:
                narrative = self.gemini.grounded_narrative(
                    language=language,
                    user_message=message,
                    fact_packet=fact_packet,
                    fact_table=fact_table,
                )
                guard_ok, unexpected_numbers = numeric_guard(narrative.answer, fact_table, tool_result.payload)
                valid_fact_ids = {f["fact_id"] for f in fact_table}
                refs_ok = all(fid in valid_fact_ids for fid in narrative.used_fact_ids)
                if guard_ok and refs_ok:
                    answer = narrative.answer
                    response_mode = "gemini_grounded"
                    gemini_used = True
                    unknowns = list(dict.fromkeys(unknowns + narrative.unknowns))
                else:
                    numeric_guard_passed = False
                    if not guard_ok:
                        gemini_notes.append(
                            "Gemini narrative was rejected because it introduced unsupported numeric values: "
                            + ", ".join(unexpected_numbers)
                        )
                    if not refs_ok:
                        gemini_notes.append("Gemini narrative was rejected because it cited unknown fact IDs.")
            except Exception as exc:
                gemini_notes.append(f"Gemini explanation failed safely: {type(exc).__name__}.")
            finally:
                gemini_seconds += perf_counter() - gemini_started

        citations = fact_packet.get("citations", [])
        human_review_required = bool(unknowns) or intent in {
            "decision_compare",
            "demand_shock",
            "smart_transfer",
            "causal_explanation",
        }

        return finish({
            "status": tool_result.status,
            "mode": response_mode,
            "intent_mode": intent_mode,
            "intent": intent,
            "language": language,
            "entities": {
                "store_id": store_id,
                "source_store_id": entity.source_store_id,
                "product_id": product_id,
                "demand_multiplier": demand_multiplier,
                "requested_scenario_id": tool_result.payload.get("requested_scenario_id") if isinstance(tool_result.payload, dict) else None,
            },
            "answer": answer,
            "tool": tool_result.tool,
            "data": tool_result.payload,
            "evidence": citations,
            "unknowns": unknowns,
            # Human actions always come from deterministic Python sections, not
            # from the optional Gemini narrative.
            "human_action": human_action,
            "human_review_required": human_review_required,
            "gemini_notes": gemini_notes,
            "safeguards": {
                "llm_calculates_metrics": False,
                "llm_executes_actions": False,
                "unsupported_numbers_rejected": True,
                "causal_inference_without_evidence": False,
                "fact_reference_validation": True,
                "user_fact_overrides_allowed": False,
            },
            "candidates": {"products": [], "stores": []},
        })

    @staticmethod
    def _entities(entity, demand_multiplier: float | None) -> dict:
        return {
            "store_id": entity.store_id,
            "source_store_id": entity.source_store_id,
            "product_id": entity.product_id,
            "demand_multiplier": demand_multiplier,
        }

    @staticmethod
    def _finalize_response(
        response: dict,
        *,
        started: float,
        gemini_seconds: float,
        gemini_used: bool,
        numeric_guard_passed: bool,
        configured_model: str,
        routing_confidence: str,
    ) -> dict:
        sections = structured_sections(
            response.get("intent", "unknown"),
            response.get("data"),
            response.get("status", "unsupported"),
            response.get("answer", ""),
        )
        for key, value in sections.items():
            response.setdefault(key, value)
        response["human_review_required"] = bool(
            response.get("human_review_required")
            or response["recommendation"].get("human_approval_required")
        )
        response.setdefault("clarification_required", response.get("status") == "needs_clarification")
        response.setdefault("candidates", {"products": [], "stores": []})
        response.setdefault("unknowns", [])
        response.setdefault("gemini_notes", [])
        response.setdefault("safeguards", {
            "llm_calculates_metrics": False,
            "llm_executes_actions": False,
            "unsupported_numbers_rejected": True,
            "causal_inference_without_evidence": False,
            "fact_reference_validation": True,
            "user_fact_overrides_allowed": False,
        })
        if response.get("human_action") is None and response["recommendation"].get("human_approval_required"):
            response["human_action"] = response["recommendation"].get("action")
        citations = response.get("evidence", [])
        source_records = sum(len(item.get("record_ids", [])) for item in citations if isinstance(item, dict))
        total_ms = round((perf_counter() - started) * 1000, 2)
        gemini_ms = round(gemini_seconds * 1000, 2) if gemini_seconds else None
        deterministic_ms = round(max(0.0, total_ms - (gemini_ms or 0.0)), 2)
        response["confidence"] = {
            "routing": routing_confidence,
            "basis": "Rule-based routing confidence, not statistical or forecast confidence.",
        }
        response["trace"] = {
            "route": response.get("intent", "unknown"),
            "tool": response.get("tool", "none"),
            "deterministic": True,
            "gemini_used": gemini_used,
            "gemini_attempted": gemini_ms is not None,
            "numeric_guard_passed": numeric_guard_passed,
            "model": configured_model if gemini_used else "deterministic_fallback",
            "configured_model": configured_model,
            "language": response.get("language", "en"),
            "source_records": source_records,
            "human_approval_required": bool(response.get("human_review_required")),
        }
        response["total_latency_ms"] = total_ms
        response["deterministic_latency_ms"] = deterministic_ms
        response["gemini_latency_ms"] = gemini_ms
        response["timing_ms"] = {
            "total": total_ms,
            "deterministic": deterministic_ms,
            "gemini": gemini_ms,
        }
        return response

    @staticmethod
    def _is_reorder_quantity_request(message: str) -> bool:
        text = " ".join(message.lower().split())
        return bool(re.search(r"reorder\s+(?:quantity|qty)|how many.+reorder|रीऑर्डर.+(?:मात्रा|कितन)|रीऑर्डर.+(?:प्रमाण|किती)", text))

    @staticmethod
    def _is_no_action_question(message: str) -> bool:
        text = " ".join(message.lower().split())
        return any(phrase in text for phrase in (
            "what happens if i do nothing",
            "if i do nothing",
            "अगर मैं कुछ न करूं",
            "मी काहीही केले नाही",
        ))

    @staticmethod
    def _localized_scope_request(language: str, missing: list[str]) -> str:
        fields = " and ".join(missing)
        return {
            "en": f"A specific {fields} is required for one reorder quantity. RetailIQ will not combine store-level recommendations.",
            "hi": f"एक रीऑर्डर मात्रा के लिए निश्चित {fields} जरूरी है। RetailIQ अलग-अलग स्टोर की सिफारिशों को नहीं मिलाएगा।",
            "mr": f"एका रीऑर्डर प्रमाणासाठी ठराविक {fields} आवश्यक आहे. RetailIQ वेगवेगळ्या स्टोअरच्या शिफारसी एकत्र करणार नाही.",
        }[language]

    @staticmethod
    def _fact_override_guardrail(language: str, intent: str, entity) -> dict:
        answer = {
            "en": "RetailIQ cannot replace database facts, configured costs, or deterministic recommendations with user-supplied values. Demand changes are accepted only through the supported what-if simulation.",
            "hi": "RetailIQ उपयोगकर्ता के दिए मान से डेटाबेस तथ्य, निर्धारित लागत या निश्चित सिफारिश नहीं बदलेगा। मांग में बदलाव केवल समर्थित what-if simulation में स्वीकार होता है।",
            "mr": "RetailIQ वापरकर्त्याने दिलेल्या आकड्यांनी डेटाबेसमधील तथ्ये, ठरवलेले खर्च किंवा निश्चित शिफारसी बदलणार नाही. मागणीतील बदल फक्त समर्थित what-if simulation मध्ये स्वीकारला जातो.",
        }[language]
        return {
            "status": "unsupported",
            "mode": "deterministic_guardrail",
            "intent_mode": "deterministic",
            "intent": intent,
            "language": language,
            "entities": CopilotService._entities(entity, None),
            "answer": answer,
            "tool": "safety.fact_override",
            "data": None,
            "evidence": [],
            "unknowns": [],
            "human_review_required": True,
            "candidates": {"products": [], "stores": []},
        }

    @staticmethod
    def _not_found_for_entities(language: str, intent: str, entity) -> dict:
        missing = entity.unknown_products + entity.unknown_stores
        values = ", ".join(missing)
        answer = {
            "en": f"No selected-dataset catalog match was found for: {values}. Provide an exact store or product name/ID.",
            "hi": f"चुने गए डेटासेट में इसका कैटलॉग मिलान नहीं मिला: {values}। सही स्टोर या प्रोडक्ट नाम/ID दें।",
            "mr": f"निवडलेल्या डेटासेटमध्ये यासाठी कॅटलॉग जुळणी सापडली नाही: {values}. अचूक स्टोअर किंवा प्रॉडक्ट नाव/ID द्या.",
        }[language]
        return {
            "status": "not_found",
            "mode": "deterministic_guardrail",
            "intent_mode": "deterministic",
            "intent": intent,
            "language": language,
            "entities": CopilotService._entities(entity, None),
            "answer": answer,
            "tool": "entity.resolve",
            "data": None,
            "evidence": [],
            "unknowns": [f"unknown catalog reference: {item}" for item in missing],
            "human_review_required": True,
            "candidates": {"products": [], "stores": []},
        }

    @staticmethod
    def _clarification_for_ambiguity(language: str, entity, intent: str = "unknown") -> dict:
        if entity.ambiguous_products:
            choices = ", ".join(
                f"{item['product_id']} {item['product_name']}" for item in entity.ambiguous_products[:8]
            )
            answer = {
                "en": f"That product reference is ambiguous. Please choose one: {choices}.",
                "hi": f"प्रोडक्ट का संदर्भ स्पष्ट नहीं है। इनमें से एक चुनें: {choices}।",
                "mr": f"प्रॉडक्टचा संदर्भ स्पष्ट नाही. यापैकी एक निवडा: {choices}.",
            }[language]
        else:
            choices = ", ".join(
                f"{item['store_id']} {item['store_name']}" for item in entity.ambiguous_stores[:8]
            )
            answer = {
                "en": f"That store reference is ambiguous. Please choose one: {choices}.",
                "hi": f"स्टोर का संदर्भ स्पष्ट नहीं है। इनमें से एक चुनें: {choices}।",
                "mr": f"स्टोअरचा संदर्भ स्पष्ट नाही. यापैकी एक निवडा: {choices}.",
            }[language]

        return {
            "status": "needs_clarification",
            "mode": "deterministic_guardrail",
            "intent_mode": "deterministic",
            "intent": intent,
            "language": language,
            "entities": CopilotService._entities(entity, None),
            "answer": answer,
            "tool": "entity.resolve",
            "data": None,
            "candidates": {
                "products": entity.ambiguous_products,
                "stores": entity.ambiguous_stores,
            },
            "evidence": [],
            "unknowns": [],
            "human_review_required": True,
            "clarification_required": True,
        }
