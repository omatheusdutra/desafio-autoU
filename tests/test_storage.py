def test_storage_local(temp_dir, monkeypatch):
    from backend_app.infrastructure import storage

    storage.settings.reports_storage = "local"
    storage.settings.reports_dir = temp_dir
    url = storage.save_report("ok", "r.txt")
    assert url.endswith("/reports/r.txt")
    assert (temp_dir / "r.txt").exists()
    url = storage.save_report(b"bytes", "r.bin")
    assert url.endswith("/reports/r.bin")


def test_storage_s3_fallback(temp_dir, monkeypatch):
    from backend_app.infrastructure import storage

    storage.settings.reports_storage = "s3"
    storage.settings.s3_bucket = "bucket"
    storage.settings.s3_prefix = "reports"
    storage.settings.reports_dir = temp_dir

    def raise_err(*_args, **_kwargs):
        raise RuntimeError("s3 down")

    monkeypatch.setattr(storage, "_s3_client", lambda: type("C", (), {"put_object": raise_err})())
    url = storage.save_report("ok", "r.txt")
    assert url.endswith("/reports/r.txt")


def test_storage_s3_success(monkeypatch, temp_dir):
    from backend_app.infrastructure import storage

    class FakeClient:
        def __init__(self):
            self.saved = []

        def put_object(self, **kwargs):
            self.saved.append(kwargs)

        def generate_presigned_url(self, *_args, **_kwargs):
            return "http://signed-url"

    storage.settings.reports_storage = "s3"
    storage.settings.s3_bucket = "bucket"
    storage.settings.s3_prefix = "reports"
    storage.settings.s3_region = "us-east-1"
    storage.settings.s3_public_base_url = None
    storage.settings.reports_dir = temp_dir

    fake = FakeClient()
    monkeypatch.setattr(storage, "_s3_client", lambda: fake)
    url = storage.save_report("ok", "r.txt")
    assert url == "http://signed-url"

    storage.settings.s3_public_base_url = "https://public.example"
    url = storage.save_report("ok", "r2.txt")
    assert url == "https://public.example/reports/r2.txt"


def test_s3_client_build(monkeypatch):
    from backend_app.infrastructure import storage

    class FakeSession:
        def __init__(self, region_name=None):
            self.region_name = region_name

        def client(self, _name):
            return object()

    monkeypatch.setattr("backend_app.infrastructure.storage.boto3.session.Session", FakeSession)
    storage._s3_client()
