from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from backend.copilot.prompts import INTENT_SYSTEM_PROMPT, NARRATIVE_SYSTEM_PROMPT
from backend.copilot.schemas import GeminiIntent, GeminiNarrative
from backend.core.config import SETTINGS


class GeminiUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class GeminiStatus:
    configured: bool
    dependency_available: bool
    model: str


class GeminiService:
    """Thin Gemini wrapper.

    No client is created and no network request is made at import/startup. The
    client is created only inside a user-triggered method.
    """

    def __init__(self):
        cfg = SETTINGS.get("gemini", {})
        self.model = os.getenv("GEMINI_MODEL") or str(cfg.get("model", "gemini-2.5-flash-lite"))

    def status(self) -> GeminiStatus:
        try:
            import google.genai  # noqa: F401
            dependency_available = True
        except ImportError:
            dependency_available = False
        return GeminiStatus(
            configured=bool(os.getenv("GEMINI_API_KEY")),
            dependency_available=dependency_available,
            model=self.model,
        )

    def _client_and_types(self):
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise GeminiUnavailable("GEMINI_API_KEY is not configured.")
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise GeminiUnavailable("google-genai is not installed.") from exc

        # Explicit key avoids accidentally preferring another environment
        # variable. Timeout is kept below the hackathon's per-request limit.
        timeout_ms = int(SETTINGS.get("gemini", {}).get("timeout_ms", 20000))
        client = genai.Client(
            api_key=key,
            http_options=types.HttpOptions(timeout=timeout_ms),
        )
        return client, types

    def classify_intent(self, *, message: str, language: str, catalogs: dict) -> GeminiIntent:
        client, types = self._client_and_types()
        prompt = {
            "system": INTENT_SYSTEM_PROMPT,
            "user_message": message,
            "detected_language": language,
            "allowed_stores": catalogs.get("stores", []),
            "allowed_products": catalogs.get("products", []),
            "supported_intents": list(GeminiIntent.model_fields["intent"].annotation.__args__),
        }
        try:
            response = client.models.generate_content(
                model=self.model,
                contents=json.dumps(prompt, ensure_ascii=False),
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                    response_schema=GeminiIntent,
                ),
            )
            if getattr(response, "parsed", None) is not None:
                parsed = response.parsed
                return parsed if isinstance(parsed, GeminiIntent) else GeminiIntent.model_validate(parsed)
            return GeminiIntent.model_validate_json(response.text)
        except Exception as exc:  # SDK/network/model failures must never take down the app.
            raise GeminiUnavailable(f"Gemini intent call failed: {exc}") from exc

    def grounded_narrative(
        self,
        *,
        language: str,
        user_message: str,
        fact_packet: dict,
        fact_table: list[dict],
    ) -> GeminiNarrative:
        client, types = self._client_and_types()
        prompt = {
            "system": NARRATIVE_SYSTEM_PROMPT,
            "requested_language": language,
            "user_message": user_message,
            "fact_packet": fact_packet,
            "fact_table": fact_table,
        }
        try:
            response = client.models.generate_content(
                model=self.model,
                contents=json.dumps(prompt, ensure_ascii=False, default=str),
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                    response_schema=GeminiNarrative,
                ),
            )
            if getattr(response, "parsed", None) is not None:
                parsed = response.parsed
                return parsed if isinstance(parsed, GeminiNarrative) else GeminiNarrative.model_validate(parsed)
            return GeminiNarrative.model_validate_json(response.text)
        except Exception as exc:
            raise GeminiUnavailable(f"Gemini explanation call failed: {exc}") from exc


