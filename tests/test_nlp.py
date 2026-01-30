import types


def test_preprocess_and_detect_language():
    from backend_app.application import nlp

    text = "Olá, este é um teste de processamento!"
    cleaned = nlp.preprocess(text)
    assert "teste" in cleaned
    assert nlp.detect_language(text) == "pt"
    assert nlp.detect_language("This is a test in English") == "en"
    assert nlp.detect_language("") == "pt"
    assert nlp.preprocess("") == ""
    assert nlp.detect_language("123") == "pt"


def test_pdf_normalization():
    from backend_app.application import nlp

    raw = "Header\nLine\nFooter\fHeader\nContent\nFooter"
    cleaned = nlp._normalize_pdf_text(raw)
    assert "Header" not in cleaned
    assert "Footer" not in cleaned
    assert "Content" in cleaned
    assert nlp._normalize_pdf_text("") == ""
    assert nlp._normalize_pdf_text(" \n ") == ""
    assert nlp._normalize_pdf_text("Single page") == "Single page"
    raw_with_blank_page = "H\nBody\nF\f \n \n\fH\nBody2\nF"
    cleaned2 = nlp._normalize_pdf_text(raw_with_blank_page)
    assert "Body2" in cleaned2


def test_extract_pdf_text_paths(monkeypatch):
    import types
    import sys
    from backend_app.application import nlp

    pdfminer = types.ModuleType("pdfminer")
    high_level = types.ModuleType("pdfminer.high_level")
    high_level.extract_text = lambda _bio: "Header\fBody"
    pdfminer.high_level = high_level
    sys.modules["pdfminer"] = pdfminer
    sys.modules["pdfminer.high_level"] = high_level

    assert nlp._extract_pdf_text(b"data") != ""

    high_level.extract_text = lambda _bio: (_ for _ in ()).throw(Exception("x"))
    class FakePage:
        def extract_text(self):
            return "H\nBody\nF"
    class FakeReader:
        pages = [FakePage()]
        def __init__(self, _):
            pass
    pypdf2 = types.ModuleType("PyPDF2")
    pypdf2.PdfReader = FakeReader
    sys.modules["PyPDF2"] = pypdf2

    assert nlp._extract_pdf_text(b"data") != ""

    class BadReader:
        def __init__(self, _):
            raise Exception("bad")
    pypdf2.PdfReader = BadReader
    assert nlp._extract_pdf_text(b"data") == ""


def test_extract_text_from_bytes_pdf(monkeypatch):
    from backend_app.application import nlp

    monkeypatch.setattr("backend_app.application.nlp._extract_pdf_text", lambda _b: "PDF")
    assert nlp.extract_text_from_bytes("file.pdf", b"data") == "PDF"
    class BadBytes:
        def decode(self, *_a, **_k):
            raise Exception("bad")
    assert nlp.extract_text_from_bytes("file.txt", BadBytes()) == ""
    assert nlp.asyncio.run(nlp.extract_text_from_bytes_async("file.txt", b"ok")) == "ok"


