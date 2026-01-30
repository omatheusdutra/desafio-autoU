import json
from pathlib import Path


def test_jobs_enqueue_and_fetch(monkeypatch):
    from backend_app.application import jobs

    class FakeJob:
        def __init__(self, status):
            self.status = status
            self.meta = {}
            self.args = ["text"]

        @property
        def is_finished(self):
            return self.status == "finished"

        @property
        def is_failed(self):
            return self.status == "failed"

        @property
        def is_started(self):
            return self.status == "started"

        @property
        def result(self):
            return {
                "primary_category": "Status de chamado",
                "overall_category": "Produtivo",
                "confidence": 0.9,
                "engine": "MockEngine",
                "reply": "ok",
            }

    class FakeQueue:
        def __init__(self):
            self.job = FakeJob("finished")

        def enqueue(self, *_args, **_kwargs):
            return type("J", (), {"id": "job1"})

        def fetch_job(self, _job_id):
            return self.job

    monkeypatch.setattr(jobs, "_get_queue", lambda: FakeQueue())
    assert jobs.enqueue_text("x") == "job1"
    assert jobs.enqueue_batch("path.zip") == "job1"


def test_jobs_get_queue_none_and_exception(monkeypatch):
    from backend_app.application import jobs

    jobs.settings.redis_url = None
    assert jobs._get_queue() is None
    assert jobs.enqueue_text("x") is None
    assert jobs.enqueue_batch("p") is None

    jobs.settings.redis_url = "redis://localhost:6379/0"
    monkeypatch.setattr("backend_app.application.jobs.Redis.from_url", lambda _u: (_ for _ in ()).throw(RuntimeError("x")))
    assert jobs._get_queue() is None


def test_jobs_get_queue_success(monkeypatch):
    from backend_app.application import jobs

    class FakeQueue:
        pass

    monkeypatch.setattr("backend_app.application.jobs.Redis.from_url", lambda _u: object())
    monkeypatch.setattr("backend_app.application.jobs.Queue", lambda *_a, **_k: FakeQueue())
    jobs.settings.redis_url = "redis://localhost:6379/0"
    assert isinstance(jobs._get_queue(), FakeQueue)


def test_jobs_fetch_statuses(monkeypatch):
    from backend_app.application import jobs

    class FakeJob:
        def __init__(self, status):
            self.status = status
            self.meta = {"progress": {"processed": 1, "total": 2}}
            self.args = ["text"]

        @property
        def is_finished(self):
            return self.status == "finished"

        @property
        def is_failed(self):
            return self.status == "failed"

        @property
        def is_started(self):
            return self.status == "started"

        @property
        def result(self):
            return {
                "primary_category": "Status de chamado",
                "overall_category": "Produtivo",
                "confidence": 0.9,
                "engine": "MockEngine",
                "reply": "ok",
            }

    class FakeQueue:
        def __init__(self, job):
            self.job = job

        def fetch_job(self, _job_id):
            return self.job

    class FakeRedis:
        pass

    monkeypatch.setattr("backend_app.application.jobs.Redis.from_url", lambda _u: FakeRedis())
    monkeypatch.setattr("backend_app.application.jobs.Queue", lambda *_a, **_k: FakeQueue(FakeJob("finished")))
    jobs.settings.redis_url = "redis://localhost:6379/0"

    payload = jobs.fetch_job("id")
    assert payload["overall_category"] == "Produtivo"

    monkeypatch.setattr("backend_app.application.jobs.Queue", lambda *_a, **_k: FakeQueue(FakeJob("started")))
    payload = jobs.fetch_job("id")
    assert payload["status"] == "processing"

    monkeypatch.setattr("backend_app.application.jobs.Queue", lambda *_a, **_k: FakeQueue(FakeJob("failed")))
    payload = jobs.fetch_job("id")
    assert payload["status"] == "failed"

    monkeypatch.setattr("backend_app.application.jobs.Queue", lambda *_a, **_k: FakeQueue(FakeJob("queued")))
    payload = jobs.fetch_job("id")
    assert payload["status"] == "queued"

    assert jobs.fetch_job("") is None
    jobs.settings.redis_url = None
    assert jobs.fetch_job("id") is None

    monkeypatch.setattr("backend_app.application.jobs.Redis.from_url", lambda _u: (_ for _ in ()).throw(RuntimeError("x")))
    jobs.settings.redis_url = "redis://localhost:6379/0"
    assert jobs.fetch_job("id") is None


def test_jobs_batch_flow(monkeypatch, temp_dir):
    from backend_app.application import jobs

    # Create a dummy zip file
    zip_path = temp_dir / "batch.zip"
    zip_path.write_bytes(b"fake")

    async def fake_handle_zip_path(path, progress_cb=None):
        if progress_cb:
            progress_cb(1, 1)
        return [], {"txt": "a", "csv": "b", "json": "c"}, {"Produtivo": 1}, {"total": 1, "processed": 1, "errors": 0, "duration_seconds": 0.1}

    monkeypatch.setattr("backend_app.application.jobs.handle_zip_path", fake_handle_zip_path)
    called = {"value": False}

    def fake_unlink(self, missing_ok=False):
        called["value"] = True

    monkeypatch.setattr(Path, "unlink", fake_unlink)
    result = jobs.process_batch_job(str(zip_path))
    assert result["report_urls"]["txt"] == "a"
    assert called["value"] is True


