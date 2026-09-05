from __future__ import annotations

import re
from typing import Literal

SupportedLanguage = Literal["en", "hi", "mr"]

_MARATHI_HINTS = {
    "काय", "कोणते", "कोणता", "कोणती", "आहे", "आहेत", "करा", "मला", "पुणे",
    "मुंबई", "नाशिक", "संपणार", "विक्री", "जास्त", "कमी", "स्टॉक",
}
_HINDI_HINTS = {
    "क्या", "कौन", "कौनसे", "कौनसे", "है", "हैं", "मुझे", "करना", "खत्म",
    "बिक्री", "ज्यादा", "कम", "स्टॉक", "आज",
}


def detect_language(text: str, preferred: str | None = None) -> SupportedLanguage:
    """Detect English, Hindi, or Marathi without any network call.

    An explicit supported preferred language wins. For Devanagari text we use a
    small deterministic vocabulary because Hindi and Marathi share the script.
    Ambiguous Devanagari defaults to Hindi; Gemini may still render the final
    answer in the user-selected language when configured.
    """

    if preferred in {"en", "hi", "mr"}:
        return preferred  # type: ignore[return-value]

    normalized = (text or "").strip().lower()
    if not normalized:
        return "en"

    if not re.search(r"[\u0900-\u097F]", normalized):
        return "en"

    tokens = set(re.findall(r"[\u0900-\u097F]+", normalized))
    mr_score = len(tokens & _MARATHI_HINTS)
    hi_score = len(tokens & _HINDI_HINTS)
    if mr_score > hi_score:
        return "mr"
    if hi_score > mr_score:
        return "hi"

    # Common Marathi forms that are strong signals even when tokenization varies.
    if any(fragment in normalized for fragment in ["संपणार", "कोणते", "आहेत", "मला सांग"]):
        return "mr"
    return "hi"
