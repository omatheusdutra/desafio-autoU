import pytest


def test_web_process_text(client):
    resp = client.post("/process", data={"email_text": "Oi, status?"})
    assert resp.status_code == 200
    assert "E-mail processado" in resp.text


def test_web_process_no_input(client):
    resp = client.post("/process", data={})
    assert resp.status_code == 400
    assert "Envie um arquivo" in resp.text


def test_security_txt(client):
    resp = client.get("/security.txt")
    assert resp.status_code == 200
    assert "Contact:" in resp.text


def test_web_process_file(client, monkeypatch):
    async def fake_extract(_f, _d):
        return "arquivo conteudo"

    monkeypatch.setattr(
        "backend_app.presentation.controllers.web.extract_text_from_bytes_async",
        fake_extract,
    )
    files = {"email_file": ("email.txt", b"fake", "text/plain")}
    resp = client.post("/process", files=files)
    assert resp.status_code == 200
