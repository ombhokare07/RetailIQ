from pathlib import Path

from fastapi.testclient import TestClient

from backend.core.config import ROOT_DIR
from backend.main import app


def test_committed_frontend_build_exists():
    index = ROOT_DIR / "frontend" / "dist" / "index.html"
    css = ROOT_DIR / "frontend" / "dist" / "assets" / "styles.css"
    js = ROOT_DIR / "frontend" / "dist" / "assets" / "app.js"
    assert index.exists()
    assert css.exists()
    assert js.exists()


def test_root_serves_retailiq_dashboard():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "RetailIQ" in response.text
    assert "Decision Twin" in response.text
    assert "AI Copilot" in response.text


def test_frontend_assets_are_served_locally():
    client = TestClient(app)
    css = client.get("/assets/styles.css")
    js = client.get("/assets/app.js")
    assert css.status_code == 200
    assert js.status_code == 200
    assert "--accent" in css.text
    assert "/api/copilot/query" in js.text


def test_frontend_has_no_external_runtime_dependencies():
    index = (ROOT_DIR / "frontend" / "dist" / "index.html").read_text(encoding="utf-8")
    assert "https://" not in index
    assert "http://" not in index
    assert "cdn" not in index.lower()
