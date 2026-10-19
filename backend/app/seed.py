from __future__ import annotations

from sqlalchemy.orm import Session

from app.allowlist_v0 import ALLOWLIST_V0
from app.models import AllowlistHost, Organization, User


def seed_allowlist_v0(db: Session) -> dict:
    """Upsert Phase-0 allowlist hosts (idempotent). Does not re-enable disabled rows."""
    inserted = 0
    skipped = 0
    for host, category in ALLOWLIST_V0:
        existing = db.query(AllowlistHost).filter(AllowlistHost.host == host).first()
        if existing:
            # Keep admin disable; refresh category label if still seeded category family
            if existing.category in (
                "placeholder",
                "",
            ) or existing.category.startswith("us_") or existing.category in {
                c for _, c in ALLOWLIST_V0
            }:
                if existing.category == "placeholder":
                    existing.category = category
            skipped += 1
            continue
        db.add(AllowlistHost(host=host, category=category, enabled=True))
        inserted += 1
    db.commit()
    return {"inserted": inserted, "skipped": skipped, "total_v0": len(ALLOWLIST_V0)}


def seed_demo(db: Session) -> dict:
    """Idempotent demo users + allowlist v0 sync."""
    allowlist_stats = seed_allowlist_v0(db)

    existing = db.query(User).filter(User.email == "admin@demo.local").first()
    if existing:
        return {
            "seeded": False,
            "message": "already seeded",
            "allowlist": allowlist_stats,
        }

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

    db.commit()
    return {
        "seeded": True,
        "users": {
            "admin": {"id": admin.id, "email": admin.email},
            "buyer": {"id": buyer.id, "email": buyer.email, "org_id": org.id},
            "contributor": {"id": contributor.id, "email": contributor.email},
        },
        "org": {"id": org.id, "kyb_status": org.kyb_status},
        "allowlist": allowlist_stats,
    }
