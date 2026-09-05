from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.api._helpers import decision_or_503
from backend.briefing.daily_briefing import ManagerBriefingService

router = APIRouter(prefix="/api/actions", tags=["manager actions"])


@router.get("/priority")
def priority_actions(store_id: str | None = None, product_id: str | None = None,
                     limit: int = Query(default=20, ge=1, le=500)):
    service = ManagerBriefingService(decisions=decision_or_503())
    try:
        return service.priority_actions(store_id=store_id, product_id=product_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
