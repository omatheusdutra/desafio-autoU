from fastapi import APIRouter, HTTPException

from ..models.schemas import (
    BatchProcessRequest,
    BatchProcessResponse,
    ProcessRequest,
    ProcessResponse,
)
from ..services.processing import classify_text, hash_text, process_api_batch
from ..config.settings import get_settings

router = APIRouter()
settings = get_settings()


@router.post("/process", response_model=ProcessResponse)
async def api_process(req: ProcessRequest):
    content = (req.text or "").strip()
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
