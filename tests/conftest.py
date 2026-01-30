import os
import sys
import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import shutil
import uuid

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "backend" / "src"
if SRC.exists() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(scope="session")
def app():
    os.environ.setdefault("ENABLE_WARMUP", "false")
    os.environ.setdefault("ENABLE_TRANSFORMERS", "false")
    os.environ.setdefault("ENABLE_RATE_LIMIT", "false")
    os.environ.setdefault("ENABLE_JOB_QUEUE", "false")
    os.environ.setdefault("ENABLE_REDIS_CACHE", "false")
    os.environ.setdefault("CACHE_TTL_SECONDS", "30")
    os.environ.setdefault("CACHE_MAX_ITEMS", "100")

    from backend_app.config.settings import get_settings

    get_settings.cache_clear()
    import app as app_module

    return app_module.app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def temp_dir():
    base = Path("tests") / ".tmp"
    base.mkdir(parents=True, exist_ok=True)
    path = base / str(uuid.uuid4())
    path.mkdir(parents=True, exist_ok=True)
    yield path
    shutil.rmtree(path, ignore_errors=True)
