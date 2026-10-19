from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.campaign_types import is_cv_campaign
from app.database import get_db
from app.deps import get_current_user, require_role
from app.models import Campaign, Submission, User, VerificationEvent
from app.schemas import (
    ReviewDecision,
    SubmissionCreate,
    SubmissionOut,
    VerificationEventOut,
)
from app.services.credits import grant_reward
from app.services.media import resolve_storage_key
from app.services.verification import run_automated_stages

router = APIRouter(prefix="/api", tags=["submissions"])


@router.post("/submissions", response_model=SubmissionOut)
def create_submission(
    body: SubmissionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("contributor")),
):
    if not user.terms_accepted:
        raise HTTPException(400, "Contributor must accept terms")
    campaign = db.get(Campaign, body.campaign_id)
    if not campaign or campaign.status != "active":
        raise HTTPException(400, "Campaign is not active")

    source_url = (body.source_url or "").strip()
    storage_key = (body.storage_key or "").strip() or None

    if is_cv_campaign(campaign.data_type):
        if not body.annotation:
            raise HTTPException(400, "CV campaign requires annotation (category, caption, bboxes)")
        if not source_url and not storage_key:
            raise HTTPException(400, "CV submission needs media URL and/or storage_key from upload")
        if storage_key:
            # Ensure key exists on disk
            path = resolve_storage_key(storage_key)
            if not path.is_file():
                raise HTTPException(400, "storage_key not found; upload media first")
        labels = body.annotation.model_dump()
        meta = {
            "claimed_capture_time": body.claimed_capture_time,
            "license_claim": body.license_claim,
            "corridor": "online_only_en",
            "template": "cv_media",
            "content_type": body.content_type,
            "sha256": body.sha256,
            "claims_synthetic": body.claims_synthetic,
            "safety": "no_conflict_zone_field_collection",
        }
    else:
        if not body.labels:
            raise HTTPException(400, "OSINT campaign requires labels")
        if not source_url:
            raise HTTPException(400, "OSINT submission requires source_url")
        labels = body.labels.model_dump()
        meta = {
            "claimed_capture_time": body.claimed_capture_time,
            "license_claim": body.license_claim,
            "corridor": "online_only_en",
            "template": "osint_label",
        }

    submission = Submission(
        campaign_id=campaign.id,
        contributor_id=user.id,
        source_url=source_url,
        storage_key=storage_key,
        labels_json=labels,
        metadata_json=meta,
        verification_status="submitted",
    )
    db.add(submission)
    db.flush()

    run_automated_stages(db, submission, campaign)
    db.commit()
    db.refresh(submission)
    return submission


@router.get("/submissions", response_model=List[SubmissionOut])
def list_submissions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    status: Optional[str] = None,
    campaign_id: Optional[int] = None,
):
    q = db.query(Submission)
    if user.role == "contributor":
        q = q.filter(Submission.contributor_id == user.id)
    elif user.role == "buyer":
        if not user.org_id:
            return []
        campaign_ids = [
            c.id
            for c in db.query(Campaign).filter(Campaign.organization_id == user.org_id).all()
        ]
        q = q.filter(Submission.campaign_id.in_(campaign_ids or [-1]))
    if status:
        q = q.filter(Submission.verification_status == status)
    if campaign_id:
        q = q.filter(Submission.campaign_id == campaign_id)
    return q.order_by(Submission.id.desc()).all()


@router.get("/submissions/{submission_id}", response_model=SubmissionOut)
def get_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    s = db.get(Submission, submission_id)
    if not s:
        raise HTTPException(404, "Not found")
    if user.role == "contributor" and s.contributor_id != user.id:
        raise HTTPException(403, "Forbidden")
    return s


@router.get("/submissions/{submission_id}/events", response_model=List[VerificationEventOut])
def submission_events(
    submission_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    s = db.get(Submission, submission_id)
    if not s:
        raise HTTPException(404, "Not found")
    if user.role == "contributor" and s.contributor_id != user.id:
        raise HTTPException(403, "Forbidden")
    return (
        db.query(VerificationEvent)
        .filter(VerificationEvent.submission_id == submission_id)
        .order_by(VerificationEvent.id.asc())
        .all()
    )


@router.get("/review-queue", response_model=List[SubmissionOut])
def review_queue(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
):
    return (
        db.query(Submission)
        .filter(Submission.verification_status == "needs_review")
        .order_by(Submission.id.asc())
        .all()
    )


@router.post("/submissions/{submission_id}/review", response_model=SubmissionOut)
def review_submission(
    submission_id: int,
    body: ReviewDecision,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    submission = db.get(Submission, submission_id)
    if not submission:
        raise HTTPException(404, "Not found")
    if submission.verification_status != "needs_review":
        raise HTTPException(400, f"Not in needs_review (status={submission.verification_status})")

    campaign = db.get(Campaign, submission.campaign_id)
    contributor = db.get(User, submission.contributor_id)
    if not campaign or not contributor:
        raise HTTPException(400, "Missing campaign/contributor")

    # CV-sensitive reason codes for Admin KO ops
    if not body.accept and body.reason_code in (
        "sensitive_person",
        "sensitive_facility",
        "synthetic_suspected",
        "conflict_zone_field",
    ):
        pass  # accepted as valid reject codes

    if body.accept:
        try:
            reward = grant_reward(
                db,
                submission=submission,
                campaign=campaign,
                contributor=contributor,
                quality_mult=body.quality_mult,
            )
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        submission.verification_status = "accepted"
        db.add(
            VerificationEvent(
                submission_id=submission.id,
                stage="manual",
                result="accepted",
                detail_json={
                    "reason_code": body.reason_code,
                    "internal_memo_ko": body.internal_memo_ko,
                    "reward": reward,
                    "template": campaign.data_type,
                },
                actor_id=admin.id,
            )
        )
    else:
        submission.verification_status = "rejected"
        submission.reject_reason = body.reason_code or "manual_reject"
        contributor.reputation_score = round(max(contributor.reputation_score - 0.5, 0), 2)
        db.add(
            VerificationEvent(
                submission_id=submission.id,
                stage="manual",
                result="rejected",
                detail_json={
                    "reason_code": body.reason_code,
                    "internal_memo_ko": body.internal_memo_ko,
                    "template": campaign.data_type,
                },
                actor_id=admin.id,
            )
        )

    db.commit()
    db.refresh(submission)
    return submission
