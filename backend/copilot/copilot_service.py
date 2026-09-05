from __future__ import annotations

from functools import cached_property

from backend.copilot.context_builder import build_grounded_context
from backend.copilot.entity_extractor import resolve_entities
from backend.copilot.intent_router import route_intent
from backend.copilot.llm import GeminiService, GeminiUnavailable
from backend.copilot.tool_router import ToolRouter
from backend.explainability.explanation_engine import numeric_guard
from backend.explainability.uncertainty import collect_unknowns
from backend.multilingual.language_detector import detect_language
from backend.multilingual.response_localizer import localize_fallback
from backend.services.analytics_service import AnalyticsService


class CopilotService:
    def __init__(self):
        self.analytics = AnalyticsService()
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
        language = detect_language(message, preferred_language)
        entity = resolve_entities(
            message,
            self.analytics.context.products,
            self.analytics.context.stores,
            explicit_store_id=explicit_store_id,
            explicit_product_id=explicit_product_id,
        )

        if entity.ambiguous_products or entity.ambiguous_stores:
            return self._clarification_for_ambiguity(language, entity)

        intent, demand_multiplier = route_intent(message)
        store_id = entity.store_id
        product_id = entity.product_id
        intent_mode = "deterministic"
        gemini_notes: list[str] = []

        # Gemini is used only to resolve an otherwise unknown request. Strong
        # deterministic routes stay deterministic to reduce latency and preserve
        # predictable tool selection.
        if intent == "unknown" and self.gemini.status().configured:
            try:
                parsed = self.gemini.classify_intent(
                    message=message,
                    language=language,
                    catalogs=self.catalogs,
                )
                intent = parsed.intent
                language = parsed.language or language
                if parsed.store_id:
                    store_id = parsed.store_id
                if parsed.product_id:
                    product_id = parsed.product_id
                if parsed.demand_multiplier is not None:
                    demand_multiplier = parsed.demand_multiplier
                intent_mode = "gemini_structured_intent"
            except GeminiUnavailable as exc:
                gemini_notes.append(str(exc))

        tool_result = self.tools.execute(
            intent=intent,
            store_id=store_id,
            product_id=product_id,
            demand_multiplier=demand_multiplier,
        )

        if tool_result.status in {"needs_clarification", "not_found", "unsupported"}:
            return {
                "status": tool_result.status,
                "mode": "deterministic_guardrail",
                "intent": intent,
                "language": language,
                "entities": {"store_id": store_id, "product_id": product_id},
                "answer": tool_result.message
                or localize_fallback("unknown", None, language),
                "tool": tool_result.tool,
                "evidence": [],
                "unknowns": [],
                "gemini_notes": gemini_notes,
                "human_review_required": True,
            }

        unknowns = collect_unknowns(intent, tool_result.payload)
        fact_packet, fact_table = build_grounded_context(intent, tool_result.payload, unknowns)
        answer = localize_fallback(intent, tool_result.payload, language, unknowns)
        response_mode = "deterministic_fallback"
        human_action = None

        # One optional Gemini call produces a grounded explanation after the
        # deterministic tool has finished. It never gets authority to execute or
        # calculate the retail decision.
        if self.gemini.status().configured:
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
                    human_action = narrative.human_action
                    unknowns = list(dict.fromkeys(unknowns + narrative.unknowns))
                else:
                    if not guard_ok:
                        gemini_notes.append(
                            "Gemini narrative was rejected because it introduced unsupported numeric values: "
                            + ", ".join(unexpected_numbers)
                        )
                    if not refs_ok:
                        gemini_notes.append("Gemini narrative was rejected because it cited unknown fact IDs.")
            except GeminiUnavailable as exc:
                gemini_notes.append(str(exc))

        citations = fact_packet.get("citations", [])
        human_review_required = bool(unknowns) or intent in {
            "decision_compare",
            "demand_shock",
            "smart_transfer",
            "causal_explanation",
        }

        return {
            "status": tool_result.status,
            "mode": response_mode,
            "intent_mode": intent_mode,
            "intent": intent,
            "language": language,
            "entities": {
                "store_id": store_id,
                "product_id": product_id,
                "demand_multiplier": demand_multiplier,
            },
            "answer": answer,
            "tool": tool_result.tool,
            "data": tool_result.payload,
            "evidence": citations,
            "unknowns": unknowns,
            "human_action": human_action,
            "human_review_required": human_review_required,
            "gemini_notes": gemini_notes,
            "safeguards": {
                "llm_calculates_metrics": False,
                "llm_executes_actions": False,
                "unsupported_numbers_rejected": True,
                "causal_inference_without_evidence": False,
            },
        }

    @staticmethod
    def _clarification_for_ambiguity(language: str, entity) -> dict:
        if entity.ambiguous_products:
            choices = ", ".join(
                f"{item['product_id']} {item['product_name']}" for item in entity.ambiguous_products[:8]
            )
            answer = {
                "en": f"That product reference is ambiguous. Please choose one: {choices}.",
                "hi": f"à¤ªà¥à¤°à¥‹à¤¡à¤•à¥à¤Ÿ à¤•à¤¾ à¤¸à¤‚à¤¦à¤°à¥à¤­ à¤…à¤¸à¥à¤ªà¤·à¥à¤Ÿ à¤¹à¥ˆà¥¤ à¤‡à¤¨à¤®à¥‡à¤‚ à¤¸à¥‡ à¤à¤• à¤šà¥à¤¨à¥‡à¤‚: {choices}à¥¤",
                "mr": f"à¤ªà¥à¤°à¥‰à¤¡à¤•à¥à¤Ÿ à¤¸à¤‚à¤¦à¤°à¥à¤­ à¤…à¤¸à¥à¤ªà¤·à¥à¤Ÿ à¤†à¤¹à¥‡. à¤¯à¤¾à¤ªà¥ˆà¤•à¥€ à¤à¤• à¤¨à¤¿à¤µà¤¡à¤¾: {choices}.",
            }[language]
        else:
            choices = ", ".join(
                f"{item['store_id']} {item['store_name']}" for item in entity.ambiguous_stores[:8]
            )
            answer = {
                "en": f"That store reference is ambiguous. Please choose one: {choices}.",
                "hi": f"à¤¸à¥à¤Ÿà¥‹à¤° à¤•à¤¾ à¤¸à¤‚à¤¦à¤°à¥à¤­ à¤…à¤¸à¥à¤ªà¤·à¥à¤Ÿ à¤¹à¥ˆà¥¤ à¤‡à¤¨à¤®à¥‡à¤‚ à¤¸à¥‡ à¤à¤• à¤šà¥à¤¨à¥‡à¤‚: {choices}à¥¤",
                "mr": f"à¤¸à¥à¤Ÿà¥‹à¤…à¤° à¤¸à¤‚à¤¦à¤°à¥à¤­ à¤…à¤¸à¥à¤ªà¤·à¥à¤Ÿ à¤†à¤¹à¥‡. à¤¯à¤¾à¤ªà¥ˆà¤•à¥€ à¤à¤• à¤¨à¤¿à¤µà¤¡à¤¾: {choices}.",
            }[language]

        return {
            "status": "needs_clarification",
            "mode": "deterministic_guardrail",
            "intent": "unknown",
            "language": language,
            "entities": {"store_id": entity.store_id, "product_id": entity.product_id},
            "answer": answer,
            "candidates": {
                "products": entity.ambiguous_products,
                "stores": entity.ambiguous_stores,
            },
            "evidence": [],
            "unknowns": [],
            "human_review_required": True,
        }
