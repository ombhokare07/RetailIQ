from __future__ import annotations

from fastapi import APIRouter, Query

from backend.api._helpers import decision_or_503, envelope

router = APIRouter(prefix="/api/transfers", tags=["smart transfers"])


@router.get("/recommendations")
def transfer_recommendations(
    store_id: str | None = None,
    product_id: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=500),
):
    service = decision_or_503()
    items = service.transfer_recommendations(
        store_id=store_id, product_id=product_id, limit=limit
    )
    return envelope(items, service.context.analysis_date.strftime("%Y-%m-%d"))
