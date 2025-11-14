import pytest
from fastapi.testclient import TestClient

from app import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def stub_classifiers(monkeypatch):
    async def fake_classify_text(content: str, route: str):
        return {
            "primary_category": "Status de chamado",
            "overall_category": "Produtivo",
            "confidence": 0.91,
            "engine": "MockEngine",
            "reply": "Ola! Este eh um stub.",
        }

    async def fake_process_api_batch(texts):
        results = []
        for idx, text in enumerate(texts):
            results.append(
                {
                    "primary_category": f"Categoria {idx}",
                    "overall_category": "Produtivo",
                    "confidence": 0.8,
                    "engine": "MockEngine",
                    "reply": f"Resposta {idx}",
                    "text_hash": f"hash-{idx}",
                }
            )
        return results

    monkeypatch.setattr(
        "backend_app.controllers.api.classify_text",
        fake_classify_text,
    )
    monkeypatch.setattr(
        "backend_app.controllers.api.process_api_batch",
        fake_process_api_batch,
    )


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_api_process_returns_expected_payload(client):
    resp = client.post("/api/process", json={"text": "status?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["primary_category"] == "Status de chamado"
    assert data["overall_category"] == "Produtivo"
    assert data["reply"].startswith("Ola")
    assert len(data["text_hash"]) == 64


def test_api_batch_handles_multiple_entries(client):
    resp = client.post("/api/batch", json={"texts": ["email 1", "email 2"]})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) == 2
    assert body["results"][0]["primary_category"] == "Categoria 0"
    assert body["results"][1]["reply"] == "Resposta 1"
