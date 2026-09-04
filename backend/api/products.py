from fastapi import APIRouter, HTTPException

from backend.api._helpers import analytics_or_503

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("/{product_id}/performance")
def product_performance(product_id: str, store_id: str | None = None):
    service = analytics_or_503()
    result = service.product_performance(product_id, store_id=store_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Product or store not found.")
    return {"status": "ok", **result}
