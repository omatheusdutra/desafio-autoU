# nlp.py

"""NLP utilities for Email Smart Reply.



The heavy resources (Transformers pipeline and OpenAI client) are loaded lazily

and cached so every request does not pay the initialization cost.

"""



import asyncio

import logging

import os

import re

import unicodedata

from functools import lru_cache

from io import BytesIO

from typing import Any, Dict, Optional



from ..config.settings import get_settings



settings = get_settings()

logger = logging.getLogger("backend_app.nlp")



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

        return extract_text(bio) or ""

    except Exception:

        try:

            import PyPDF2



            reader = PyPDF2.PdfReader(BytesIO(file_bytes))

            pages = [page.extract_text() or "" for page in reader.pages]

            return "\n".join(pages)

        except Exception:

            return ""





def extract_text_from_bytes(filename: str, file_bytes: bytes) -> str:

    filename = (filename or "").lower()

    if filename.endswith(".pdf"):

        return _extract_pdf_text(file_bytes)

    try:

        return file_bytes.decode("utf-8", errors="ignore")

    except Exception:

        return ""





def preprocess(text: str) -> str:

    text = re.sub(r"\s+", " ", text).strip()

    return text





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





def heuristic_multiclass(text: str) -> Dict[str, Any]:

    normalized = _strip_accents(text).lower()

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





async def gpt_reply(text: str, category: str) -> str:

    client = _get_openai_client(settings.openai_api_key)

    if not client:

        return build_template_reply(category, text)



    prompt = (

        f"Categoria: {category}\n\n"

        "Escreva uma resposta de email profissional, objetiva e cordial em PT-BR, "

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





def _predict_category_sync(text: str) -> Dict[str, Any]:

    z = zero_shot_multiclass(text)

    if z["label"]:

        primary = z["label"]

        confidence = z["confidence"]

        engine = z["engine"]

    else:

        h = heuristic_multiclass(text)

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





async def classify_and_respond(text: str) -> Dict[str, Any]:

    text = preprocess(text)

    prediction = await asyncio.to_thread(_predict_category_sync, text)

    reply = await gpt_reply(text, prediction["primary_category"])

    prediction["reply"] = reply

    return prediction

