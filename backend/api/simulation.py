from __future__ import annotations

from functools import lru_cache
from backend.api._helpers import _decisions_for_path
from backend.services.dataset_workspace import workspace

from fastapi import APIRouter, HTTPException, Query

from backend.services.data_service import DataServiceError
from backend.services.simulation_service import SimulationService

router = APIRouter(prefix="/api/simulation", tags=["retail decision twin"])


@lru_cache(maxsize=1)
def _simulation_for_path(data_path: str) -> SimulationService:
    return SimulationService(_decisions_for_path(data_path))


def get_simulation_service() -> SimulationService:
    return _simulation_for_path(str(workspace.active_path))


get_simulation_service.cache_clear = _simulation_for_path.cache_clear


def simulation_or_503() -> SimulationService:
    try:
        service = get_simulation_service()
        _ = service.context.analysis_date
        return service
    except (DataServiceError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/compare")
def compare_decisions(
    store_id: str,
    product_id: str,
    horizon_days: int | None = Query(default=None, ge=1, le=60),
    demand_multiplier: float | None = Query(default=None, gt=0, le=5.0),
):
    result = simulation_or_503().compare(
        store_id=store_id,
        product_id=product_id,
        horizon_days=horizon_days,
        demand_multiplier=demand_multiplier,
    )
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.get("/demand-shock")
def demand_shock(
    store_id: str,
    product_id: str,
    demand_multiplier: float = Query(..., gt=0, le=5.0),
    horizon_days: int | None = Query(default=None, ge=1, le=60),
):
    result = simulation_or_503().compare(
        store_id=store_id,
        product_id=product_id,
        horizon_days=horizon_days,
        demand_multiplier=demand_multiplier,
    )
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=result["message"])
    return result
