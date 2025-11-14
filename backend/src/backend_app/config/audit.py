import json
import logging
from pathlib import Path
from typing import Any, Dict

from .settings import get_settings

logger = logging.getLogger("backend_app.audit")


def append_event(event: Dict[str, Any]) -> None:
    """Persist audit events without breaking request flow."""
    settings = get_settings()
    log_path: Path = settings.audit_log_path
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
            )
    except OSError as exc:
        logger.warning("Unable to write audit log: %s (%s)", log_path, exc)
