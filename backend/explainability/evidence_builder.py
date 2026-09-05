from __future__ import annotations

from typing import Any

from backend.explainability.source_tracker import build_source_citations


def _compact(value: Any, *, max_list: int = 5, depth: int = 0) -> Any:
    if depth > 5:
        return "[nested data omitted]"
    if isinstance(value, list):
        compacted = [_compact(v, max_list=max_list, depth=depth + 1) for v in value[:max_list]]
        if len(value) > max_list:
            compacted.append({"omitted_items": len(value) - max_list})
        return compacted
    if isinstance(value, dict):
        result = {}
        for k, v in value.items():
            # Raw record-id lists are surfaced through citations instead of sent
            # in full to Gemini.
            if k in {"sale_ids", "current_sale_ids", "previous_sale_ids"} and isinstance(v, list):
                result[k] = v[:8]
                if len(v) > 8:
                    result[f"{k}_omitted"] = len(v) - 8
            elif k == "alternative_sources" and isinstance(v, list):
                result[k] = _compact(v, max_list=2, depth=depth + 1)
            else:
                result[k] = _compact(v, max_list=max_list, depth=depth + 1)
        return result
    return value


def build_evidence_packet(intent: str, payload: Any, unknowns: list[str] | None = None) -> dict:
    return {
        "intent": intent,
        "facts": _compact(payload),
        "unknowns": list(unknowns or []),
        "citations": build_source_citations(payload),
        "grounding_rule": "All business facts and calculations come from deterministic Python logic over committed local retail data.",
    }
