import hashlib
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.campaign_types import allowed_cv_categories, is_cv_campaign
from app.config import settings
from app.models import Campaign, Submission, VerificationEvent
from app.ontology_registry import get_ontology, resolve_pin, validate_labels_against_ontology
from app.services.allowlist import is_host_allowed
from app.services.dual_annotate import mark_dual_required, should_require_dual
from app.services.url_quality import (
    check_url_reachability,
    contributor_reject_message,
    normalize_url_for_hash,
    validate_url_shape,
)


REQUIRED_LABEL_KEYS = ("event_type", "location_public", "event_time", "equipment_type")
ALLOWED_UPLOAD_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/webp", "video/mp4"}
)


def _reject(
    submission: Submission,
    *,
    reason: str,
    detail: Optional[Dict[str, Any]] = None,
) -> str:
    detail = detail or {}
    meta = dict(submission.metadata_json or {})
    msg = contributor_reject_message(reason, detail)
    meta["reject_message"] = msg
    meta["reject_detail"] = detail
    submission.metadata_json = meta
    submission.verification_status = "rejected"
    submission.reject_reason = reason
    return "rejected"


def _url_check_enabled() -> bool:
    mode = (settings.url_reachability or "auto").lower()
    if mode == "off":
        return False
    return True  # auto and on both probe


def _url_unreachable_rejects() -> bool:
    """Reject on unreachable only when URL_REACHABILITY=on. auto = flag only (smoke-safe)."""
    return (settings.url_reachability or "auto").lower() == "on"


def _campaign_ontology(campaign: Campaign):
    """Load ontology pinned on campaign (or default for data_type)."""
    try:
        if campaign.ontology_id and campaign.schema_version:
            return get_ontology(campaign.ontology_id, campaign.schema_version)
        _, _, doc = resolve_pin(
            campaign.data_type, campaign.ontology_id, campaign.schema_version
        )
        return doc
    except (KeyError, ValueError):
        return None


