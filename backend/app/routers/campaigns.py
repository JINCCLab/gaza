from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_role
from app.models import AuditLog, Campaign, Organization, User
from app.schemas import CampaignCreate, CampaignDecision, CampaignOut
from app.services.credits import fund_campaign_pool

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


@router.get("", response_model=List[CampaignOut])
def list_campaigns(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    status: Optional[str] = None,
):
    q = db.query(Campaign)
    if user.role == "buyer":
        if not user.org_id:
            return []
        q = q.filter(Campaign.organization_id == user.org_id)
    elif user.role == "contributor":
        q = q.filter(Campaign.status == "active")
    if status:
        q = q.filter(Campaign.status == status)
    return q.order_by(Campaign.id.desc()).all()


@router.post("", response_model=CampaignOut)
def create_campaign(
    body: CampaignCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("buyer")),
):
    if not user.org_id:
        raise HTTPException(400, "Buyer has no org")
    org = db.get(Organization, user.org_id)
    if not org or org.kyb_status != "approved":
        raise HTTPException(403, "Org KYB must be approved before creating campaigns")

    campaign = Campaign(
        organization_id=org.id,
        title=body.title,
        description=body.description,
        data_type=body.data_type,
        data_class=body.data_class,
        target_region=body.target_region,
        requirements_json=body.requirements_json,
        synthetic_allowed=body.synthetic_allowed,
        target_quantity=body.target_quantity,
        unit_reward=body.unit_reward,
        status="draft",
    )
    db.add(campaign)
    db.flush()

    if body.pool_fund_amount > 0:
        fund_campaign_pool(
            db,
            campaign=campaign,
            organization_id=org.id,
            amount=body.pool_fund_amount,
            actor_user_id=user.id,
        )

    # Auto-submit for admin review when created with pool
    campaign.status = "pending_review"
    db.add(
        AuditLog(
            actor_id=user.id,
            action="campaign_create",
            entity_type="campaign",
            entity_id=campaign.id,
            detail_json={"status": campaign.status},
        )
    )
    db.commit()
    db.refresh(campaign)
    return campaign


@router.get("/{campaign_id}", response_model=CampaignOut)
def get_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if user.role == "contributor" and campaign.status != "active":
        raise HTTPException(404, "Campaign not found")
    if user.role == "buyer" and campaign.organization_id != user.org_id:
        raise HTTPException(403, "Forbidden")
    return campaign


@router.post("/{campaign_id}/submit-review", response_model=CampaignOut)
def submit_for_review(
    campaign_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("buyer")),
):
    campaign = db.get(Campaign, campaign_id)
    if not campaign or campaign.organization_id != user.org_id:
        raise HTTPException(404, "Campaign not found")
    if campaign.status not in ("draft", "rejected"):
        raise HTTPException(400, f"Cannot submit from status={campaign.status}")
    campaign.status = "pending_review"
    db.commit()
    db.refresh(campaign)
    return campaign


@router.post("/{campaign_id}/decide", response_model=CampaignOut)
def decide_campaign(
    campaign_id: int,
    body: CampaignDecision,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if campaign.status != "pending_review":
        raise HTTPException(400, "Campaign not pending_review")
    campaign.status = "active" if body.approve else "rejected"
    campaign.admin_notes = body.notes
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="campaign_decide",
            entity_type="campaign",
            entity_id=campaign.id,
            detail_json={"status": campaign.status, "notes": body.notes},
        )
    )
    db.commit()
    db.refresh(campaign)
    return campaign
