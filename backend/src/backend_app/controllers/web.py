from typing import Optional

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse

from ..services.processing import classify_text, ensure_payload_limit
from ..services.nlp import extract_text_from_bytes

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(request, "index.html", {})


@router.post("/process", response_class=HTMLResponse)
async def process_email(
    request: Request,
    email_text: Optional[str] = Form(None),
    email_file: Optional[UploadFile] = File(None),
):
    templates = request.app.state.templates
    content = ""
    if email_file:
        raw_bytes = await email_file.read()
        ensure_payload_limit(len(raw_bytes))
        content = extract_text_from_bytes(email_file.filename or "", raw_bytes)
    if not content and email_text:
        cleaned = email_text.strip()
        if cleaned:
            ensure_payload_limit(len(cleaned.encode("utf-8")))
            content = cleaned

    if not content:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"error": "Envie um arquivo .txt/.pdf ou cole o texto do e-mail."},
            status_code=400,
        )

    result = await classify_text(content, "/process")

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "input_text": content,
            "category": result.get("overall_category"),
            "primary_category": result.get("primary_category"),
            "confidence": result.get("confidence"),
            "suggested_reply": result.get("reply"),
            "engine": result.get("engine"),
            "success_message": "E-mail processado com sucesso!",
        },
    )
