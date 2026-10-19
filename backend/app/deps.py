from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User


def get_current_user(
    x_user_id: int | None = Header(default=None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> User:
    """Demo auth: pass X-User-Id header. Real Clerk/Supabase deferred."""
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="Missing X-User-Id header (demo auth)")
    user = db.get(User, x_user_id)
    if not user or user.status != "active":
        raise HTTPException(status_code=401, detail="Invalid user")
    return user


def require_role(*roles: str):
    def _inner(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail=f"Requires role in {roles}")
        return user

    return _inner
