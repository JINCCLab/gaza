"""
Background verification worker.

Consumes Redis list jobs (LPUSH/BRPOP) and runs the same pipeline as sync submit:

    python -m app.worker

Env: DATABASE_URL, REDIS_URL, VERIFY_QUEUE_KEY (optional).
"""

from __future__ import annotations

import json
import logging
import signal
import sys
import time
from typing import Any, Dict, Optional

from app.config import settings
from app.database import SessionLocal
from app.db_migrate import apply_schema
from app.models import Campaign, Submission
from app.services.queue import get_redis_client
from app.services.verification import run_automated_stages

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [verify-worker] %(message)s",
)
logger = logging.getLogger("verify-worker")

_running = True


def _handle_signal(signum: int, _frame: Any) -> None:
    global _running
    logger.info("Signal %s received — draining then exit", signum)
    _running = False


def process_job(payload: Dict[str, Any]) -> None:
    submission_id = int(payload["submission_id"])
    db = SessionLocal()
    try:
        submission = db.get(Submission, submission_id)
        if not submission:
            logger.warning("submission_id=%s not found — skip", submission_id)
            return
        if submission.verification_status not in ("submitted", "in_review"):
            logger.info(
                "submission_id=%s already status=%s — skip",
                submission_id,
                submission.verification_status,
            )
            return
        campaign = db.get(Campaign, submission.campaign_id)
        if not campaign:
            logger.error("campaign missing for submission_id=%s", submission_id)
            submission.verification_status = "rejected"
            submission.reject_reason = "campaign_missing"
            db.commit()
            return
        final = run_automated_stages(db, submission, campaign)
        db.commit()
        logger.info("submission_id=%s → %s", submission_id, final)
    except Exception:
        db.rollback()
        logger.exception("Failed processing submission_id=%s", submission_id)
        raise
    finally:
        db.close()


def _parse_payload(raw: str) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(raw)
        if not isinstance(data, dict) or "submission_id" not in data:
            logger.error("Invalid job payload: %s", raw)
            return None
        return data
    except json.JSONDecodeError:
        logger.error("Non-JSON job payload: %s", raw)
        return None


def run_forever() -> None:
    if not settings.redis_url:
        logger.error("REDIS_URL is required for the worker")
        sys.exit(1)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # Idempotent: Compose entrypoint also migrates; safe if worker starts alone.
    apply_schema()

    logger.info(
        "Starting worker queue=%s database=%s",
        settings.verify_queue_key,
        settings.database_url.split("://")[0],
    )

    while _running:
        try:
            client = get_redis_client()
            item = client.brpop(settings.verify_queue_key, timeout=2)
            if not item:
                continue
            _key, raw = item
            payload = _parse_payload(raw)
            if payload is None:
                continue
            process_job(payload)
        except Exception as e:  # noqa: BLE001 — keep worker alive
            logger.warning("Worker loop error (retry in 2s): %s", e)
            time.sleep(2)

    logger.info("Worker stopped")


if __name__ == "__main__":
    run_forever()
