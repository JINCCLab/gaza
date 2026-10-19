from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Campaign, CreditLedger, Submission, User


def fund_campaign_pool(
    db: Session,
    *,
    campaign: Campaign,
    organization_id: int,
    amount: float,
    actor_user_id: Optional[int] = None,
) -> None:
    """Record pool_fund. Fee stub: platform_fee_pct recorded separately, pool gets net."""
    fee = round(amount * settings.platform_fee_pct, 2)
    net = round(amount - fee, 2)
    campaign.reward_pool = round(campaign.reward_pool + net, 2)
    campaign.reward_remaining = round(campaign.reward_remaining + net, 2)

    db.add(
        CreditLedger(
            user_id=actor_user_id,
            organization_id=organization_id,
            campaign_id=campaign.id,
            type="pool_fund",
            amount=net,
            balance_after=campaign.reward_remaining,
            note=f"gross={amount} fee={fee} ({int(settings.platform_fee_pct * 100)}%)",
        )
    )
    if fee > 0:
        db.add(
            CreditLedger(
                organization_id=organization_id,
                campaign_id=campaign.id,
                type="fee",
                amount=-fee,
                balance_after=None,
                note="platform fee on deposit (stub accounting)",
            )
        )


def grant_reward(
    db: Session,
    *,
    submission: Submission,
    campaign: Campaign,
    contributor: User,
    quality_mult: float = 1.0,
) -> float:
    mult = min(max(quality_mult, 0.0), settings.quality_mult_cap)
    reward = round(campaign.unit_reward * mult, 2)
    if campaign.reward_remaining < reward:
        raise ValueError("Insufficient campaign reward pool")

    campaign.reward_remaining = round(campaign.reward_remaining - reward, 2)
    contributor.credit_balance = round(contributor.credit_balance + reward, 2)
    contributor.redeem_reserve = round(contributor.redeem_reserve + reward, 2)
    contributor.reputation_score = round(contributor.reputation_score + 1.0, 2)
    submission.final_reward = reward

    db.add(
        CreditLedger(
            user_id=contributor.id,
            organization_id=campaign.organization_id,
            campaign_id=campaign.id,
            submission_id=submission.id,
            type="reward",
            amount=reward,
            balance_after=contributor.credit_balance,
            note=f"unit={campaign.unit_reward} mult={mult}",
        )
    )
    db.add(
        CreditLedger(
            user_id=contributor.id,
            campaign_id=campaign.id,
            submission_id=submission.id,
            type="redeem_reserve",
            amount=reward,
            balance_after=contributor.redeem_reserve,
            note="Phase-0 locked redeem; Phase-1 token path TBD",
        )
    )
    return reward
