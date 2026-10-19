"""Redis enqueue for background verification (with sync fallback helpers)."""

from __future__ import annotations

import json
import logging
from typing import Literal, Optional

from app.config import settings

logger = logging.getLogger(__name__)

RedisStatus = Literal["ok", "down", "unset"]


def redis_status() -> RedisStatus:
    if not settings.redis_url:
        return "unset"
    try:
        import redis

        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1.0)
        client.ping()
        return "ok"
    except Exception as e:  # noqa: BLE001 — intentional soft probe
        logger.debug("Redis probe failed: %s", e)
        return "down"


def get_redis_client():
    """Return a Redis client or raise if REDIS_URL missing / unreachable."""
    if not settings.redis_url:
        raise RuntimeError("REDIS_URL is not set")
    import redis

    client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2.0, decode_responses=True)
    client.ping()
    return client


def want_async_verify() -> bool:
    """
    Whether the API should try Redis enqueue.
    VERIFY_MODE=sync → never. async → always try. auto → try when REDIS_URL set.
    """
    mode = settings.verify_mode
    if mode == "sync":
        return False
    if mode == "async":
        return True
    # auto
    return bool(settings.redis_url)


def enqueue_verification(submission_id: int) -> bool:
    """
    Push a verification job. Returns True on success.
    Caller should fall back to sync run_automated_stages on False.
    """
    try:
        client = get_redis_client()
        payload = json.dumps({"submission_id": int(submission_id)})
        client.lpush(settings.verify_queue_key, payload)
        logger.info("Enqueued verification job submission_id=%s", submission_id)
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "Enqueue failed for submission_id=%s (%s); caller should sync-fallback",
            submission_id,
            e,
        )
        return False


def effective_verify_path() -> Literal["sync", "async"]:
    """Best-effort label for health/UI (async only if we would enqueue and Redis is up)."""
    if not want_async_verify():
        return "sync"
    if redis_status() == "ok":
        return "async"
    return "sync"
