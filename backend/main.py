from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from backend.core.config import ROOT_DIR, SETTINGS
from backend.services.data_service import DataService, DataServiceError

APP_VERSION = str(SETTINGS.get("app", {}).get("version", "0.1.0"))
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
