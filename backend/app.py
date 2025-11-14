"""Entrypoint used by deployment tooling (uvicorn backend.app:app)."""

from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
if SRC_DIR.exists() and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backend_app.app import app

__all__ = ["app"]
