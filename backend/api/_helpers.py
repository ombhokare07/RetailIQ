from __future__ import annotations

from functools import lru_cache

from fastapi import HTTPException

from backend.services.analytics_service import AnalyticsService
from backend.services.data_service import DataServiceError
from backend.services.decision_service import DecisionService


@lru_cache(maxsize=1)
def get_analytics_service() -> AnalyticsService:
    return AnalyticsService()


def analytics_or_503() -> AnalyticsService:
    try:
        service = get_analytics_service()
        _ = service.context.analysis_date
        return service
    except (DataServiceError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@lru_cache(maxsize=1)
def get_decision_service() -> DecisionService:
    return DecisionService(get_analytics_service())


def decision_or_503() -> DecisionService:
    try:
        service = get_decision_service()
        _ = service.context.analysis_date
        return service
    except (DataServiceError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def envelope(items: list[dict], analysis_date: str) -> dict:
    return {
        "status": "ok",
        "analysis_date": analysis_date,
        "count": len(items),
        "items": items,
    }