def test_heuristic_and_zero_shot(monkeypatch, temp_dir):
    from backend_app.application import nlp

    original_get = nlp._get_zero_shot_classifier
    nlp.settings.keyword_overrides_path = str(temp_dir / "k.json")
    (temp_dir / "k.json").write_text('{"Status de chamado":["teste"]}', encoding="utf-8")
    out = nlp.heuristic_multiclass("teste")
    assert out["label"] in nlp.CATEGORIES
    out2 = nlp.heuristic_multiclass("zzzz")
    assert out2["label"] == "Status de chamado"
    out3 = nlp.heuristic_multiclass("obrigado pelo retorno")
    assert out3["label"] == nlp.IMPRODUTIVE_LABEL
    out4 = nlp.heuristic_multiclass("kaj.bsfklasdbfjakbfjkbjkds")
    assert out4["label"] == nlp.IMPRODUTIVE_LABEL

    monkeypatch.setattr("backend_app.application.nlp._get_zero_shot_classifier", lambda _e: None)
    z = nlp.zero_shot_multiclass("texto")
    assert z["engine"] == "Heuristic"

    def fake_classifier(_text, _cats, multi_label=False):
        return {"labels": ["Financeiro"], "scores": [0.9]}

    monkeypatch.setattr("backend_app.application.nlp._get_zero_shot_classifier", lambda _e: fake_classifier)
    z2 = nlp.zero_shot_multiclass("texto")
    assert z2["label"] == "Financeiro"

    def bad_classifier(_text, _cats, multi_label=False):
        raise Exception("fail")
    monkeypatch.setattr("backend_app.application.nlp._get_zero_shot_classifier", lambda _e: bad_classifier)
    z3 = nlp.zero_shot_multiclass("texto")
    assert z3["engine"] == "Heuristic"

    nlp.settings.enable_transformers = False
    monkeypatch.setattr("backend_app.application.nlp._get_zero_shot_classifier", original_get)
    nlp._get_zero_shot_classifier.cache_clear()
    assert nlp._get_zero_shot_classifier(False) is None

    import types, sys

    class FakePipe:
        def __call__(self, text, cats, multi_label=False):
            return {"labels": ["Financeiro"], "scores": [0.9]}

    transformers = types.ModuleType("transformers")
    transformers.pipeline = lambda *_a, **_k: FakePipe()
    sys.modules["transformers"] = transformers
    nlp._get_zero_shot_classifier.cache_clear()
    nlp.settings.enable_transformers = True
    assert nlp._get_zero_shot_classifier(True) is not None

    def bad_pipeline(*_a, **_k):
        raise Exception("boom")
    transformers.pipeline = bad_pipeline
    nlp._get_zero_shot_classifier.cache_clear()
    assert nlp._get_zero_shot_classifier(True) is None

    bad_path = temp_dir / "bad.json"
    bad_path.write_text("not-json", encoding="utf-8")
    nlp.settings.keyword_overrides_path = str(bad_path)
    nlp.heuristic_multiclass("teste")

    list_path = temp_dir / "list.json"
    list_path.write_text('["x"]', encoding="utf-8")
    nlp.settings.keyword_overrides_path = str(list_path)
    nlp.heuristic_multiclass("teste")


def test_gpt_reply_fallback(monkeypatch):
    from backend_app.application import nlp

    monkeypatch.setattr("backend_app.application.nlp._get_openai_client", lambda _k: None)
    reply = nlp.gpt_reply("Hello", "Status de chamado", "en")
    if hasattr(reply, "__await__"):
        reply = nlp.asyncio.run(reply)
    assert "Hello" in reply or "Thanks" in reply
    reply_pt = nlp.build_language_fallback("pt")
    assert "portugu" in reply_pt.lower()


def test_gpt_reply_with_client(monkeypatch):
    from backend_app.application import nlp

    class FakeResp:
        def __init__(self):
            self.choices = [types.SimpleNamespace(message=types.SimpleNamespace(content="ok"))]

    class FakeClient:
        class chat:
            class completions:
                @staticmethod
                def create(**_kwargs):
                    return FakeResp()

    monkeypatch.setattr("backend_app.application.nlp._get_openai_client", lambda _k: FakeClient())
    reply = nlp.gpt_reply("Texto", "Status de chamado", "pt")
    if hasattr(reply, "__await__"):
        reply = nlp.asyncio.run(reply)
    assert reply == "ok"

    class BadClient:
        class chat:
            class completions:
                @staticmethod
                def create(**_kwargs):
                    raise Exception("fail")

    monkeypatch.setattr("backend_app.application.nlp._get_openai_client", lambda _k: BadClient())
    reply2 = nlp.gpt_reply("Texto", "Status de chamado", "pt")
    if hasattr(reply2, "__await__"):
        reply2 = nlp.asyncio.run(reply2)
    assert "Equipe" in reply2


