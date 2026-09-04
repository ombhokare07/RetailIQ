from __future__ import annotations

from fastapi import APIRouter, Query

from backend.api._helpers import analytics_or_503, envelope

router = APIRouter(prefix="/api/sales", tags=["sales"])


@router.get("/anomalies")
def sales_anomalies(
    store_id: str | None = None,
    product_id: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=500),
):
    service = analytics_or_503()
    items = service.anomalies(store_id=store_id, product_id=product_id, limit=limit)
    return envelope(items, service.context.analysis_date.strftime("%Y-%m-%d"))
