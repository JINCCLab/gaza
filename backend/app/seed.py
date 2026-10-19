from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import settings
from app.models import AllowlistHost, Organization, User


def seed_demo(db: Session) -> dict:
    """Idempotent demo users + allowlist placeholders."""
    existing = db.query(User).filter(User.email == "admin@demo.local").first()
    if existing:
        return {"seeded": False, "message": "already seeded"}

    admin = User(
        email="admin@demo.local",
        display_name="Admin (Founder)",
        role="admin",
        terms_accepted=True,
        kyc_status="not_required",
    )
    db.add(admin)
    db.flush()

    buyer = User(
        email="buyer@demo.local",
        display_name="Buyer Ops",
        role="buyer",
        terms_accepted=True,
        kyc_status="not_required",
    )
    db.add(buyer)
    db.flush()

    org = Organization(
        name="Demo OSINT Intel Firm",
        owner_user_id=buyer.id,
        kyb_status="pending",
        intended_use="Structured OSINT event/equipment labeling for media intel research (public sources only).",
    )
    db.add(org)
    db.flush()
    buyer.org_id = org.id

    contributor = User(
        email="contributor@demo.local",
        display_name="EN Contributor",
        role="contributor",
        terms_accepted=True,
        country="US",
        kyc_status="not_required",
    )
    db.add(contributor)

    for host in settings.default_allowlist_hosts:
        db.add(AllowlistHost(host=host, category="placeholder"))

    db.commit()
    return {
        "seeded": True,
        "users": {
            "admin": {"id": admin.id, "email": admin.email},
            "buyer": {"id": buyer.id, "email": buyer.email, "org_id": org.id},
            "contributor": {"id": contributor.id, "email": contributor.email},
        },
        "org": {"id": org.id, "kyb_status": org.kyb_status},
    }
