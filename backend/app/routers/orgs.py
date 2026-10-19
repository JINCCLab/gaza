from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_role
from app.models import AuditLog, Organization, User
from app.schemas import KybDecision, OrgCreate, OrgOut

router = APIRouter(prefix="/api/orgs", tags=["orgs"])


@router.post("", response_model=OrgOut)
def create_org(
    body: OrgCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("buyer")),
):
    if user.org_id:
        raise HTTPException(400, "Buyer already belongs to an org")
    org = Organization(
        name=body.name,
        owner_user_id=user.id,
        kyb_status="pending",
        intended_use=body.intended_use,
    )
    db.add(org)
    db.flush()
    user.org_id = org.id
    db.add(
        AuditLog(
            actor_id=user.id,
            action="org_create",
            entity_type="organization",
            entity_id=org.id,
            detail_json={"name": org.name},
        )
    )
    db.commit()
    db.refresh(org)
    return org


@router.get("/{org_id}", response_model=OrgOut)
def get_org(org_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Org not found")
    if user.role != "admin" and user.org_id != org.id:
        raise HTTPException(403, "Forbidden")
    return org


@router.post("/{org_id}/kyb", response_model=OrgOut)
def decide_kyb(
    org_id: int,
    body: KybDecision,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Org not found")
    org.kyb_status = "approved" if body.approve else "rejected"
    org.kyb_notes = body.notes
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="kyb_decision",
            entity_type="organization",
            entity_id=org.id,
            detail_json={"kyb_status": org.kyb_status, "notes": body.notes},
        )
    )
    db.commit()
    db.refresh(org)
    return org
