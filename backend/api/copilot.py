from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, HTTPException

from backend.copilot.copilot_service import CopilotService
from backend.copilot.schemas import CopilotRequest
from backend.services.data_service import DataServiceError

router = APIRouter(prefix="/api/copilot", tags=["grounded multilingual copilot"])


@lru_cache(maxsize=1)
def get_copilot_service() -> CopilotService:
    return CopilotService()


@router.get("/status")
def copilot_status():
    try:
        return get_copilot_service().status()
    except (DataServiceError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/query")
def copilot_query(request: CopilotRequest):
    try:
        return get_copilot_service().ask(
            message=request.message,
            preferred_language=request.language,
            explicit_store_id=request.store_id,
            explicit_product_id=request.product_id,
        )
    except (DataServiceError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
