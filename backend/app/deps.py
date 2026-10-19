from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth_jwt import verify_access_token
from app.database import get_db
from app.identity import upsert_user_from_claims
from app.models import User

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Require Authorization: Bearer <session JWT> (Clerk or local dev)."""
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization Bearer token (sign in via Clerk or POST /api/auth/dev-login)",
        )
    claims = verify_access_token(creds.credentials)
    user = upsert_user_from_claims(db, claims)
    if user.status != "active":
        raise HTTPException(status_code=401, detail="User inactive")
    return user


def get_optional_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if creds is None or not creds.credentials:
        return None
    try:
        claims = verify_access_token(creds.credentials)
        user = upsert_user_from_claims(db, claims)
    except HTTPException:
        return None
    if not user or user.status != "active":
        return None
    return user


def require_role(*roles: str):
    def _inner(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail=f"Requires role in {roles}")
        return user

    return _inner
