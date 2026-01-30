import pytest


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
    async def fake_extract_text_from_bytes_async(_filename: str, _data: bytes):
        return "conteudo extraido"

    monkeypatch.setattr(
        "backend_app.presentation.controllers.api.classify_text",
        fake_classify_text,
    )
    monkeypatch.setattr(
        "backend_app.presentation.controllers.api.process_api_batch",
        fake_process_api_batch,
    )
    monkeypatch.setattr(
        "backend_app.presentation.controllers.api.extract_text_from_bytes_async",
        fake_extract_text_from_bytes_async,
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


def test_api_submit_returns_immediate_result_when_queue_off(client, monkeypatch):
    import backend_app.presentation.controllers.api as api_module

    api_module.settings.enable_job_queue = False
    api_module.settings.redis_url = None

    resp = client.post("/api/submit", json={"text": "status?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["result"]["overall_category"] == "Produtivo"


def test_api_submit_file_returns_immediate_result(client, monkeypatch):
    import backend_app.presentation.controllers.api as api_module

    api_module.settings.enable_job_queue = False
    api_module.settings.redis_url = None

    files = {
        "email_file": ("email.txt", b"fake-content", "text/plain"),
    }
    resp = client.post("/api/submit_file", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["result"]["overall_category"] == "Produtivo"


def test_api_job_returns_status(monkeypatch, client):
    def fake_fetch_job(job_id: str):
        if job_id == "queued":
            return {"status": "queued"}
        if job_id == "processing":
            return {"status": "processing"}
        if job_id == "done":
            return {
                "primary_category": "Status de chamado",
                "overall_category": "Produtivo",
                "confidence": 0.9,
                "engine": "MockEngine",
                "reply": "Stub",
                "text_hash": "hash",
            }
        return None

    monkeypatch.setattr("backend_app.presentation.controllers.api.fetch_job", fake_fetch_job)

    resp = client.get("/api/job/queued")
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"

    resp = client.get("/api/job/processing")
    assert resp.status_code == 200
    assert resp.json()["status"] == "processing"

    resp = client.get("/api/job/done")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"

    resp = client.get("/api/job/missing")
    assert resp.status_code == 200
    assert resp.json()["status"] == "not_found"


def test_api_batch_submit_without_queue(client, monkeypatch):
    import backend_app.presentation.controllers.api as api_module

    api_module.settings.enable_job_queue = False
    api_module.settings.redis_url = None

    async def fake_handle_zip_payload(_data: bytes, progress_cb=None):
        return [], {"txt": "x", "csv": "y", "json": "z"}, {}, {}

    monkeypatch.setattr(
        "backend_app.presentation.controllers.api.handle_zip_payload",
        fake_handle_zip_payload,
    )

    files = {"emails_zip": ("emails.zip", b"fake-bytes", "application/zip")}
    resp = client.post("/api/batch_submit", files=files)
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


def test_api_batch_job_status(monkeypatch, client):
    def fake_fetch_batch_job(job_id: str):
        if job_id == "queued":
            return {"status": "queued", "progress": {"processed": 0, "total": 5}}
        if job_id == "processing":
            return {"status": "processing", "progress": {"processed": 2, "total": 5}}
        if job_id == "done":
            return {
                "status": "completed",
                "report_urls": {"txt": "a", "csv": "b", "json": "c"},
                "summary": {"Produtivo": 1},
                "stats": {"total": 1, "processed": 1, "errors": 0, "duration_seconds": 0.1},
            }
        return None

    monkeypatch.setattr("backend_app.presentation.controllers.api.fetch_batch_job", fake_fetch_batch_job)

    resp = client.get("/api/batch_job/queued")
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"

    resp = client.get("/api/batch_job/processing")
    assert resp.status_code == 200
    assert resp.json()["status"] == "processing"

    resp = client.get("/api/batch_job/done")
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"

    resp = client.get("/api/batch_job/missing")
    assert resp.status_code == 200
    assert resp.json()["status"] == "not_found"


def test_api_batch_submit_with_queue(client, monkeypatch):
    import backend_app.presentation.controllers.api as api_module

    api_module.settings.enable_job_queue = True
    api_module.settings.redis_url = "redis://localhost:6379/0"
    monkeypatch.setattr("backend_app.presentation.controllers.api.enqueue_batch", lambda _p: "job123")

    files = {"emails_zip": ("emails.zip", b"fake-bytes", "application/zip")}
    resp = client.post("/api/batch_submit", files=files)
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"


def test_api_batch_job_failed(monkeypatch, client):
    monkeypatch.setattr(
        "backend_app.presentation.controllers.api.fetch_batch_job",
        lambda _job_id: {"status": "failed"},
    )
    resp = client.get("/api/batch_job/failed")
    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"


def test_api_submit_queue_branch(monkeypatch, client):
    import backend_app.presentation.controllers.api as api_module

    api_module.settings.enable_job_queue = True
    api_module.settings.redis_url = "redis://localhost:6379/0"
    monkeypatch.setattr("backend_app.presentation.controllers.api.enqueue_text", lambda _t: "jobx")

    resp = client.post("/api/submit", json={"text": "status?"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"


def test_api_submit_file_empty_content(monkeypatch, client):
    async def fake_extract(_f, _d):
        return ""

    monkeypatch.setattr(
        "backend_app.presentation.controllers.api.extract_text_from_bytes_async",
        fake_extract,
    )

    files = {"email_file": ("email.txt", b"fake-content", "text/plain")}
    resp = client.post("/api/submit_file", files=files)
    assert resp.status_code == 400


def test_api_batch_limit_error(client):
    import backend_app.presentation.controllers.api as api_module

    original = api_module.settings.max_batch_items
    api_module.settings.max_batch_items = 1
    resp = client.post("/api/batch", json={"texts": ["a", "b"]})
    assert resp.status_code == 422
    api_module.settings.max_batch_items = original


def test_api_submit_file_queue(monkeypatch, client):
    import backend_app.presentation.controllers.api as api_module

    api_module.settings.enable_job_queue = True
    api_module.settings.redis_url = "redis://localhost:6379/0"
    monkeypatch.setattr("backend_app.presentation.controllers.api.enqueue_text", lambda _t: "job2")

    files = {"email_file": ("email.txt", b"fake-content", "text/plain")}
    resp = client.post("/api/submit_file", files=files)
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"


def test_api_batch_submit_cached(monkeypatch, client):
    import backend_app.presentation.controllers.api as api_module

    api_module.settings.enable_job_queue = False
    api_module.settings.redis_url = None
    monkeypatch.setattr(
        "backend_app.presentation.controllers.api.get_cached_batch",
        lambda _h: {"report_urls": {"txt": "x"}, "summary": {}, "stats": {}},
    )
    files = {"emails_zip": ("emails.zip", b"fake-bytes", "application/zip")}
    resp = client.post("/api/batch_submit", files=files)
    assert resp.status_code == 200
    assert resp.json()["report_urls"]["txt"] == "x"
