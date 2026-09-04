from fastapi import APIRouter, HTTPException

from backend.api._helpers import analytics_or_503

router = APIRouter(prefix="/api/stores", tags=["stores"])


@router.get("/{store_id}/performance")
def store_performance(store_id: str):
    service = analytics_or_503()
    result = service.store_performance(store_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Store not found.")
    return {"status": "ok", **result}
