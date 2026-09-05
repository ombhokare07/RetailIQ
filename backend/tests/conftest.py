"""Global test guard: no test may create a real Gemini client."""

import os

# Set this before application modules load. python-dotenv does not replace an
# existing value, including the intentionally blank test value.
os.environ["GEMINI_API_KEY"] = ""

import pytest

from backend.copilot.llm import GeminiService


@pytest.fixture(autouse=True)
def block_real_gemini_client(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")

    def blocked_client(*args, **kwargs):
        raise AssertionError("Real Gemini clients are forbidden in pytest; inject a fake Gemini service.")

    monkeypatch.setattr(GeminiService, "_client_and_types", blocked_client)