def test_jobs_progress_meta(monkeypatch, temp_dir):
    from backend_app.application import jobs

    zip_path = temp_dir / "batch.zip"
    zip_path.write_bytes(b"fake")

    class FakeJob:
        def __init__(self):
            self.meta = {}
        def save_meta(self):
            self.meta["saved"] = True

    job = FakeJob()
    monkeypatch.setattr("backend_app.application.jobs.get_current_job", lambda: job)

    async def fake_handle_zip_path(_path, progress_cb=None):
        if progress_cb:
            progress_cb(1, 2)
        return [], {"txt": "a", "csv": "b", "json": "c"}, {}, {"total": 2, "processed": 1, "errors": 1, "duration_seconds": 0.1}

    monkeypatch.setattr("backend_app.application.jobs.handle_zip_path", fake_handle_zip_path)
    jobs.process_batch_job(str(zip_path))
    assert job.meta["progress"]["processed"] == 1


def test_jobs_fetch_batch(monkeypatch):
    from backend_app.application import jobs

    class FakeJob:
        def __init__(self, status):
            self.status = status
            self.meta = {"progress": {"processed": 1, "total": 2}}

        @property
        def is_finished(self):
            return self.status == "finished"

        @property
        def is_failed(self):
            return self.status == "failed"

        @property
        def is_started(self):
            return self.status == "started"

        @property
        def result(self):
            return {"report_urls": {"txt": "a"}, "summary": {}, "stats": {}}

    class FakeQueue:
        def __init__(self, job):
            self.job = job

        def fetch_job(self, _job_id):
            return self.job

    class FakeRedis:
        pass

    monkeypatch.setattr("backend_app.application.jobs.Redis.from_url", lambda _u: FakeRedis())
    jobs.settings.redis_url = "redis://localhost:6379/0"

    monkeypatch.setattr("backend_app.application.jobs.Queue", lambda *_a, **_k: FakeQueue(FakeJob("finished")))
    payload = jobs.fetch_batch_job("id")
    assert payload["status"] == "completed"

    monkeypatch.setattr("backend_app.application.jobs.Queue", lambda *_a, **_k: FakeQueue(FakeJob("started")))
    payload = jobs.fetch_batch_job("id")
    assert payload["status"] == "processing"

    monkeypatch.setattr("backend_app.application.jobs.Queue", lambda *_a, **_k: FakeQueue(FakeJob("failed")))
    payload = jobs.fetch_batch_job("id")
    assert payload["status"] == "failed"

    monkeypatch.setattr("backend_app.application.jobs.Queue", lambda *_a, **_k: FakeQueue(FakeJob("queued")))
    payload = jobs.fetch_batch_job("id")
    assert payload["status"] == "queued"

    assert jobs.fetch_batch_job("") is None
    jobs.settings.redis_url = None
    assert jobs.fetch_batch_job("id") is None

    monkeypatch.setattr("backend_app.application.jobs.Redis.from_url", lambda _u: (_ for _ in ()).throw(RuntimeError("x")))
    jobs.settings.redis_url = "redis://localhost:6379/0"
    assert jobs.fetch_batch_job("id") is None


def test_jobs_fetch_missing_job(monkeypatch):
    from backend_app.application import jobs

    class FakeQueue:
        def fetch_job(self, _job_id):
            return None

    class FakeRedis:
        pass

    monkeypatch.setattr("backend_app.application.jobs.Redis.from_url", lambda _u: FakeRedis())
    monkeypatch.setattr("backend_app.application.jobs.Queue", lambda *_a, **_k: FakeQueue())
    jobs.settings.redis_url = "redis://localhost:6379/0"
    assert jobs.fetch_job("missing") is None
    assert jobs.fetch_batch_job("missing") is None


def test_jobs_progress_no_current_job(monkeypatch, temp_dir):
    from backend_app.application import jobs

    zip_path = temp_dir / "batch.zip"
    zip_path.write_bytes(b"fake")

    jobs.get_current_job = None

    async def fake_handle_zip_path(_path, progress_cb=None):
        if progress_cb:
            progress_cb(1, 1)
        return [], {"txt": "a", "csv": "b", "json": "c"}, {}, {"total": 1, "processed": 1, "errors": 0, "duration_seconds": 0.1}

    monkeypatch.setattr("backend_app.application.jobs.handle_zip_path", fake_handle_zip_path)
    jobs.process_batch_job(str(zip_path))


def test_jobs_reload_without_get_current_job(monkeypatch):
    import importlib
    import sys
    import types

    import backend_app.application.jobs as jobs_module

    dummy = types.ModuleType("rq")
    dummy.Queue = object
    sys.modules["rq"] = dummy
    reloaded = importlib.reload(jobs_module)
    assert reloaded.get_current_job is None

    import rq as real_rq

    sys.modules["rq"] = real_rq
    importlib.reload(jobs_module)
