from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth_jwt import issue_dev_token, verify_access_token
from app.config import settings
from app.database import get_db
from app.deps import get_current_user, require_role
from app.identity import subject_for_dev_email, upsert_user_from_claims
from app.models import Organization, User
from app.schemas import OrgOut, UserOut
from app.seed import seed_demo

router = APIRouter(prefix="/api", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


class DevLoginIn(BaseModel):
    email: str = Field(..., description="Seeded persona email, e.g. admin@demo.local")


class DevLoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    auth_mode: str = "dev"
    user: UserOut


class AuthConfigOut(BaseModel):
    mode: str
    configured_mode: str
    clerk_ready: bool
    message: str
    has_clerk_publishable_key: bool


@router.get("/auth/config", response_model=AuthConfigOut)
def auth_config():
    mode = settings.resolved_auth_mode()
    clerk_ready = bool(settings.clerk_secret_key and settings.clerk_jwks_endpoint())
    if mode == "clerk":
        msg = "Clerk JWT verification enabled. Send Authorization: Bearer <session token>."
    else:
        msg = (
            "Dev session mode (no Clerk keys). Sign in via POST /api/auth/dev-login "
            "or the UI /sign-in page; X-User-Id is retired."
        )
    return AuthConfigOut(
        mode=mode,
        configured_mode=settings.auth_mode,
        clerk_ready=clerk_ready,
        message=msg,
        has_clerk_publishable_key=bool(settings.clerk_publishable_key),
    )


@router.post("/auth/dev-login", response_model=DevLoginOut)
def dev_login(body: DevLoginIn, db: Session = Depends(get_db)):
    """Issue a local HS256 session JWT for seeded personas. Disabled when Clerk is active."""
    if settings.resolved_auth_mode() != "dev":
        raise HTTPException(
            status_code=403,
            detail="Dev login disabled while Clerk is active (set AUTH_MODE=dev to force local sessions)",
        )
    seed_demo(db)
    email = body.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Unknown user {email}. Seed personas: "
                "admin@demo.local, buyer@demo.local, contributor@demo.local"
            ),
        )
    if not user.auth_subject:
        user.auth_subject = subject_for_dev_email(user.email)
        db.commit()
        db.refresh(user)
    token = issue_dev_token(
        subject=user.auth_subject,
        email=user.email,
        role=user.role,
        display_name=user.display_name,
    )
    return DevLoginOut(access_token=token, user=UserOut.model_validate(user))


@router.post("/seed")
def seed(db: Session = Depends(get_db)):
    return seed_demo(db)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.get("/auth/personas", response_model=List[UserOut])
def list_dev_personas(db: Session = Depends(get_db)):
    """Dev-only: seeded personas for the /sign-in page (no Act-as header)."""
    if settings.resolved_auth_mode() != "dev":
        raise HTTPException(status_code=403, detail="Persona list only available in dev auth mode")
    seed_demo(db)
    return db.query(User).order_by(User.id).all()


@router.get("/users", response_model=List[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    return db.query(User).order_by(User.id).all()


@router.get("/orgs", response_model=List[OrgOut])
def list_orgs(
    db: Session = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
):
    """Authenticated list; still public-readable in Phase-0 for buyer home after sign-in."""
    if creds and creds.credentials:
        claims = verify_access_token(creds.credentials)
        upsert_user_from_claims(db, claims)
    from app.routers.orgs import org_to_out

    return [org_to_out(o) for o in db.query(Organization).order_by(Organization.id).all()]
