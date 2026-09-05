from fastapi import APIRouter

from backend.api._helpers import analytics_or_503

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
def dashboard_summary(store_id: str | None = None):
    service = analytics_or_503()
    return {"status": "ok", **service.dashboard_summary(store_id=store_id)}


@router.get("/assumptions")
def analytics_assumptions():
    service = analytics_or_503()
    return {"status": "ok", **service.assumptions()}
