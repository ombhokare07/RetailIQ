import os

import pytest

from backend.copilot.copilot_service import CopilotService
from backend.copilot.entity_extractor import resolve_entities
from backend.copilot.intent_router import parse_demand_multiplier, route_intent
from backend.multilingual.language_detector import detect_language


@pytest.fixture(autouse=True)
def no_gemini_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


def test_language_detection_english_hindi_marathi():
    assert detect_language("Which products may run out?") == "en"
    assert detect_language("कौन से प्रोडक्ट खत्म होने वाले हैं?", "hi") == "hi"
    assert detect_language("पुणे स्टोअरमध्ये कोणते प्रॉडक्ट लवकर संपणार आहेत?", "mr") == "mr"


def test_demand_multiplier_parsing():
    assert parse_demand_multiplier("what if demand increases by 50%") == 1.5
    assert parse_demand_multiplier("what if demand is 2x") == 2.0


def test_intent_routes_causal_before_sales_drop():
    intent, _ = route_intent("Why did Brown Bread sales fall in Pune?")
    assert intent == "causal_explanation"


def test_exact_product_name_beats_ambiguous_bread_word():
    service = CopilotService()
    result = resolve_entities(
        "Why did Brown Bread sales fall in Pune?",
        service.analytics.context.products,
        service.analytics.context.stores,
    )
    assert result.product_id == "P006"
    assert result.store_id == "S001"
    assert not result.ambiguous_products


def test_ambiguous_product_returns_clarification():
    service = CopilotService()
    result = service.ask(message="How is bread doing this month in Pune?")
    assert result["status"] == "needs_clarification"
    assert len(result["candidates"]["products"]) >= 2
    assert "Brown Bread" in result["answer"]
    assert "White Bread" in result["answer"]


def test_stockout_query_returns_grounded_deterministic_fallback():
    service = CopilotService()
    result = service.ask(message="Which products may run out in Pune?")
    assert result["status"] == "ok"
    assert result["intent"] == "stockout_risk"
    assert result["mode"] == "deterministic_fallback"
    assert result["data"]
    assert result["data"][0]["store_id"] == "S001"
    assert result["safeguards"]["llm_calculates_metrics"] is False
    assert any(c["source"] == "data/raw/inventory.csv" for c in result["evidence"])


def test_marathi_stockout_query_localizes_without_gemini():
    service = CopilotService()
    result = service.ask(
        message="पुणे स्टोअरमध्ये कोणते प्रॉडक्ट लवकर संपणार आहेत?",
        preferred_language="mr",
    )
    assert result["language"] == "mr"
    assert result["intent"] == "stockout_risk"
    assert "स्टॉक" in result["answer"]


def test_causal_question_refuses_to_invent_reason():
    service = CopilotService()
    result = service.ask(message="Why did Brown Bread sales fall in Pune?")
    assert result["intent"] == "causal_explanation"
    assert result["data"]["causal_evidence_available"] is False
    assert "will not invent a cause" in result["answer"]
    assert "promotion/activity data" in result["unknowns"]
    assert result["human_review_required"] is True


def test_decision_compare_uses_deterministic_twin():
    service = CopilotService()
    result = service.ask(
        message="What should I do about Amul Milk in Pune: transfer, reorder, or wait?"
    )
    assert result["intent"] == "decision_compare"
    assert result["data"]["comparison"]["recommended_scenario_id"] == "smart_transfer"
    assert result["tool"] == "simulation.compare"


def test_demand_shock_query_parses_multiplier():
    service = CopilotService()
    result = service.ask(
        message="What if demand for Amul Milk in Pune increases by 50%?"
    )
    assert result["intent"] == "demand_shock"
    assert result["entities"]["demand_multiplier"] == 1.5
    assert result["data"]["demand_assumption"]["demand_multiplier"] == 1.5


def test_incomplete_product_does_not_get_guessed_reorder():
    service = CopilotService()
    result = service.ask(
        message="Will Kitchen Towels run out in Pune?",
        explicit_product_id="P049",
        explicit_store_id="S001",
    )
    assert result["intent"] == "stockout_risk"
    assert result["data"][0]["risk"] == "unknown"
    assert result["data"][0]["recommended_reorder_qty"] is None
    assert "reorder_level" in result["unknowns"]


def test_status_has_no_startup_network_dependency():
    status = CopilotService().status()
    assert status["startup_network_calls"] is False
    assert status["gemini_configured"] is False
    assert status["supported_languages"] == ["en", "hi", "mr"]


def test_mocked_gemini_grounded_answer_is_accepted():
    from types import SimpleNamespace
    from backend.copilot.schemas import GeminiNarrative

    class FakeGemini:
        def status(self):
            return SimpleNamespace(configured=True, dependency_available=True, model="fake")

        def grounded_narrative(self, **kwargs):
            return GeminiNarrative(
                answer="Amul Milk 1L has 18 units in stock and 2.5714 days of cover.",
                used_fact_ids=[],
                unknowns=[],
            )

    service = CopilotService()
    service.gemini = FakeGemini()
    result = service.ask(message="Will Amul Milk run out in Pune?")
    assert result["mode"] == "gemini_grounded"
    assert "18 units" in result["answer"]


def test_mocked_gemini_unsupported_number_is_rejected():
    from types import SimpleNamespace
    from backend.copilot.schemas import GeminiNarrative

    class FakeGemini:
        def status(self):
            return SimpleNamespace(configured=True, dependency_available=True, model="fake")

        def grounded_narrative(self, **kwargs):
            return GeminiNarrative(
                answer="Amul Milk will lose 99999 units tomorrow.",
                used_fact_ids=[],
                unknowns=[],
            )

    service = CopilotService()
    service.gemini = FakeGemini()
    result = service.ask(message="Will Amul Milk run out in Pune?")
    assert result["mode"] == "deterministic_fallback"
    assert "99999" not in result["answer"]
    assert result["gemini_notes"]
