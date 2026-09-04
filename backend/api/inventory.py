from __future__ import annotations

from fastapi import APIRouter, Query

from backend.api._helpers import analytics_or_503, envelope

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


@router.get("/stockout-risk")
def stockout_risk(
    store_id: str | None = None,
    product_id: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=500),
):
    service = analytics_or_503()
    items = service.stockout(store_id=store_id, product_id=product_id, limit=limit)
    return envelope(items, service.context.analysis_date.strftime("%Y-%m-%d"))


@router.get("/overstock")
def overstock(
    store_id: str | None = None,
    product_id: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=500),
):
    service = analytics_or_503()
    items = service.overstock(store_id=store_id, product_id=product_id, limit=limit)
    return envelope(items, service.context.analysis_date.strftime("%Y-%m-%d"))


@router.get("/slow-movers")
def slow_movers(
    store_id: str | None = None,
    product_id: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=500),
):
    service = analytics_or_503()
    items = service.slow_movers(store_id=store_id, product_id=product_id, limit=limit)
    return envelope(items, service.context.analysis_date.strftime("%Y-%m-%d"))


@router.get("/health")
def inventory_health(
    store_id: str | None = None,
    product_id: str | None = None,
    limit: int | None = Query(default=None, ge=1, le=500),
):
    service = analytics_or_503()
    items = service.inventory_health(store_id=store_id, product_id=product_id, limit=limit)
    return envelope(items, service.context.analysis_date.strftime("%Y-%m-%d"))
