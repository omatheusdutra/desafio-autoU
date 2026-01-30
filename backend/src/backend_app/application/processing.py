"""Business logic helpers for FastAPI routes."""

import asyncio
import csv
import hashlib
import io
import json
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable

from fastapi import HTTPException

from ..config.audit import append_event
from ..config.settings import get_settings
from ..infrastructure.cache import (
    get_cached,
    get_cached_batch,
    set_cached,
    set_cached_batch,
)
from ..infrastructure.storage import save_report
from .nlp import classify_and_respond, extract_text_from_bytes_async

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
    results: List[Dict[str, Any]] = [{} for _ in texts]
    missing: List[Tuple[int, str, str]] = []

    for idx, text in enumerate(texts):
        text_hash = hash_text(text or "")
        cached = get_cached(text_hash)
        if cached:
            results[idx] = cached
        else:
            missing.append((idx, text, text_hash))

    async def _run(text: str) -> Dict[str, Any]:
        async with semaphore:
            return await classify_and_respond(text)

    if missing:
        computed = await asyncio.gather(*[_run(t) for _, t, _ in missing])
        for (idx, _, text_hash), result in zip(missing, computed):
            set_cached(text_hash, result)
            results[idx] = result
    return results


def build_txt_report(rows: List[Dict[str, Any]]) -> str:
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
    return "\n".join(lines)


def build_csv_report(rows: List[Dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([label for _, label in REPORT_COLUMNS] + ["Erro"])
    for row in rows:
        values = []
        for key, _ in REPORT_COLUMNS:
            value = row.get(key, "")
            if isinstance(value, float):
                value = f"{value:.3f}"
            value = str(value).replace("\t", " ").replace("\n", " ").strip()
            values.append(value)
        values.append(str(row.get("error", "")).strip())
        writer.writerow(values)
    return output.getvalue()


def build_json_report(rows: List[Dict[str, Any]]) -> str:
    return json.dumps(rows, ensure_ascii=False, indent=2)


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
    text_hash = hash_text(content)
    cached = get_cached(text_hash)
    if cached:
        _log_classification(route, content, cached)
        return cached
    result = await classify_and_respond(content)
    set_cached(text_hash, result)
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


async def _handle_zip(
    zf: zipfile.ZipFile,
    start_time: float,
    zip_hash: Optional[str] = None,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, str], Dict[str, int], Dict[str, Any]]:
    if zip_hash:
        cached = get_cached_batch(zip_hash)
        if cached:
            return (
                cached.get("rows", []),
                cached.get("report_urls", {}),
                cached.get("summary", {}),
                cached.get("stats", {}),
            )
    entries: List[Dict[str, str]] = []
    errors: List[Dict[str, Any]] = []
    parse_semaphore = asyncio.Semaphore(max(settings.pdf_parse_workers, 1))
    for name in zf.namelist():
        if len(entries) >= settings.max_batch_items:
            break
        if name.endswith("/"):
            continue
        if not (name.lower().endswith(".txt") or name.lower().endswith(".pdf")):
            errors.append(
                {"arquivo": name, "error": "Formato nao suportado."}
            )
            continue
        try:
            file_bytes = zf.read(name)
        except Exception:
            errors.append({"arquivo": name, "error": "Falha ao ler o arquivo."})
            continue
        if not file_bytes or len(file_bytes) > MAX_UPLOAD_BYTES:
            errors.append({"arquivo": name, "error": "Arquivo vazio ou excede limite."})
            continue
        async with parse_semaphore:
            content = await extract_text_from_bytes_async(name, file_bytes)
        if not content.strip():
            errors.append({"arquivo": name, "error": "Conteudo vazio."})
            continue
        entries.append({"arquivo": name, "conteudo": content or ""})

    if not entries:
        raise HTTPException(
            status_code=400,
            detail="Nenhum .txt ou .pdf valido encontrado no ZIP.",
        )

    texts = [e["conteudo"] for e in entries]
    results = await classify_many(texts) if texts else []
    rows: List[Dict[str, Any]] = []
    total = len(entries)
    for idx, (entry, result) in enumerate(zip(entries, results), start=1):
        content = entry["conteudo"]
        row = {
            "arquivo": entry["arquivo"],
            "primary_category": result.get("primary_category"),
            "overall_category": result.get("overall_category"),
            "confidence": result.get("confidence"),
            "engine": result.get("engine"),
            "text_hash": hash_text(content or ""),
            "reply": result.get("reply"),
            "error": "",
        }
        _record_event("/batch_upload", filename=row["arquivo"], **row)
        rows.append(row)
        if progress_cb:
            progress_cb(idx, total)
    for err in errors:
        rows.append(
            {
                "arquivo": err.get("arquivo"),
                "primary_category": "",
                "overall_category": "",
                "confidence": 0.0,
                "engine": "",
                "text_hash": "",
                "reply": "",
                "error": err.get("error", ""),
            }
        )

    ts = int(time.time())
    report_base = f"report_{ts}"
    report_txt = build_txt_report(rows)
    report_csv = build_csv_report(rows)
    report_json = build_json_report(rows)
    report_urls = {
        "txt": await asyncio.to_thread(save_report, report_txt, f"{report_base}.txt"),
        "csv": await asyncio.to_thread(save_report, report_csv, f"{report_base}.csv", "text/csv; charset=utf-8"),
        "json": await asyncio.to_thread(save_report, report_json, f"{report_base}.json", "application/json"),
    }

    summary: Dict[str, int] = {}
    for r in rows:
        category = r.get("overall_category")
        if not category:
            continue
        summary[category] = summary.get(category, 0) + 1

    stats = {
        "total": len(entries) + len(errors),
        "processed": len(entries),
        "errors": len(errors),
        "duration_seconds": round(time.time() - start_time, 3),
    }
    if stats["processed"] > 0:
        stats["avg_seconds_per_item"] = round(
            stats["duration_seconds"] / stats["processed"], 3
        )

    payload = {
        "rows": rows,
        "report_urls": report_urls,
        "summary": summary,
        "stats": stats,
    }
    if zip_hash:
        set_cached_batch(zip_hash, payload)
    return rows, report_urls, summary, stats


async def handle_zip_payload(
    data: bytes,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, str], Dict[str, int], Dict[str, Any]]:
    ensure_payload_limit(len(data))
    start_time = time.time()
    zip_hash = hashlib.sha256(data).hexdigest()
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="Arquivo ZIP invalido.") from exc
    return await _handle_zip(zf, start_time, zip_hash=zip_hash, progress_cb=progress_cb)


async def handle_zip_path(
    zip_path: Path,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, str], Dict[str, int], Dict[str, Any]]:
    start_time = time.time()
    hash_ctx = hashlib.sha256()
    with zip_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hash_ctx.update(chunk)
    zip_hash = hash_ctx.hexdigest()
    try:
        with zipfile.ZipFile(zip_path) as zf:
            return await _handle_zip(zf, start_time, zip_hash=zip_hash, progress_cb=progress_cb)
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="Arquivo ZIP invalido.") from exc
