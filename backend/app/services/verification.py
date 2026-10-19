import hashlib
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models import Campaign, Submission, VerificationEvent
from app.services.allowlist import is_host_allowed


REQUIRED_LABEL_KEYS = ("event_type", "location_public", "event_time", "equipment_type")


def _hash_payload(source_url: str, labels: Dict[str, Any]) -> str:
    blob = f"{source_url.strip().lower()}|{sorted(labels.items())}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _event(
    db: Session,
    submission_id: int,
    stage: str,
    result: str,
    detail: Optional[Dict[str, Any]] = None,
    actor_id: Optional[int] = None,
) -> VerificationEvent:
    ev = VerificationEvent(
        submission_id=submission_id,
        stage=stage,
        result=result,
        detail_json=detail or {},
        actor_id=actor_id,
    )
    db.add(ev)
    return ev


def run_automated_stages(db: Session, submission: Submission, campaign: Campaign) -> str:
    """
    Stages 1–7 stubs. Default route = needs_review (Phase-0 posture).
    Returns final automated status: needs_review | rejected.
    """
    labels = submission.labels_json or {}
    meta = submission.metadata_json or {}

    # 1. Technical — URL present, payload size ok (stub)
    if not submission.source_url or len(submission.source_url) > 2000:
        _event(db, submission.id, "technical", "fail", {"reason": "invalid_url"})
        submission.verification_status = "rejected"
        submission.reject_reason = "technical_invalid"
        return "rejected"
    _event(db, submission.id, "technical", "pass", {"stub": True})

    # 2. Schema / policy
    missing = [k for k in REQUIRED_LABEL_KEYS if not labels.get(k)]
    req = campaign.requirements_json or {}
    allowed_events = set(req.get("event_types") or [])
    allowed_equip = set(req.get("equipment_types") or [])
    schema_ok = not missing
    if allowed_events and labels.get("event_type") not in allowed_events:
        schema_ok = False
        missing.append("event_type_not_in_enum")
    if allowed_equip and labels.get("equipment_type") not in allowed_equip:
        schema_ok = False
        missing.append("equipment_type_not_in_enum")
    if not schema_ok:
        _event(db, submission.id, "schema_policy", "fail", {"missing": missing})
        submission.verification_status = "rejected"
        submission.reject_reason = "schema_policy"
        return "rejected"
    _event(db, submission.id, "schema_policy", "pass", {"keys": list(REQUIRED_LABEL_KEYS)})

    # 3. Provenance — allowlist host check (enabled hosts only)
    allowed, host, fail_code = is_host_allowed(db, submission.source_url)
    if not allowed:
        message = (
            f"Source host '{host or '(empty)'}' is not on the Phase-0 allowlist "
            "(or is disabled). Use a public EN news/official host from the allowlist. "
            "Online-only OSINT — no conflict-zone field collection."
        )
        _event(
            db,
            submission.id,
            "provenance",
            "fail",
            {
                "host": host,
                "reason": fail_code or "host_not_allowlisted",
                "message": message,
            },
        )
        submission.verification_status = "rejected"
        submission.reject_reason = "allowlist_reject"
        meta = dict(meta)
        meta["allowlist_failure"] = {
            "host": host,
            "code": fail_code or "host_not_allowlisted",
            "message": message,
        }
        submission.metadata_json = meta
        return "rejected"
    _event(
        db,
        submission.id,
        "provenance",
        "pass",
        {"host": host, "license_claim": meta.get("license_claim")},
    )

    # 4. Duplicate — file_hash (content hash of url+labels)
    file_hash = _hash_payload(submission.source_url, labels)
    submission.file_hash = file_hash
    dup = (
        db.query(Submission)
        .filter(
            Submission.campaign_id == submission.campaign_id,
            Submission.file_hash == file_hash,
            Submission.id != submission.id,
            Submission.verification_status.in_(["needs_review", "accepted", "in_review", "submitted"]),
        )
        .first()
    )
    if dup:
        _event(db, submission.id, "duplicate", "fail", {"duplicate_of": dup.id, "file_hash": file_hash})
        submission.verification_status = "rejected"
        submission.reject_reason = "duplicate"
        return "rejected"
    _event(db, submission.id, "duplicate", "pass", {"file_hash": file_hash})

    # 5. Fraud signals (stub — always low)
    submission.fraud_score = 0.05
    _event(db, submission.id, "fraud", "pass", {"fraud_score": 0.05, "stub": True})

    # 6. Synthetic / deepfake (stub — OSINT labels are meta, low risk)
    submission.synthetic_score = 0.0
    _event(db, submission.id, "synthetic", "pass", {"synthetic_score": 0.0, "stub": True})

    # 7. Quality (stub — heuristic)
    submission.quality_score = 0.8
    _event(db, submission.id, "quality", "pass", {"quality_score": 0.8, "stub": True})

    # 8. Route — Phase-0 default needs_review
    _event(
        db,
        submission.id,
        "route",
        "needs_review",
        {"policy": "phase0_manual_default", "auto_accept": False},
    )
    submission.verification_status = "needs_review"
    return "needs_review"
