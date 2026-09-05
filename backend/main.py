from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from backend.api.copilot import router as copilot_router
from backend.api.dashboard import router as dashboard_router
from backend.api.inventory import router as inventory_router
from backend.api.financial import router as financial_router
from backend.api.products import router as products_router
from backend.api.sales import router as sales_router
from backend.api.simulation import router as simulation_router
from backend.api.stores import router as stores_router
from backend.api.transfers import router as transfers_router
from backend.core.config import ROOT_DIR, SETTINGS
from backend.services.data_service import DataService, DataServiceError

APP_VERSION = str(SETTINGS.get("app", {}).get("version", "0.2.0"))
app = FastAPI(title="RetailIQ", version=APP_VERSION)


@app.get("/health")
def health():
    return {"status": "ok", "service": "RetailIQ", "version": APP_VERSION}


@app.get("/api/health")
def api_health():
    return {"status": "ok", "service": "RetailIQ", "version": APP_VERSION}


@app.get("/api/data/summary")
def data_summary():
    try:
        service = DataService(ROOT_DIR / "data" / "raw")
        return {"status": "ok", **service.summary()}
    except DataServiceError as exc:
        return {"status": "degraded", "error": str(exc)}


# API routers are registered before the SPA catch-all so API paths can never be
# swallowed by frontend routing.
app.include_router(dashboard_router)
app.include_router(copilot_router)
app.include_router(inventory_router)
app.include_router(sales_router)
app.include_router(products_router)
app.include_router(stores_router)
app.include_router(transfers_router)
app.include_router(financial_router)
app.include_router(simulation_router)


DIST_DIR = ROOT_DIR / "frontend" / "dist"
ASSETS_DIR = DIST_DIR / "assets"
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


@app.get("/")
def root():
    index = DIST_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {
        "status": "ok",
        "service": "RetailIQ API",
        "message": "Frontend build not installed yet. API is running.",
    }


@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    if full_path.startswith("api/") or full_path in {"health", "docs", "openapi.json"}:
        return {"detail": "Not Found"}
    index = DIST_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"detail": "Frontend build not installed yet."}


def run():
    app_cfg = SETTINGS.get("app", {})
    uvicorn.run(
        "backend.main:app",
        host=str(app_cfg.get("host", "0.0.0.0")),
        port=int(app_cfg.get("port", 8000)),
        reload=False,
    )
