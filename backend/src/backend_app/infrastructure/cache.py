import json
import logging
from typing import Any, Dict, Optional

from cachetools import TTLCache
from redis import Redis

from ..config.settings import get_settings

logger = logging.getLogger("backend_app.cache")
settings = get_settings()

_local_cache = TTLCache(
    maxsize=max(settings.cache_max_items, 100),
    ttl=max(settings.cache_ttl_seconds, 60),
)
_redis_client: Optional[Redis] = None


def _get_redis() -> Optional[Redis]:
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if not settings.redis_url:
        return None
    try:
        _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
        return _redis_client
    except Exception as exc:
        logger.warning("Redis unavailable: %s", exc)
        return None


def _key(text_hash: str) -> str:
    return f"email-smart-reply:{text_hash}"


def _batch_key(zip_hash: str) -> str:
    return f"email-smart-reply:batch:{zip_hash}"


def get_cached(text_hash: str) -> Optional[Dict[str, Any]]:
    if not text_hash:
        return None
    if settings.enable_redis_cache:
        client = _get_redis()
        if client:
            try:
                payload = client.get(_key(text_hash))
                if payload:
                    return json.loads(payload)
            except Exception as exc:
                logger.warning("Redis cache read failed: %s", exc)
    try:
        return _local_cache.get(text_hash)
    except Exception:
        return None


def set_cached(text_hash: str, payload: Dict[str, Any]) -> None:
    if not text_hash or not payload:
        return
    if settings.enable_redis_cache:
        client = _get_redis()
        if client:
            try:
                client.setex(
                    _key(text_hash),
                    max(settings.cache_ttl_seconds, 60),
                    json.dumps(payload, ensure_ascii=False),
                )
            except Exception as exc:
                logger.warning("Redis cache write failed: %s", exc)
    try:
        _local_cache[text_hash] = payload
    except Exception:
        pass


def get_cached_batch(zip_hash: str) -> Optional[Dict[str, Any]]:
    if not zip_hash:
        return None
    if settings.enable_redis_cache:
        client = _get_redis()
        if client:
            try:
                payload = client.get(_batch_key(zip_hash))
                if payload:
                    return json.loads(payload)
            except Exception as exc:
                logger.warning("Redis batch cache read failed: %s", exc)
    try:
        return _local_cache.get(_batch_key(zip_hash))
    except Exception:
        return None


def set_cached_batch(zip_hash: str, payload: Dict[str, Any]) -> None:
    if not zip_hash or not payload:
        return
    if settings.enable_redis_cache:
        client = _get_redis()
        if client:
            try:
                client.setex(
                    _batch_key(zip_hash),
                    max(settings.cache_ttl_seconds, 60),
                    json.dumps(payload, ensure_ascii=False),
                )
            except Exception as exc:
                logger.warning("Redis batch cache write failed: %s", exc)
    try:
        _local_cache[_batch_key(zip_hash)] = payload
    except Exception:
        pass
