def test_audit_append_event_handles_oserror(monkeypatch):
    from backend_app.config import audit

    def raise_oserror(*_args, **_kwargs):
        raise OSError("no write")

    monkeypatch.setattr(audit.Path, "open", raise_oserror)
    audit.append_event({"x": 1})
