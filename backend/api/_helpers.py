from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from backend.services.data_service import DataService
from backend.services.dataset_workspace import workspace

from fastapi import HTTPException

from backend.services.analytics_service import AnalyticsService
from backend.services.data_service import DataServiceError
from backend.services.decision_service import DecisionService


@lru_cache(maxsize=1)
def _analytics_for_path(data_path: str) -> AnalyticsService:
    return AnalyticsService(DataService(Path(data_path)))


def get_analytics_service() -> AnalyticsService:
    return _analytics_for_path(str(workspace.active_path))


get_analytics_service.cache_clear = _analytics_for_path.cache_clear


def analytics_or_503() -> AnalyticsService:
    try:
        service = get_analytics_service()
        _ = service.context.analysis_date
        return service
    except (DataServiceError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@lru_cache(maxsize=1)
def _decisions_for_path(data_path: str) -> DecisionService:
    return DecisionService(_analytics_for_path(data_path))


def get_decision_service() -> DecisionService:
    return _decisions_for_path(str(workspace.active_path))


get_decision_service.cache_clear = _decisions_for_path.cache_clear


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
