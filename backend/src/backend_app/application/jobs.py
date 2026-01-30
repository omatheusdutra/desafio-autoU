import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from redis import Redis
from rq import Queue

from ..config.settings import get_settings
from .nlp import classify_and_respond_sync
from .processing import hash_text
from .processing import handle_zip_path

try:
    from rq import get_current_job
except Exception:
    get_current_job = None

logger = logging.getLogger("backend_app.jobs")
settings = get_settings()


def _get_queue() -> Optional[Queue]:
    if not settings.redis_url:
        return None
    try:
        conn = Redis.from_url(settings.redis_url)
        return Queue("email-smart-reply", connection=conn)
    except Exception as exc:
        logger.warning("Queue unavailable: %s", exc)
        return None


def enqueue_text(text: str) -> Optional[str]:
    queue = _get_queue()
    if not queue:
        return None
    job = queue.enqueue(classify_and_respond_sync, text or "")
    return job.id


def enqueue_batch(zip_path: str) -> Optional[str]:
    queue = _get_queue()
    if not queue:
        return None
    job = queue.enqueue(process_batch_job, zip_path)
    return job.id


def process_batch_job(zip_path: str) -> Dict[str, Any]:
    path = Path(zip_path)

    def _progress(processed: int, total: int) -> None:
        if not get_current_job:
            return
        job = get_current_job()
        if not job:
            return
        job.meta["progress"] = {"processed": processed, "total": total}
        job.save_meta()

    try:
        rows, report_urls, summary, stats = asyncio.run(
            handle_zip_path(path, progress_cb=_progress)
        )
        return {
            "report_urls": report_urls,
            "summary": summary,
            "stats": stats,
            "rows": rows,
        }
    finally:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


def fetch_job(job_id: str) -> Optional[Dict[str, Any]]:
    if not job_id or not settings.redis_url:
        return None
    try:
        conn = Redis.from_url(settings.redis_url)
        job = Queue("email-smart-reply", connection=conn).fetch_job(job_id)
        if not job:
            return None
        if job.is_finished:
            result = job.result if isinstance(job.result, dict) else {}
            text = job.args[0] if job.args else ""
            result["text_hash"] = hash_text(text or "")
            return result
        if job.is_started:
            return {"status": "processing"}
        if job.is_failed:
            return {"status": "failed"}
        return {"status": "queued"}
    except Exception as exc:
        logger.warning("Queue fetch failed: %s", exc)
        return None


def fetch_batch_job(job_id: str) -> Optional[Dict[str, Any]]:
    if not job_id or not settings.redis_url:
        return None
    try:
        conn = Redis.from_url(settings.redis_url)
        job = Queue("email-smart-reply", connection=conn).fetch_job(job_id)
        if not job:
            return None
        if job.is_finished:
            return {"status": "completed", **(job.result or {})}
        if job.is_failed:
            return {"status": "failed"}
        if job.is_started:
            return {"status": "processing", "progress": job.meta.get("progress")}
        return {"status": "queued", "progress": job.meta.get("progress")}
    except Exception as exc:
        logger.warning("Queue fetch failed: %s", exc)
        return None
