# nlp.py

"""NLP utilities for Email Smart Reply.



The heavy resources (Transformers pipeline and OpenAI client) are loaded lazily

and cached so every request does not pay the initialization cost.

"""



import asyncio
import json
import logging
import os
import re
import unicodedata
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional



from ..config.settings import get_settings



settings = get_settings()

logger = logging.getLogger("backend_app.nlp")

PACKAGE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_KEYWORD_OVERRIDES = PACKAGE_DIR / "config" / "keyword_overrides.json"

STOPWORDS = {
    "a",
    "ao",
    "aos",
    "as",
    "com",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "entre",
    "era",
    "essa",
    "essas",
    "esse",
    "esses",
    "esta",
    "estao",
    "estas",
    "este",
    "estes",
    "eu",
    "foi",
    "ha",
    "ja",
    "lhe",
    "lhes",
    "mas",
    "me",
    "mesmo",
    "minha",
    "minhas",
    "meu",
    "meus",
    "na",
    "nas",
    "no",
    "nos",
    "o",
    "os",
    "ou",
    "para",
    "por",
    "que",
    "se",
    "sem",
    "sua",
    "suas",
    "seu",
    "seus",
    "tem",
    "tendo",
    "ter",
    "temos",
    "tinha",
    "tive",
    "tivemos",
    "um",
    "uma",
    "umas",
    "uns",
    "voce",
    "voces",
}

STEM_SUFFIXES = (
    "acoes",
    "acao",
    "coes",
    "cao",
    "mente",
    "imento",
    "imentos",
    "amento",
    "amentos",
    "idade",
    "idades",
    "ador",
    "adores",
    "adora",
    "adoras",
    "avel",
    "avelmente",
    "ico",
    "ica",
    "icos",
    "icas",
    "s",
)

PT_STOPWORDS = {
    "de",
    "a",
    "o",
    "e",
    "que",
    "do",
    "da",
    "em",
    "um",
    "para",
    "com",
    "na",
    "no",
    "por",
    "se",
    "os",
    "as",
    "dos",
    "das",
    "ao",
    "aos",
    "como",
    "mais",
    "mas",
    "foi",
    "ser",
    "isso",
    "sua",
    "seu",
}

EN_STOPWORDS = {
    "the",
    "and",
    "to",
    "of",
    "in",
    "for",
    "is",
    "on",
    "that",
    "with",
    "as",
    "this",
    "it",
    "by",
    "be",
    "are",
    "from",
    "at",
    "or",
    "an",
}


IMPRODUTIVE_LABEL = "Sauda\u00e7\u00f5es/Improdutivo"
CATEGORIES = [
    "Status de chamado",
    "Suporte tecnico",
    "Financeiro",
    "Documentos/Anexos",
    "Acesso/Senha",

    IMPRODUTIVE_LABEL,

]





def binary_from_category(cat: str) -> str:

    return "Improdutivo" if cat == IMPRODUTIVE_LABEL else "Produtivo"





def _extract_pdf_text(file_bytes: bytes) -> str:

    try:

        from pdfminer.high_level import extract_text



        bio = BytesIO(file_bytes)

        raw = extract_text(bio) or ""
        return _normalize_pdf_text(raw)

    except Exception:

        try:

            import PyPDF2



            reader = PyPDF2.PdfReader(BytesIO(file_bytes))

            pages = [page.extract_text() or "" for page in reader.pages]

            return _normalize_pdf_text("\f".join(pages))

        except Exception:

            return ""


def _normalize_pdf_text(raw: str) -> str:
    if not raw:
        return ""
    pages = raw.split("\f")
    if not any(p.strip() for p in pages):
        return raw.strip()
    headers = {}
    footers = {}
    for page in pages:
        lines = [l.strip() for l in page.splitlines() if l.strip()]
        if not lines:
            continue
        top = lines[:2]
        bottom = lines[-2:]
        for line in top:
            headers[line] = headers.get(line, 0) + 1
        for line in bottom:
            footers[line] = footers.get(line, 0) + 1
    threshold = max(2, int(len(pages) * 0.6))
    header_set = {k for k, v in headers.items() if v >= threshold}
    footer_set = {k for k, v in footers.items() if v >= threshold}
    cleaned_pages = []
    for page in pages:
        lines = [l.strip() for l in page.splitlines() if l.strip()]
        filtered = [
            l for l in lines if l not in header_set and l not in footer_set
        ]
        cleaned_pages.append("\n".join(filtered))
    return "\n".join(cleaned_pages).strip()





