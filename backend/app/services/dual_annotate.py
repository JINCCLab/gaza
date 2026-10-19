"""Dual-annotator sample (MVP): force a second Admin accept before credit."""

from __future__ import annotations

import random
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Submission


def should_require_dual(db: Session, campaign_id: int) -> bool:
    """
    Decide whether this submission (about to enter needs_review) needs a 2nd accept.
    - dual_annotate_first_n: first N needs_review-bound outcomes per campaign
      (counts existing dual-flagged or needs_2nd_review / already dual-accepted samples)
    - dual_annotate_rate: additional random probability
    """
    first_n = max(0, int(settings.dual_annotate_first_n or 0))
    rate = float(settings.dual_annotate_rate or 0.0)
    rate = min(max(rate, 0.0), 1.0)

    if first_n > 0:
        # Count submissions already marked for dual on this campaign
        prior = (
            db.query(Submission)
            .filter(Submission.campaign_id == campaign_id)
            .all()
        )
        dual_count = 0
        for s in prior:
            meta = s.metadata_json or {}
            if meta.get("dual_annotate_required"):
                dual_count += 1
            elif s.verification_status == "needs_2nd_review":
                dual_count += 1
        if dual_count < first_n:
            return True

    if rate <= 0:
        return False
    if rate >= 1.0:
        return True
    return random.random() < rate


def mark_dual_required(meta: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(meta or {})
    out["dual_annotate_required"] = True
    out["dual_annotate_status"] = "awaiting_first"
    return out
