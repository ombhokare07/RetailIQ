from pathlib import Path
import os
import yaml
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env", encoding="utf-8-sig")


def _load_yaml(name: str) -> dict:
    path = ROOT_DIR / "config" / name
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


SETTINGS = _load_yaml("settings.yaml")
THRESHOLDS = _load_yaml("thresholds.yaml")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
