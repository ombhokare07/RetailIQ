from __future__ import annotations

from fastapi import APIRouter, Query

from backend.api._helpers import decision_or_503, envelope

router = APIRouter(prefix="/api/financial", tags=["financial impact"])


@router.get("/summary")
def financial_summary():
    service = decision_or_503()
    return {"status": "ok", **service.financial_summary()}


@router.get("/revenue-risk")
def revenue_risk(
    store_id: str | None = None,
    product_id: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=500),
):
    service = decision_or_503()
    items = service.revenue_risk(store_id=store_id, product_id=product_id, limit=limit)
    return envelope(items, service.context.analysis_date.strftime("%Y-%m-%d"))


@router.get("/overstock-capital")
def overstock_capital(
    store_id: str | None = None,
    product_id: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=500),
):
    service = decision_or_503()
    items = service.overstock_capital(store_id=store_id, product_id=product_id, limit=limit)
    return envelope(items, service.context.analysis_date.strftime("%Y-%m-%d"))


@router.get("/transfer-benefits")
def transfer_benefits(
    store_id: str | None = None,
    product_id: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=500),
):
    service = decision_or_503()
    items = service.transfer_benefits(store_id=store_id, product_id=product_id, limit=limit)
    return envelope(items, service.context.analysis_date.strftime("%Y-%m-%d"))
