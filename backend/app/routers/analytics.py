"""Admin-only Phase-0 ops analytics (funnel / outcomes / credits)."""

from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_role
from app.models import Campaign, CreditLedger, Organization, Submission, User
from app.schemas import (
    AdminAnalyticsOut,
    CampaignAnalyticsRow,
    CountByKey,
    CreditsSummary,
    FunnelRates,
)

router = APIRouter(prefix="/api/admin/analytics", tags=["admin-analytics"])


def _counts_by(rows: List[tuple]) -> List[CountByKey]:
    return [CountByKey(key=str(k) if k is not None else "unknown", count=int(c)) for k, c in rows]


@router.get("", response_model=AdminAnalyticsOut)
def admin_analytics(
    _admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> AdminAnalyticsOut:
    """Aggregate campaign funnel, submission outcomes, and credit totals for founder ops."""

    campaign_rows = (
        db.query(Campaign.status, func.count(Campaign.id)).group_by(Campaign.status).all()
    )
    campaigns_by_status = _counts_by(campaign_rows)
    campaigns_total = sum(r.count for r in campaigns_by_status)

    submission_rows = (
        db.query(Submission.verification_status, func.count(Submission.id))
        .group_by(Submission.verification_status)
        .all()
    )
    submissions_by_status = _counts_by(submission_rows)
    status_map: Dict[str, int] = {r.key: r.count for r in submissions_by_status}
    submissions_total = sum(status_map.values())
    accepted = status_map.get("accepted", 0)
    rejected = status_map.get("rejected", 0)
    needs_review = status_map.get("needs_review", 0) + status_map.get("needs_2nd_review", 0)
    in_review = status_map.get("in_review", 0) + status_map.get("submitted", 0)
    decided = accepted + rejected
    accept_rate = (accepted / decided) if decided else None
    reject_rate = (rejected / decided) if decided else None

    reject_reason_rows = (
        db.query(Submission.reject_reason, func.count(Submission.id))
        .filter(Submission.verification_status == "rejected")
        .group_by(Submission.reject_reason)
        .all()
    )
    reject_reasons = _counts_by(reject_reason_rows)

    reward_sum = (
        db.query(func.coalesce(func.sum(CreditLedger.amount), 0.0))
        .filter(CreditLedger.type == "reward")
        .scalar()
    )
    pool_funded = (
        db.query(func.coalesce(func.sum(CreditLedger.amount), 0.0))
        .filter(CreditLedger.type == "pool_fund")
        .scalar()
    )
    reward_count = (
        db.query(func.count(CreditLedger.id)).filter(CreditLedger.type == "reward").scalar()
    )
    contributor_balances = (
        db.query(func.coalesce(func.sum(User.credit_balance), 0.0))
        .filter(User.role == "contributor")
        .scalar()
    )

    kyb_rows = (
        db.query(Organization.kyb_status, func.count(Organization.id))
        .group_by(Organization.kyb_status)
        .all()
    )
    orgs_by_kyb = _counts_by(kyb_rows)

    # Per-campaign: submission counts + accepted/rejected + remaining pool
    campaigns = db.query(Campaign).order_by(Campaign.id.asc()).all()
    per_campaign: List[CampaignAnalyticsRow] = []
    for camp in campaigns:
        sub_counts = (
            db.query(Submission.verification_status, func.count(Submission.id))
            .filter(Submission.campaign_id == camp.id)
            .group_by(Submission.verification_status)
            .all()
        )
        smap = {str(k): int(c) for k, c in sub_counts}
        total = sum(smap.values())
        acc = smap.get("accepted", 0)
        rej = smap.get("rejected", 0)
        rewards = (
            db.query(func.coalesce(func.sum(CreditLedger.amount), 0.0))
            .filter(
                CreditLedger.campaign_id == camp.id,
                CreditLedger.type == "reward",
            )
            .scalar()
        )
        per_campaign.append(
            CampaignAnalyticsRow(
                campaign_id=camp.id,
                title=camp.title,
                data_type=camp.data_type,
                status=camp.status,
                submissions_total=total,
                accepted=acc,
                rejected=rej,
                needs_review=smap.get("needs_review", 0),
                reward_pool=camp.reward_pool,
                reward_remaining=camp.reward_remaining,
                credits_granted=float(rewards or 0.0),
            )
        )

    return AdminAnalyticsOut(
        campaigns_total=campaigns_total,
        campaigns_by_status=campaigns_by_status,
        submissions_total=submissions_total,
        submissions_by_status=submissions_by_status,
        funnel=FunnelRates(
            accepted=accepted,
            rejected=rejected,
            needs_review=needs_review,
            pending_verify=in_review,
            decided=decided,
            accept_rate=accept_rate,
            reject_rate=reject_rate,
        ),
        reject_reasons=reject_reasons,
        credits=CreditsSummary(
            rewards_granted_total=float(reward_sum or 0.0),
            reward_entries=int(reward_count or 0),
            pool_funded_total=float(pool_funded or 0.0),
            contributor_balances_total=float(contributor_balances or 0.0),
        ),
        orgs_by_kyb=orgs_by_kyb,
        per_campaign=per_campaign,
    )