def _hash_payload(*parts: str) -> str:
    blob = "|".join(parts)
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
    Branches OSINT vs CV (cv_media) template verification.
    Returns final automated status: needs_review | rejected.
    """
    if is_cv_campaign(campaign.data_type):
        return _run_cv_stages(db, submission, campaign)
    return _run_osint_stages(db, submission, campaign)


def _run_osint_stages(db: Session, submission: Submission, campaign: Campaign) -> str:
    labels = submission.labels_json or {}
    meta = dict(submission.metadata_json or {})

    # 1. Technical — URL shape (https, no IP, no userinfo)
    shape_ok, shape_code, shape_msg = validate_url_shape(submission.source_url or "")
    if not shape_ok:
        detail = {"reason": shape_code, "message": shape_msg}
        _event(db, submission.id, "technical", "fail", detail)
        reason = (
            "url_shape_reject"
            if shape_code
            in ("bad_scheme", "ip_literal", "url_userinfo", "missing_scheme", "empty_url")
            else "technical_invalid"
        )
        return _reject(submission, reason=reason, detail=detail)
    _event(db, submission.id, "technical", "pass", {"template": "osint", "url_shape": "ok"})

    # 2. Schema / policy — require pinned ontology enums (tighten Phase-0)
    onto = _campaign_ontology(campaign)
    if not onto:
        detail = {"errors": ["ontology_unavailable"], "message": "Campaign has no ontology pin."}
        _event(db, submission.id, "schema_policy", "fail", detail)
        return _reject(submission, reason="schema_policy", detail=detail)
    schema_ok, missing = validate_labels_against_ontology(
        onto,
        labels=labels,
        source_url=submission.source_url or "",
    )
    # Also intersect campaign requirements enums when present (stricter of the two)
    req = campaign.requirements_json or {}
    allowed_events = set(req.get("event_types") or [])
    allowed_equip = set(req.get("equipment_types") or [])
    if allowed_events and labels.get("event_type") not in allowed_events:
        schema_ok = False
        missing.append("event_type_not_in_campaign_enum")
    if allowed_equip and labels.get("equipment_type") not in allowed_equip:
        schema_ok = False
        missing.append("equipment_type_not_in_campaign_enum")
    detail = {
        "ontology_id": onto.get("ontology_id"),
        "schema_version": onto.get("schema_version"),
        "errors": missing,
        "message": contributor_reject_message("schema_policy", {"errors": missing}),
    }
    if not schema_ok:
        _event(db, submission.id, "schema_policy", "fail", detail)
        return _reject(submission, reason="schema_policy", detail=detail)
    _event(
        db,
        submission.id,
        "schema_policy",
        "pass",
        {
            "keys": list(onto.get("required_label_fields") or REQUIRED_LABEL_KEYS),
            "ontology_id": onto.get("ontology_id"),
            "schema_version": onto.get("schema_version"),
        },
    )

    # 3. Provenance — allowlist + shape (enabled hosts only)
    allowed, host, fail_code = is_host_allowed(db, submission.source_url)
    if not allowed:
        shape_codes = {
            "bad_scheme",
            "ip_literal",
            "url_userinfo",
            "missing_scheme",
            "empty_url",
            "invalid_host",
        }
        if fail_code in shape_codes:
            message = shape_msg or contributor_reject_message("url_shape_reject")
            reason = "url_shape_reject"
        else:
            message = (
                f"Source host '{host or '(empty)'}' is not on the Phase-0 allowlist "
                "(or is disabled). Use a public EN news/official host from the allowlist. "
                "Online-only OSINT — no conflict-zone field collection."
            )
            reason = "allowlist_reject"
        _event(
            db,
            submission.id,
            "provenance",
            "fail",
            {"host": host, "reason": fail_code or "host_not_allowlisted", "message": message},
        )
        meta["allowlist_failure"] = {
            "host": host,
            "code": fail_code or "host_not_allowlisted",
            "message": message,
        }
        submission.metadata_json = meta
        return _reject(
            submission,
            reason=reason,
            detail={"host": host, "code": fail_code, "message": message},
        )

    # 3b. Reachability stub (no scrape)
    reach = check_url_reachability(
        submission.source_url,
        timeout_s=float(settings.url_reachability_timeout_s),
        enabled=_url_check_enabled(),
    )
    meta["url_reachability"] = reach
    submission.metadata_json = meta
    if reach.get("checked") and reach.get("reachable") is False:
        if _url_unreachable_rejects():
            _event(db, submission.id, "provenance", "fail", {"reachability": reach})
            return _reject(
                submission,
                reason="url_unreachable",
                detail={
                    "reachability": reach,
                    "message": contributor_reject_message("url_unreachable"),
                },
            )
        _event(
            db,
            submission.id,
            "provenance",
            "flag",
            {"reachability": reach, "note": "auto mode; continuing to review"},
        )
    _event(
        db,
        submission.id,
        "provenance",
        "pass",
        {
            "host": host,
            "license_claim": meta.get("license_claim"),
            "reachability": reach,
        },
    )

    # 4. Duplicate — normalized URL + labels
    norm = normalize_url_for_hash(submission.source_url)
    meta["normalized_source_url"] = norm
    submission.metadata_json = meta
    file_hash = _hash_payload(norm, str(sorted((labels or {}).items())))
    return _finish_common(db, submission, campaign, file_hash, template="osint")


def _run_cv_stages(db: Session, submission: Submission, campaign: Campaign) -> str:
    labels = submission.labels_json or {}
    meta = dict(submission.metadata_json or {})
    req = campaign.requirements_json or {}

    # 1. Technical — media URL and/or local upload; content type check
    has_url = bool((submission.source_url or "").strip())
    has_file = bool((submission.storage_key or "").strip())
    if not has_url and not has_file:
        detail = {"reason": "missing_media", "hint": "Provide media URL or upload storage_key"}
        _event(db, submission.id, "technical", "fail", detail)
        return _reject(submission, reason="technical_invalid", detail=detail)
    if has_url:
        shape_ok, shape_code, shape_msg = validate_url_shape(submission.source_url or "")
        if not shape_ok:
            detail = {"reason": shape_code, "message": shape_msg}
            _event(db, submission.id, "technical", "fail", detail)
            return _reject(submission, reason="url_shape_reject", detail=detail)

    content_type = (meta.get("content_type") or "").lower()
    if has_file and content_type and content_type not in ALLOWED_UPLOAD_TYPES:
        detail = {"reason": "unsupported_media_type", "content_type": content_type}
        _event(db, submission.id, "technical", "fail", detail)
        return _reject(submission, reason="technical_invalid", detail=detail)
    _event(
        db,
        submission.id,
        "technical",
        "pass",
        {
            "template": "cv_media",
            "has_url": has_url,
            "has_file": has_file,
            "content_type": content_type or None,
        },
    )

    # 2. Schema — versioned ontology + category / caption / optional bboxes
    category = labels.get("category")
    caption = labels.get("caption")
    bboxes = labels.get("bboxes") or []
    missing = []
    onto = _campaign_ontology(campaign)
    if onto:
        ok, onto_errs = validate_labels_against_ontology(
            onto,
            labels=labels,
            source_url=submission.source_url or "",
            storage_key=submission.storage_key,
        )
        if not ok:
            missing.extend(onto_errs)
    else:
        if not category:
            missing.append("category")
        if not caption or not str(caption).strip():
            missing.append("caption")
        allowed_cats = allowed_cv_categories(req)
        if category and category not in allowed_cats:
            missing.append("category_not_in_whitelist")
    # Always validate bbox shape when present
    if not isinstance(bboxes, list):
        missing.append("bboxes_not_list")
    else:
        for i, box in enumerate(bboxes):
            if not isinstance(box, dict):
                missing.append(f"bbox_{i}_invalid")
                continue
            for k in ("x", "y", "w", "h"):
                try:
                    v = float(box.get(k))
                except (TypeError, ValueError):
                    missing.append(f"bbox_{i}_{k}")
                    continue
                if v < 0 or v > 1:
                    missing.append(f"bbox_{i}_{k}_range")
    if missing:
        detail = {
            "missing": missing,
            "errors": missing,
            "ontology_id": (onto or {}).get("ontology_id") if onto else None,
            "schema_version": (onto or {}).get("schema_version") if onto else None,
        }
        _event(db, submission.id, "schema_policy", "fail", detail)
        return _reject(submission, reason="schema_policy", detail=detail)
    whitelist = sorted(allowed_cv_categories(req))
    _event(
        db,
        submission.id,
        "schema_policy",
        "pass",
        {
            "category": category,
            "bbox_count": len(bboxes),
            "whitelist": whitelist,
            "ontology_id": (onto or {}).get("ontology_id") if onto else None,
            "schema_version": (onto or {}).get("schema_version") if onto else None,
        },
    )

    # 3. Provenance — allowlist if URL provided; uploads require license claim + public category
    if has_url:
        allowed, host, fail_code = is_host_allowed(db, submission.source_url)
        if not allowed:
            message = (
                f"CV media URL host '{host or '(empty)'}' is not on the Phase-0 allowlist "
                "(or is disabled). Use a public EN official/news host, or upload a local file "
                "from a whitelist public scene (parade/museum/official promo). "
                "No conflict-zone field collection."
            )
            _event(
                db,
                submission.id,
                "provenance",
                "fail",
                {"host": host, "reason": fail_code or "host_not_allowlisted", "message": message},
            )
            meta["allowlist_failure"] = {
                "host": host,
                "code": fail_code or "host_not_allowlisted",
                "message": message,
            }
            submission.metadata_json = meta
            return _reject(
                submission,
                reason="allowlist_reject",
                detail={"host": host, "code": fail_code, "message": message},
            )
        reach = check_url_reachability(
            submission.source_url,
            timeout_s=float(settings.url_reachability_timeout_s),
            enabled=_url_check_enabled(),
        )
        meta["url_reachability"] = reach
        submission.metadata_json = meta
        if reach.get("checked") and reach.get("reachable") is False and _url_unreachable_rejects():
            _event(db, submission.id, "provenance", "fail", {"reachability": reach})
            return _reject(
                submission,
                reason="url_unreachable",
                detail={"reachability": reach},
            )
        _event(
            db,
            submission.id,
            "provenance",
            "pass" if reach.get("reachable") is not False else "flag",
            {
                "host": host,
                "license_claim": meta.get("license_claim"),
                "mode": "url",
                "reachability": reach,
            },
        )
    else:
        if not meta.get("license_claim"):
            detail = {"reason": "missing_license_claim_for_upload"}
            _event(db, submission.id, "provenance", "fail", detail)
            return _reject(submission, reason="provenance", detail=detail)
        _event(
            db,
            submission.id,
            "provenance",
            "pass",
            {
                "mode": "upload",
                "license_claim": meta.get("license_claim"),
                "note": "upload path; category whitelist enforced in schema",
            },
        )

    # 4. Duplicate — normalized URL / storage key + annotation
    if submission.storage_key:
        media_id = submission.storage_key
    else:
        media_id = normalize_url_for_hash(submission.source_url or "")
        meta["normalized_source_url"] = media_id
        submission.metadata_json = meta
    content_hash = meta.get("sha256") or ""
    file_hash = _hash_payload(
        media_id,
        content_hash,
        str(category),
        str(caption).strip().lower(),
        str(bboxes),
    )
    return _finish_common(db, submission, campaign, file_hash, template="cv_media")


def _finish_common(
    db: Session,
    submission: Submission,
    campaign: Campaign,
    file_hash: str,
    *,
    template: str,
) -> str:
    meta = dict(submission.metadata_json or {})
    submission.file_hash = file_hash
    dup = (
        db.query(Submission)
        .filter(
            Submission.campaign_id == submission.campaign_id,
            Submission.file_hash == file_hash,
            Submission.id != submission.id,
            Submission.verification_status.in_(
                ["needs_review", "needs_2nd_review", "accepted", "in_review", "submitted"]
            ),
        )
        .first()
    )
    if dup:
        detail = {
            "duplicate_of": dup.id,
            "file_hash": file_hash,
            "message": contributor_reject_message("duplicate"),
        }
        _event(db, submission.id, "duplicate", "fail", detail)
        return _reject(submission, reason="duplicate", detail=detail)
    _event(db, submission.id, "duplicate", "pass", {"file_hash": file_hash})

    # 5. Fraud signals (stub)
    submission.fraud_score = 0.05
    _event(db, submission.id, "fraud", "pass", {"fraud_score": 0.05, "stub": True})

    # 6. Synthetic — CV: reject when campaign forbids synthetic but claim/flag set
    claims_synthetic = bool(meta.get("claims_synthetic"))
    if template == "cv_media" and not campaign.synthetic_allowed and claims_synthetic:
        detail = {
            "reason": "synthetic_not_allowed",
            "synthetic_allowed": False,
            "message": "Campaign synthetic_allowed=false (Phase-0 default). Real public scenes only.",
        }
        _event(db, submission.id, "synthetic", "fail", detail)
        submission.synthetic_score = 1.0
        return _reject(submission, reason="synthetic_not_allowed", detail=detail)
    submission.synthetic_score = 0.9 if claims_synthetic else 0.05 if template == "cv_media" else 0.0
    _event(
        db,
        submission.id,
        "synthetic",
        "pass" if not claims_synthetic else "flag",
        {
            "synthetic_score": submission.synthetic_score,
            "synthetic_allowed": campaign.synthetic_allowed,
            "claims_synthetic": claims_synthetic,
            "stub": True,
        },
    )

    # 7. Quality stub
    submission.quality_score = 0.75 if template == "cv_media" else 0.8
    _event(
        db,
        submission.id,
        "quality",
        "pass",
        {"quality_score": submission.quality_score, "stub": True},
    )

    # 8. Route — Phase-0 default needs_review (+ optional dual-annotator sample)
    dual = should_require_dual(db, campaign.id)
    if dual:
        meta = mark_dual_required(dict(submission.metadata_json or {}))
        submission.metadata_json = meta
    _event(
        db,
        submission.id,
        "route",
        "needs_review",
        {
            "policy": "phase0_manual_default",
            "auto_accept": False,
            "template": template,
            "dual_annotate_required": dual,
        },
    )
    submission.verification_status = "needs_review"
    return "needs_review"