def extract_text_from_bytes(filename: str, file_bytes: bytes) -> str:

    filename = (filename or "").lower()

    if filename.endswith(".pdf"):

        return _extract_pdf_text(file_bytes)

    try:

        return file_bytes.decode("utf-8", errors="ignore")

    except Exception:

        return ""


async def extract_text_from_bytes_async(filename: str, file_bytes: bytes) -> str:
    return await asyncio.to_thread(extract_text_from_bytes, filename, file_bytes)





def _simple_stem(token: str) -> str:
    for suffix in STEM_SUFFIXES:
        if token.endswith(suffix) and len(token) > len(suffix) + 2:
            return token[: -len(suffix)]
    return token


def preprocess(text: str) -> str:
    """Basic PT-BR preprocessing for heuristic classification."""
    if not text:
        return ""
    cleaned = unicodedata.normalize("NFKC", text).lower()
    cleaned = _strip_accents(cleaned)
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    tokens = []
    for token in cleaned.split():
        if token in STOPWORDS or len(token) <= 2:
            continue
        stemmed = _simple_stem(token)
        tokens.append(token)
        if stemmed != token:
            tokens.append(stemmed)
    return " ".join(tokens)


def detect_language(text: str) -> str:
    if not text:
        return "pt"
    cleaned = _strip_accents(text.lower())
    tokens = re.findall(r"[a-z]+", cleaned)
    if not tokens:
        return "pt"
    pt_hits = sum(1 for t in tokens if t in PT_STOPWORDS)
    en_hits = sum(1 for t in tokens if t in EN_STOPWORDS)
    if en_hits > pt_hits and en_hits >= 2:
        return "en"
    return "pt"