def test_openai_client_exception(monkeypatch):
    from backend_app.application import nlp
    import types
    import sys

    class FakeOpenAI:
        def __init__(self, *args, **kwargs):
            raise Exception("bad")

    mod = types.ModuleType("openai")
    mod.OpenAI = FakeOpenAI
    sys.modules["openai"] = mod

    nlp._get_openai_client.cache_clear()
    client = nlp._get_openai_client("key")
    assert client is None
    nlp._get_openai_client.cache_clear()
    assert nlp._get_openai_client(None) is None


def test_classify_and_respond(monkeypatch):
    from backend_app.application import nlp

    async def fake_gpt(text, category, language="pt"):
        return "reply"

    monkeypatch.setattr("backend_app.application.nlp.gpt_reply", fake_gpt)
    result = nlp.classify_and_respond_sync("status do chamado")
    assert result["reply"] == "reply"

    res = nlp.asyncio.run(nlp.classify_and_respond("status do chamado"))
    assert res["reply"] == "reply"

    monkeypatch.setattr("backend_app.application.nlp.zero_shot_multiclass", lambda _t: {"label": "Financeiro", "confidence": 0.7, "engine": "Z"})
    res2 = nlp.classify_and_respond_sync("fatura")
    assert res2["primary_category"] == "Financeiro"


def test_predict_category_sync_heuristic(monkeypatch):
    from backend_app.application import nlp

    monkeypatch.setattr("backend_app.application.nlp.zero_shot_multiclass", lambda _t: {"label": None, "confidence": 0.0, "engine": "Heuristic"})
    monkeypatch.setattr("backend_app.application.nlp.heuristic_multiclass", lambda _t: {"label": "Status de chamado", "confidence": 0.55, "engine": "Heuristic"})
    out = nlp._predict_category_sync("texto", "texto")
    assert out["primary_category"] == "Status de chamado"


def test_predict_category_sync_prefers_short_thanks(monkeypatch):
    from backend_app.application import nlp

    monkeypatch.setattr(
        "backend_app.application.nlp.heuristic_multiclass",
        lambda _t: {"label": nlp.IMPRODUTIVE_LABEL, "confidence": 0.7, "engine": "Heuristic"},
    )
    monkeypatch.setattr(
        "backend_app.application.nlp.zero_shot_multiclass",
        lambda _t: {"label": "Status de chamado", "confidence": 0.9, "engine": "Transformers"},
    )
    out = nlp._predict_category_sync("texto", "texto")
    assert out["primary_category"] == nlp.IMPRODUTIVE_LABEL


def test_build_template_variants():
    from backend_app.application import nlp

    assert "Equipe de Suporte" in nlp.build_template_reply("Status de chamado", "")
    assert "Equipe T\u00e9cnica" in nlp.build_template_reply("Suporte tecnico", "")
    assert "Financeiro" in nlp.build_template_reply("Financeiro", "")
    assert "documentos" in nlp.build_template_reply("Documentos/Anexos", "").lower()
    assert "acesso" in nlp.build_template_reply("Acesso/Senha", "").lower()
    assert "Agradecemos" in nlp.build_template_reply("Outra", "")


def test_keyword_overrides_edge_cases(monkeypatch, temp_dir):
    from backend_app.application import nlp

    missing_path = temp_dir / "missing.json"
    nlp.DEFAULT_KEYWORD_OVERRIDES = missing_path
    nlp.settings.keyword_overrides_path = None
    nlp.heuristic_multiclass("status")

    edge_path = temp_dir / "edge.json"
    edge_path.write_text('{"Status de chamado":[1, "teste"], "Other": "x"}', encoding="utf-8")
    nlp.settings.keyword_overrides_path = str(edge_path)
    nlp.heuristic_multiclass("teste")


def test_warmup_models(monkeypatch):
    from backend_app.application import nlp

    nlp.settings.enable_transformers = False
    nlp.warmup_models()

    nlp.settings.enable_transformers = True
    monkeypatch.setattr("backend_app.application.nlp._get_zero_shot_classifier", lambda _e: None)
    nlp.warmup_models()

    def boom(_e):
        raise Exception("fail")
    monkeypatch.setattr("backend_app.application.nlp._get_zero_shot_classifier", boom)
    nlp.warmup_models()
