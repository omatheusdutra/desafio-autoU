import os

from fastapi.testclient import TestClient


def test_app_rate_limit_and_block_dot_git(monkeypatch):
    os.environ["ENABLE_RATE_LIMIT"] = "true"
    os.environ["ENABLE_WARMUP"] = "false"
    os.environ["ENABLE_TRANSFORMERS"] = "false"

    from backend_app.config.settings import get_settings

    get_settings.cache_clear()
    from backend_app.app import create_app

    app = create_app()
    client = TestClient(app)
    resp = client.get("/.git/HEAD")
    assert resp.status_code == 404


def test_app_warmup_called(monkeypatch):
    os.environ["ENABLE_RATE_LIMIT"] = "false"
    os.environ["ENABLE_WARMUP"] = "true"
    os.environ["ENABLE_TRANSFORMERS"] = "false"

    from backend_app.config.settings import get_settings

    get_settings.cache_clear()

    called = {"value": False}

    def fake_warmup():
        called["value"] = True

    import importlib

    app_module = importlib.import_module("backend_app.app")
    monkeypatch.setattr(app_module, "warmup_models", fake_warmup)
    create_app = app_module.create_app

    app = create_app()
    with TestClient(app) as client:
        client.get("/health")
    assert called["value"] is True