def _strip_accents(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")





@lru_cache()

def _get_zero_shot_classifier(enable_transformers: bool):

    if not enable_transformers:

        return None

    try:

        from transformers import pipeline



        return pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

    except Exception as exc:

        logger.warning("Unable to load Transformers zero-shot model: %s", exc)

        return None





def zero_shot_multiclass(text: str) -> Dict[str, Any]:

    classifier = _get_zero_shot_classifier(settings.enable_transformers)

    if not classifier:

        return {"label": None, "confidence": 0.0, "engine": "Heuristic"}

    try:

        hyp = classifier(text, CATEGORIES, multi_label=False)

        if isinstance(hyp, dict):

            label = hyp["labels"][0]

            scores = dict(zip(hyp["labels"], hyp["scores"]))

            conf = float(scores.get(label, 0.0))

            return {

                "label": label,

                "confidence": conf,

                "engine": "Transformers (bart-large-mnli)",

            }

    except Exception as exc:

        logger.warning("Zero-shot classification failed: %s", exc)

    return {"label": None, "confidence": 0.0, "engine": "Heuristic"}


def _apply_keyword_overrides(kw: Dict[str, list]) -> Dict[str, list]:
    overrides_path = (
        settings.keyword_overrides_path
        if getattr(settings, "keyword_overrides_path", None)
        else None
    )
    if overrides_path:
        path = Path(overrides_path)
    else:
        path = DEFAULT_KEYWORD_OVERRIDES
    if not path.exists():
        return kw
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return kw
    if not isinstance(payload, dict):
        return kw
    for category, terms in payload.items():
        if not isinstance(terms, list):
            continue
        normalized_terms = []
        for term in terms:
            if not isinstance(term, str):
                continue
            normalized_terms.append(_strip_accents(term.lower()))
        kw.setdefault(category, [])
        kw[category].extend(normalized_terms)
    return kw


def heuristic_multiclass(text: str) -> Dict[str, Any]:

    normalized = text or ""

    # Heurística curta para mensagens de cortesia/agradecimento
    short_thanks = (
        "obrigado",
        "obrigada",
        "obg",
        "agradeco",
        "agradece",
        "agradecemos",
        "valeu",
        "muito obrigado",
        "muito obrigada",
    )
    if len(normalized.split()) <= 6 and any(t in normalized for t in short_thanks):
        return {
            "label": IMPRODUTIVE_LABEL,
            "confidence": 0.7,
            "engine": "Heuristic",
        }

    # Mensagens sem sentido (muitos caracteres aleatórios, poucas vogais)
    cleaned = _strip_accents(normalized.lower())
    letters = [c for c in cleaned if c.isalpha()]
    if letters:
        vowels = sum(1 for c in letters if c in "aeiou")
        vowel_ratio = vowels / max(len(letters), 1)
        longest_token = max((len(t) for t in cleaned.split()), default=0)
        if vowel_ratio < 0.25 and longest_token >= 8:
            return {
                "label": IMPRODUTIVE_LABEL,
                "confidence": 0.75,
                "engine": "Heuristic",
            }

    kw = {

        "Status de chamado": [

            "status",

            "atualizacao",

            "andamento",

            "chamado",

            "protocolo",

            "ticket",

        ],

        "Suporte tecnico": [

            "erro",

            "bug",

            "falha",

            "stack",

            "trace",

            "log",

            "api",

            "timeout",

            "homologacao",

        ],

        "Financeiro": [

            "fatura",

            "boleto",

            "nota fiscal",

            "nf",

            "cobranca",

            "pagamento",

            "reembolso",

            "financeiro",

        ],

        "Documentos/Anexos": [

            "anexo",

            "documento",

            "arquivo",

            "pdf",

            "planilha",

            "contrato",

        ],

        "Acesso/Senha": [

            "acesso",

            "login",

            "senha",

            "reset",

            "bloqueio",

            "liberacao",

        ],

        IMPRODUTIVE_LABEL: [

            "feliz natal",

            "boas festas",

            "parabens",

            "agradeço",

            "obrigado",

            "abraços",

            "convite",

        ],

    }
    kw = _apply_keyword_overrides(kw)
    for category, keys in kw.items():
        kw[category] = [
            _strip_accents(key.lower())
            for key in keys
            if isinstance(key, str)
        ]

    scores = {c: 0 for c in kw}

    for cat, keys in kw.items():

        scores[cat] = sum(k in normalized for k in keys)

    best = max(scores, key=scores.get)

    conf = min(0.95, 0.5 + 0.1 * scores[best])

    if all(v == 0 for v in scores.values()):

        best = "Status de chamado"

        conf = 0.55

    return {"label": best, "confidence": conf, "engine": "Heuristic"}





def build_template_reply(category: str, text: str) -> str:
    if category == "Status de chamado":
        return (
            "Ol\u00e1!\n\n"
            "Estamos acompanhando o chamado e queremos manter voc\u00ea atualizado(a). "
            "Para avan\u00e7armos, confirme o n\u00famero do protocolo e, se poss\u00edvel, algum identificador (CPF/CNPJ ou refer\u00eancia interna). "
            "Assim que tivermos novidades, retornaremos em at\u00e9 24h \u00fateis.\n\n"
            "Conte conosco,\nEquipe de Suporte"
        )
    if category == "Suporte tecnico":
        return (
            "Ol\u00e1!\n\n"
            "Obrigado por detalhar o ocorrido. Para aprofundarmos a an\u00e1lise, envie por gentileza:\n"
            "- Passos exatos para reproduzir\n"
            "- Data/hora aproximada do incidente\n"
            "- Ambiente utilizado (produ\u00e7\u00e3o/homologa\u00e7\u00e3o)\n"
            "- Prints ou logs do erro\n\n"
            "Com essas informa\u00e7\u00f5es priorizamos sua demanda e retornamos com a solu\u00e7\u00e3o o quanto antes.\n\n"
            "Atenciosamente,\nEquipe T\u00e9cnica"
        )
    if category == "Financeiro":
        return (
            "Ol\u00e1!\n\n"
            "Recebemos sua solicita\u00e7\u00e3o financeira e j\u00e1 estamos cuidando. "
            "Para agilizar, confirme o n\u00famero da fatura/nota, CNPJ e valor envolvido. "
            "Se tiver comprovante ou boleto, pode anexar tamb\u00e9m. Assim que validarmos, retornamos imediatamente.\n\n"
            "At\u00e9 breve,\nTime Financeiro"
        )
    if category == "Documentos/Anexos":
        return (
            "Ol\u00e1!\n\n"
            "Identificamos sua solicita\u00e7\u00e3o envolvendo documentos/anexos. "
            "Confirme quais arquivos precisamos validar e, se poss\u00edvel, envie-os em PDF. "
            "Assim que revisarmos o material, informaremos o pr\u00f3ximo passo.\n\n"
            "Obrigado pela parceria,\nEquipe"
        )
    if category == "Acesso/Senha":
        return (
            "Ol\u00e1!\n\n"
            "Vamos apoi\u00e1-lo com o acesso/senha. informe o usu\u00e1rio/login e o sistema afetado. "
            "Se algum erro aparecer na tela, compartilhe a mensagem. Com isso, conseguimos liberar ou redefinir rapidamente.\n\n"
            "Estamos \u00e0 disposi\u00e7\u00e3o,\nSuporte ao Usu\u00e1rio"
        )
    return (
        "Ol\u00e1!\n\n"
        "Agradecemos a sua mensagem! No momento n\u00e3o h\u00e1 nenhuma a\u00e7\u00e3o necess\u00e1ria. "
        "Se surgir alguma demanda espec\u00edfica, escreva pra gente e teremos prazer em ajudar.\n\n"
        "Abra\u00e7os,\nEquipe"
    )


def build_language_fallback(language: str) -> str:
    if language == "en":
        return (
            "Hello!\n\n"
            "Thanks for your message. To help you faster, could you please send the request in Portuguese (PT-BR)? "
            "If you prefer, we can also continue in English.\n\n"
            "Best regards,\nSupport Team"
        )
    return (
        "Ol\u00e1!\n\n"
        "Recebemos sua mensagem, mas precisamos do conte\u00fado em portugu\u00eas (PT-BR) para agilizar o atendimento. "
        "Se preferir, podemos continuar em ingl\u00eas.\n\n"
        "Atenciosamente,\nEquipe de Suporte"
    )
@lru_cache()

def _get_openai_client(api_key: Optional[str]):

    if not api_key:

        return None

    try:

        from openai import OpenAI



        proxy_url = (

            os.getenv("OPENAI_PROXY")

            or os.getenv("HTTPS_PROXY")

            or os.getenv("HTTP_PROXY")

        )



        if proxy_url:

            os.environ.setdefault("HTTPS_PROXY", proxy_url)

            os.environ.setdefault("HTTP_PROXY", proxy_url)



        return OpenAI(api_key=api_key)

    except Exception as exc:

        logger.warning("Unable to initialize OpenAI client: %s", exc)

        return None





async def gpt_reply(text: str, category: str, language: str = "pt") -> str:

    client = _get_openai_client(settings.openai_api_key)

    if not client:

        if language != "pt":
            return build_language_fallback(language)
        return build_template_reply(category, text)



    prompt = (

        f"Categoria: {category}\n\n"

        f"Idioma detectado: {language}. "
        "Escreva uma resposta de email profissional, objetiva e cordial no mesmo idioma, "

        "com ate 120 palavras. Se precisar de dados, liste-os em marcadores.\n\n"

        f"Texto recebido:\n{text[:2500]}"

    )



    def _call_openai() -> str:

        resp = client.chat.completions.create(

            model="gpt-4o-mini",

            messages=[

                {"role": "system", "content": "Voce e um assistente de atendimento ao cliente."},

                {"role": "user", "content": prompt},

            ],

            temperature=0.3,

            max_tokens=220,

        )

        return resp.choices[0].message.content.strip()



    try:

        return await asyncio.to_thread(_call_openai)

    except Exception as exc:

        logger.warning("OpenAI reply failed, falling back to template: %s", exc)

        return build_template_reply(category, text)





def _predict_category_sync(raw_text: str, processed_text: str) -> Dict[str, Any]:
    # Prioridade para mensagens curtas de cortesia (evita false positives do zero-shot)
    h_quick = heuristic_multiclass(processed_text)
    if h_quick["label"] == IMPRODUTIVE_LABEL and h_quick["confidence"] >= 0.7:
        primary = h_quick["label"]
        confidence = h_quick["confidence"]
        engine = h_quick["engine"]
    else:
        z = zero_shot_multiclass(raw_text)
        if z["label"]:
            primary = z["label"]
            confidence = z["confidence"]
            engine = z["engine"]
        else:
            h = heuristic_multiclass(processed_text)
            primary = h["label"]
            confidence = h["confidence"]
            engine = h["engine"]

    overall = binary_from_category(primary)

    return {

        "primary_category": primary,

        "overall_category": overall,

        "confidence": round(confidence, 3),

        "engine": engine,

    }


def classify_and_respond_sync(text: str) -> Dict[str, Any]:
    raw_text = text or ""
    processed_text = preprocess(raw_text)
    language = detect_language(raw_text)
    prediction = _predict_category_sync(raw_text, processed_text)
    reply = gpt_reply(raw_text, prediction["primary_category"], language)
    if asyncio.iscoroutine(reply):
        reply = asyncio.run(reply)
    prediction["reply"] = reply
    prediction["language"] = language
    return prediction


def warmup_models() -> None:
    if not settings.enable_transformers:
        return
    try:
        _get_zero_shot_classifier(True)
        zero_shot_multiclass("Teste rapido de aquecimento do modelo.")
    except Exception:
        pass



async def classify_and_respond(text: str) -> Dict[str, Any]:
    raw_text = text or ""
    processed_text = preprocess(raw_text)
    language = detect_language(raw_text)

    prediction = await asyncio.to_thread(
        _predict_category_sync, raw_text, processed_text
    )

    reply = await gpt_reply(raw_text, prediction["primary_category"], language)

    prediction["reply"] = reply
    prediction["language"] = language

    return prediction

