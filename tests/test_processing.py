import io
import zipfile


def _make_zip(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buffer.getvalue()


def test_handle_zip_payload(monkeypatch):
    from backend_app.application import processing

    async def fake_extract(_name, _data):
        return "conteudo"

    async def fake_classify(text):
        return {
            "primary_category": "Status de chamado",
            "overall_category": "Produtivo",
            "confidence": 0.9,
            "engine": "Mock",
            "reply": "ok",
        }

    monkeypatch.setattr("backend_app.application.processing.extract_text_from_bytes_async", fake_extract)
    monkeypatch.setattr("backend_app.application.processing.classify_and_respond", fake_classify)
    monkeypatch.setattr("backend_app.application.processing.get_cached_batch", lambda _h: None)
    monkeypatch.setattr("backend_app.application.processing.set_cached_batch", lambda *_a, **_k: None)

    data = _make_zip({"a.txt": "hello", "b.pdf": "x", "c.xyz": "y"})
    progress = {"value": 0}

    def cb(p, t):
        progress["value"] = p

    rows, report_urls, summary, stats = processing.asyncio.run(
        processing.handle_zip_payload(data, progress_cb=cb)
    )
    assert report_urls["txt"].endswith(".txt")
    assert summary["Produtivo"] >= 1
    assert stats["total"] >= 2
    assert progress["value"] >= 1


def test_handle_zip_payload_errors(monkeypatch):
    from backend_app.application import processing

    async def fake_extract(_name, _data):
        return ""

    monkeypatch.setattr("backend_app.application.processing.extract_text_from_bytes_async", fake_extract)

    data = _make_zip({"a.txt": ""})
    try:
        processing.asyncio.run(processing.handle_zip_payload(data))
    except Exception as exc:
        assert "Nenhum" in str(exc)


def test_handle_zip_payload_cached(monkeypatch):
    from backend_app.application import processing

    async def fake_extract(_name, _data):
        return "conteudo"

    async def fake_classify(_text):
        return {
            "primary_category": "Status de chamado",
            "overall_category": "Produtivo",
            "confidence": 0.9,
            "engine": "Mock",
            "reply": "ok",
        }

    monkeypatch.setattr("backend_app.application.processing.extract_text_from_bytes_async", fake_extract)
    monkeypatch.setattr("backend_app.application.processing.classify_and_respond", fake_classify)

    data = _make_zip({"a.txt": "hello"})
    processing.asyncio.run(processing.handle_zip_payload(data))

    async def raise_classify(_text):
        raise RuntimeError("should not run")

    monkeypatch.setattr("backend_app.application.processing.classify_and_respond", raise_classify)
    processing.asyncio.run(processing.handle_zip_payload(data))


def test_handle_zip_payload_cached_short_circuit(monkeypatch):
    from backend_app.application import processing

    async def fake_handle(_data):
        return [], {"txt": "x"}, {}, {}

    monkeypatch.setattr(
        "backend_app.application.processing.get_cached_batch",
        lambda _h: {"rows": [], "report_urls": {"txt": "x"}, "summary": {}, "stats": {}},
    )
    data = _make_zip({"a.txt": "hello"})
    rows, report_urls, summary, stats = processing.asyncio.run(
        processing.handle_zip_payload(data)
    )
    assert report_urls["txt"] == "x"


def test_handle_zip_payload_limit(monkeypatch):
    from backend_app.application import processing

    original = processing.MAX_UPLOAD_BYTES
    processing.MAX_UPLOAD_BYTES = 1
    data = b"xx"
    try:
        processing.asyncio.run(processing.handle_zip_payload(data))
    except Exception as exc:
        assert "Payload excede" in str(exc) or "Payload" in str(exc)
    finally:
        processing.MAX_UPLOAD_BYTES = original


def test_handle_zip_payload_read_error(monkeypatch):
    from backend_app.application import processing
    import zipfile

    data = _make_zip({"bad.txt": "hello"})
    original = zipfile.ZipFile.read

    def bad_read(self, name, *args, **kwargs):
        if name == "bad.txt":
            raise Exception("read error")
        return original(self, name, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "read", bad_read)
    try:
        processing.asyncio.run(processing.handle_zip_payload(data))
    except Exception:
        pass


def test_handle_zip_payload_directory_and_limits(monkeypatch):
    from backend_app.application import processing

    async def fake_extract(_name, _data):
        return "conteudo"

    async def fake_classify(_text):
        return {
            "primary_category": "Status de chamado",
            "overall_category": "Produtivo",
            "confidence": 0.9,
            "engine": "Mock",
            "reply": "ok",
        }

    monkeypatch.setattr("backend_app.application.processing.extract_text_from_bytes_async", fake_extract)
    monkeypatch.setattr("backend_app.application.processing.classify_and_respond", fake_classify)

    original_max = processing.settings.max_batch_items
    processing.settings.max_batch_items = 1
    data = _make_zip({"folder/": "", "a.txt": "hello", "b.txt": "world"})
    rows, _report_urls, _summary, stats = processing.asyncio.run(
        processing.handle_zip_payload(data)
    )
    assert stats["processed"] == 1
    processing.settings.max_batch_items = original_max


def test_handle_zip_payload_empty_content_error(monkeypatch):
    from backend_app.application import processing

    async def fake_extract(name, _data):
        if name == "empty.txt":
            return "   "
        return "ok"

    async def fake_classify(_text):
        return {
            "primary_category": "Status de chamado",
            "overall_category": "Produtivo",
            "confidence": 0.9,
            "engine": "Mock",
            "reply": "ok",
        }

    monkeypatch.setattr("backend_app.application.processing.extract_text_from_bytes_async", fake_extract)
    monkeypatch.setattr("backend_app.application.processing.classify_and_respond", fake_classify)
    data = _make_zip({"empty.txt": "x", "ok.txt": "y"})
    rows, _report_urls, _summary, stats = processing.asyncio.run(
        processing.handle_zip_payload(data)
    )
    assert stats["errors"] >= 1


def test_handle_zip_payload_no_valid_entries(monkeypatch):
    from backend_app.application import processing

    processing.MAX_UPLOAD_BYTES = 1024 * 1024
    data = _make_zip({"bad.xyz": "x"})
    try:
        processing.asyncio.run(processing.handle_zip_payload(data))
    except Exception as exc:
        assert "Nenhum" in str(exc)


def test_handle_zip_path_invalid(temp_dir):
    from backend_app.application import processing

    bad = temp_dir / "bad.zip"
    bad.write_bytes(b"not-zip")
    try:
        processing.asyncio.run(processing.handle_zip_path(bad))
    except Exception as exc:
        assert "ZIP" in str(exc)


def test_handle_zip_path_valid(monkeypatch, temp_dir):
    from backend_app.application import processing

    async def fake_extract(_name, _data):
        return "conteudo"

    async def fake_classify(_text):
        return {
            "primary_category": "Status de chamado",
            "overall_category": "Produtivo",
            "confidence": 0.9,
            "engine": "Mock",
            "reply": "ok",
        }

    monkeypatch.setattr("backend_app.application.processing.extract_text_from_bytes_async", fake_extract)
    monkeypatch.setattr("backend_app.application.processing.classify_and_respond", fake_classify)

    zip_path = temp_dir / "ok.zip"
    zip_path.write_bytes(_make_zip({"a.txt": "hello"}))
    rows, report_urls, summary, stats = processing.asyncio.run(
        processing.handle_zip_path(zip_path)
    )
    assert rows[0]["arquivo"] == "a.txt"
    assert report_urls["txt"].endswith(".txt")


def test_reports_builders():
    from backend_app.application import processing

    rows = [
        {
            "arquivo": "a.txt",
            "overall_category": "Produtivo",
            "primary_category": "Status de chamado",
            "confidence": 0.9,
            "engine": "Mock",
            "text_hash": "h",
            "reply": "r",
            "error": "",
        }
    ]
    txt = processing.build_txt_report(rows)
    csv = processing.build_csv_report(rows)
    js = processing.build_json_report(rows)
    assert "Arquivo" in txt
    assert "Arquivo" in csv
    assert "a.txt" in js


def test_record_event_exception(monkeypatch):
    from backend_app.application import processing

    async def fake_classify(_text):
        return {
            "primary_category": "Status de chamado",
            "overall_category": "Produtivo",
            "confidence": 0.9,
            "engine": "Mock",
            "reply": "ok",
        }

    monkeypatch.setattr("backend_app.application.processing.append_event", lambda *_a, **_k: (_ for _ in ()).throw(Exception("x")))
    monkeypatch.setattr("backend_app.application.processing.classify_and_respond", fake_classify)
    processing.asyncio.run(processing.classify_text("oi", "/test"))


def test_classify_many_cache(monkeypatch):
    from backend_app.application import processing

    async def fake_classify(_text):
        return {"primary_category": "Status de chamado", "overall_category": "Produtivo", "confidence": 0.9, "engine": "Mock", "reply": "ok"}

    monkeypatch.setattr("backend_app.application.processing.classify_and_respond", fake_classify)
    monkeypatch.setattr("backend_app.application.processing.get_cached", lambda _h: {"primary_category": "Cached", "overall_category": "Produtivo", "confidence": 0.9, "engine": "Mock", "reply": "ok"} if _h == processing.hash_text("a") else None)
    monkeypatch.setattr("backend_app.application.processing.set_cached", lambda *_a, **_k: None)
    res = processing.asyncio.run(processing.classify_many(["a", "b"]))
    assert res[0]["primary_category"] == "Cached"


def test_classify_text_cached(monkeypatch):
    from backend_app.application import processing

    monkeypatch.setattr("backend_app.application.processing.get_cached", lambda _h: {"primary_category": "Cached", "overall_category": "Produtivo", "confidence": 0.9, "engine": "Mock", "reply": "ok"})
    res = processing.asyncio.run(processing.classify_text("a", "/test"))
    assert res["primary_category"] == "Cached"


def test_process_api_batch(monkeypatch):
    from backend_app.application import processing

    async def fake_classify_many(texts):
        return [
            {"primary_category": "Status de chamado", "overall_category": "Produtivo", "confidence": 0.9, "engine": "Mock", "reply": "ok"}
            for _ in texts
        ]

    monkeypatch.setattr("backend_app.application.processing.classify_many", fake_classify_many)
    payloads = processing.asyncio.run(processing.process_api_batch(["a", " b "]))
    assert len(payloads) == 2
    assert payloads[1]["text_hash"] == processing.hash_text("b")


def test_handle_zip_payload_bad_zip():
    from backend_app.application import processing

    try:
        processing.asyncio.run(processing.handle_zip_payload(b"bad"))
    except Exception as exc:
        assert "ZIP" in str(exc)
