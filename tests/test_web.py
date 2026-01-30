import pytest



def test_index_route_renders_page(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Email Smart Reply" in resp.text
    assert "Envie um unico e-mail" in resp.text
    assert "Processar via fila" in resp.text


def test_batch_upload_uses_template(client, monkeypatch):
    async def fake_handle_zip_payload(_data: bytes):
        rows = [
            {
                "arquivo": "email1.txt",
                "primary_category": "Status de chamado",
                "overall_category": "Produtivo",
                "confidence": 0.9,
                "engine": "MockEngine",
                "text_hash": "abc",
                "reply": "Stub",
                "error": "",
            }
        ]
        summary = {"Produtivo": 1}
        report_urls = {
            "txt": "/reports/report_123.txt",
            "csv": "/reports/report_123.csv",
            "json": "/reports/report_123.json",
        }
        stats = {"total": 1, "processed": 1, "errors": 0, "duration_seconds": 0.1}
        return rows, report_urls, summary, stats

    monkeypatch.setattr(
        "backend_app.presentation.controllers.batch.handle_zip_payload",
        fake_handle_zip_payload,
    )

    files = {
        "emails_zip": (
            "emails.zip",
            b"fake-bytes",
            "application/zip",
        )
    }
    resp = client.post("/batch_upload", files=files)
    assert resp.status_code == 200
    assert "/reports/report_123.txt" in resp.text
    assert "/reports/report_123.csv" in resp.text
    assert "/reports/report_123.json" in resp.text
    assert "email1.txt" in resp.text
