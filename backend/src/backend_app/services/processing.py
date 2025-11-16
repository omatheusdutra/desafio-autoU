"""Business logic helpers for FastAPI routes."""

import asyncio
import hashlib
import io
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

from fastapi import HTTPException

from ..config.audit import append_event
from ..config.settings import get_settings
from .nlp import classify_and_respond, extract_text_from_bytes

settings = get_settings()

MAX_UPLOAD_BYTES = settings.max_upload_mb * 1024 * 1024
REPORT_COLUMNS = [
    ("arquivo", "Arquivo"),
    ("overall_category", "Categoria binaria"),
    ("primary_category", "Categoria principal"),
    ("confidence", "Confianca"),
    ("engine", "Engine"),
    ("text_hash", "Hash"),
    ("reply", "Resposta"),
]


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _record_event(route: str, **event: Any) -> None:
    payload = {"ts": round(time.time(), 3), "route": route, **event}
    try:
        append_event(payload)
    except Exception:
        pass


def ensure_payload_limit(size_bytes: int) -> None:
    if size_bytes > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Payload excede o limite de {settings.max_upload_mb} MB.",
        )


async def classify_many(texts: List[str]) -> List[Dict[str, Any]]:
    workers = max(settings.classification_workers, 1)
    semaphore = asyncio.Semaphore(workers)

    async def _run(text: str) -> Dict[str, Any]:
        async with semaphore:
            return await classify_and_respond(text)

    return await asyncio.gather(*[_run(t) for t in texts])


def write_txt_report(rows: List[Dict[str, Any]], report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["\t".join(label for _, label in REPORT_COLUMNS)]
    for row in rows:
        values = []
        for key, _ in REPORT_COLUMNS:
            value = row.get(key, "")
            if isinstance(value, float):
                value = f"{value:.3f}"
            value = str(value).replace("\t", " ").replace("\n", " ").strip()
            values.append(value)
        lines.append("\t".join(values))
    report_path.write_text("\n".join(lines), encoding="utf-8")


def _log_classification(route: str, content: str, result: Dict[str, Any]) -> None:
    _record_event(
        route,
        text_hash=hash_text(content),
        primary_category=result.get("primary_category"),
        overall_category=result.get("overall_category"),
        confidence=result.get("confidence"),
        engine=result.get("engine"),
    )


async def classify_text(content: str, route: str) -> Dict[str, Any]:
    result = await classify_and_respond(content)
    _log_classification(route, content, result)
    return result


async def process_api_batch(texts: List[str]) -> List[Dict[str, Any]]:
    normalized = [(t or "").strip() for t in texts]
    results = await classify_many(normalized)
    payloads: List[Dict[str, Any]] = []
    for content, result in zip(normalized, results):
        _log_classification("/api/batch", content, result)
        payloads.append(
            {
                **result,
                "text_hash": hash_text(content),
            }
        )
    return payloads


async def handle_zip_payload(data: bytes) -> Tuple[List[Dict[str, Any]], str, Dict[str, int]]:
    ensure_payload_limit(len(data))
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="Arquivo ZIP invalido.") from exc

    entries: List[Dict[str, str]] = []
    for name in zf.namelist():
        if len(entries) >= settings.max_batch_items:
            break
        if name.endswith("/"):
            continue
        if not (name.lower().endswith(".txt") or name.lower().endswith(".pdf")):
            continue
        try:
            file_bytes = zf.read(name)
        except Exception:
            continue
        if not file_bytes or len(file_bytes) > MAX_UPLOAD_BYTES:
            continue
        content = extract_text_from_bytes(name, file_bytes)
        entries.append({"arquivo": name, "conteudo": content or ""})

    if not entries:
        raise HTTPException(
            status_code=400,
            detail="Nenhum .txt ou .pdf valido encontrado no ZIP.",
        )

    texts = [e["conteudo"] for e in entries]
    results = await classify_many(texts)
    rows: List[Dict[str, Any]] = []
    for entry, result in zip(entries, results):
        content = entry["conteudo"]
        row = {
            "arquivo": entry["arquivo"],
            "primary_category": result.get("primary_category"),
            "overall_category": result.get("overall_category"),
            "confidence": result.get("confidence"),
            "engine": result.get("engine"),
            "text_hash": hash_text(content or ""),
            "reply": result.get("reply"),
        }
        _record_event("/batch_upload", filename=row["arquivo"], **row)
        rows.append(row)

    ts = int(time.time())
    report_name = f"report_{ts}.txt"
    report_path = settings.reports_dir / report_name
    await asyncio.to_thread(write_txt_report, rows, report_path)

    summary: Dict[str, int] = {}
    for r in rows:
        summary[r["overall_category"]] = summary.get(r["overall_category"], 0) + 1

    return rows, report_name, summary
