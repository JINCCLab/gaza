"""Map IdP claims → local User rows (roles: admin / buyer / contributor)."""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth_jwt import TokenClaims
from app.models import User

ALLOWED_ROLES = frozenset({"admin", "buyer", "contributor"})

# Seed emails keep fixed roles when metadata is absent.
SEED_ROLE_BY_EMAIL = {
    "admin@demo.local": "admin",
    "buyer@demo.local": "buyer",
    "contributor@demo.local": "contributor",
}


def resolve_role(claims: TokenClaims, existing: Optional[User] = None) -> str:
    if claims.role and claims.role in ALLOWED_ROLES:
        return claims.role
    email = (claims.email or "").lower()
    if email in SEED_ROLE_BY_EMAIL:
        return SEED_ROLE_BY_EMAIL[email]
    if existing and existing.role in ALLOWED_ROLES:
        return existing.role
    return "contributor"


def upsert_user_from_claims(db: Session, claims: TokenClaims) -> User:
    user = db.query(User).filter(User.auth_subject == claims.subject).first()
    if not user and claims.email:
        user = db.query(User).filter(User.email == claims.email.lower()).first()

    role = resolve_role(claims, user)
    display = claims.display_name or (claims.email.split("@")[0] if claims.email else claims.subject)

    if user:
        user.auth_subject = claims.subject
        if claims.email:
            user.email = claims.email.lower()
        if claims.display_name:
            user.display_name = claims.display_name
        # Allow Clerk publicMetadata.role to update; keep seed roles stable otherwise
        if claims.role and claims.role in ALLOWED_ROLES:
            user.role = claims.role
        db.commit()
        db.refresh(user)
        return user

    if not claims.email:
        raise HTTPException(
            status_code=401,
            detail="Token has no email; cannot provision local user",
        )

    user = User(
        email=claims.email.lower(),
        display_name=display,
        role=role,
        auth_subject=claims.subject,
        terms_accepted=True,
        kyc_status="not_required",
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def subject_for_dev_email(email: str) -> str:
    return f"dev:{email.lower()}"
