import hashlib
from fastapi import APIRouter, File, HTTPException, UploadFile

from ...domain.schemas import (
    BatchProcessRequest,
    BatchProcessResponse,
    BatchJobStatusResponse,
    BatchJobSubmitResponse,
    JobStatusResponse,
    JobSubmitResponse,
    ProcessRequest,
    ProcessResponse,
)
from ...application.processing import (
    classify_text,
    ensure_payload_limit,
    hash_text,
    process_api_batch,
)
from ...application.jobs import enqueue_batch, enqueue_text, fetch_batch_job, fetch_job
from ...infrastructure.cache import get_cached_batch
from ...application.nlp import extract_text_from_bytes_async
from ...application.processing import handle_zip_payload
import time
from ...config.settings import get_settings

router = APIRouter()
settings = get_settings()


@router.post("/process", response_model=ProcessResponse)
async def api_process(req: ProcessRequest):
    content = (req.text or "").strip()
    if content:
        ensure_payload_limit(len(content.encode("utf-8")))
    result = await classify_text(content, "/api/process")

    return ProcessResponse(
        primary_category=result.get("primary_category"),
        overall_category=result.get("overall_category"),
        confidence=float(result.get("confidence", 0)),
        engine=result.get("engine") or "unknown",
        reply=result.get("reply") or "",
        text_hash=hash_text(content),
    )


@router.post("/batch", response_model=BatchProcessResponse)
async def api_batch(req: BatchProcessRequest):
    texts = req.texts or []
    if len(texts) > settings.max_batch_items:
        raise HTTPException(
            status_code=422,
            detail=f"Lote excede o limite de {settings.max_batch_items} registros.",
        )
    for text in texts:
        if text:
            ensure_payload_limit(len(text.encode("utf-8")))

    payloads = await process_api_batch(texts)
    results = [
        ProcessResponse(
            primary_category=item.get("primary_category"),
            overall_category=item.get("overall_category"),
            confidence=float(item.get("confidence", 0)),
            engine=item.get("engine") or "unknown",
            reply=item.get("reply") or "",
            text_hash=item.get("text_hash", ""),
        )
        for item in payloads
    ]
    return BatchProcessResponse(results=results)


@router.post("/submit", response_model=JobSubmitResponse)
async def api_submit(req: ProcessRequest):
    content = (req.text or "").strip()
    if content:
        ensure_payload_limit(len(content.encode("utf-8")))

    if settings.enable_job_queue and settings.redis_url:
        job_id = enqueue_text(content)
        if job_id:
            return JobSubmitResponse(job_id=job_id, status="queued")

    result = await classify_text(content, "/api/submit")
    return JobSubmitResponse(
        job_id=None,
        status="completed",
        result=ProcessResponse(
            primary_category=result.get("primary_category"),
            overall_category=result.get("overall_category"),
            confidence=float(result.get("confidence", 0)),
            engine=result.get("engine") or "unknown",
            reply=result.get("reply") or "",
            text_hash=hash_text(content),
        ),
    )


@router.get("/job/{job_id}", response_model=JobStatusResponse)
async def api_job(job_id: str):
    payload = fetch_job(job_id)
    if not payload:
        return JobStatusResponse(status="not_found", message="Job nao encontrado.")
    status = payload.get("status")
    if status in {"queued", "failed"}:
        msg = "Na fila." if status == "queued" else "Falha no processamento."
        return JobStatusResponse(status=status, message=msg)
    if status == "processing":
        return JobStatusResponse(status=status, message="Processando.")
    return JobStatusResponse(
        status="completed",
        result=ProcessResponse(
            primary_category=payload.get("primary_category"),
            overall_category=payload.get("overall_category"),
            confidence=float(payload.get("confidence", 0)),
            engine=payload.get("engine") or "unknown",
            reply=payload.get("reply") or "",
            text_hash=payload.get("text_hash", ""),
        ),
    )


@router.post("/submit_file", response_model=JobSubmitResponse)
async def api_submit_file(email_file: UploadFile = File(...)):
    raw_bytes = await email_file.read()
    ensure_payload_limit(len(raw_bytes))
    content = await extract_text_from_bytes_async(email_file.filename or "", raw_bytes)
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo sem conteudo valido.")

    if settings.enable_job_queue and settings.redis_url:
        job_id = enqueue_text(content)
        if job_id:
            return JobSubmitResponse(job_id=job_id, status="queued")

    result = await classify_text(content, "/api/submit_file")
    return JobSubmitResponse(
        job_id=None,
        status="completed",
        result=ProcessResponse(
            primary_category=result.get("primary_category"),
            overall_category=result.get("overall_category"),
            confidence=float(result.get("confidence", 0)),
            engine=result.get("engine") or "unknown",
            reply=result.get("reply") or "",
            text_hash=hash_text(content),
        ),
    )


@router.post("/batch_submit", response_model=BatchJobSubmitResponse)
async def api_batch_submit(emails_zip: UploadFile = File(...)):
    data = await emails_zip.read()
    ensure_payload_limit(len(data))
    zip_hash = hashlib.sha256(data).hexdigest()
    cached = get_cached_batch(zip_hash)
    if cached:
        return BatchJobSubmitResponse(
            job_id=None,
            status="completed",
            report_urls=cached.get("report_urls"),
            summary=cached.get("summary"),
            stats=cached.get("stats"),
        )

    if settings.enable_job_queue and settings.redis_url:
        uploads_dir = settings.reports_dir / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        tmp_path = uploads_dir / f"batch_{ts}.zip"
        tmp_path.write_bytes(data)
        job_id = enqueue_batch(str(tmp_path))
        if job_id:
            return BatchJobSubmitResponse(job_id=job_id, status="queued")

    rows, report_urls, summary, stats = await handle_zip_payload(data)
    return BatchJobSubmitResponse(
        job_id=None,
        status="completed",
        report_urls=report_urls,
        summary=summary,
        stats=stats,
    )


@router.get("/batch_job/{job_id}", response_model=BatchJobStatusResponse)
async def api_batch_job(job_id: str):
    payload = fetch_batch_job(job_id)
    if not payload:
        return BatchJobStatusResponse(status="not_found", message="Job nao encontrado.")
    status = payload.get("status")
    if status in {"queued", "processing", "failed"}:
        msg = {
            "queued": "Na fila.",
            "processing": "Processando.",
            "failed": "Falha no processamento.",
        }.get(status, "")
        return BatchJobStatusResponse(
            status=status,
            message=msg,
            progress=payload.get("progress"),
        )
    return BatchJobStatusResponse(
        status="completed",
        report_urls=payload.get("report_urls"),
        summary=payload.get("summary"),
        stats=payload.get("stats"),
        progress=payload.get("progress"),
    )
