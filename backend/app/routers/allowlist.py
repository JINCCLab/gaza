from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_optional_user, require_role
from app.models import AllowlistHost, User
from app.schemas import AllowlistHostCreate, AllowlistHostOut, AllowlistHostUpdate
from app.services.allowlist import normalize_host

router = APIRouter(prefix="/api/allowlist", tags=["allowlist"])


@router.get("", response_model=List[AllowlistHostOut])
def list_hosts(
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
    enabled_only: bool = Query(default=False),
):
    """
    Non-admin (or anonymous) callers only see enabled hosts.
    Admin sees all unless enabled_only=true.
    """
    q = db.query(AllowlistHost)
    if enabled_only or not user or user.role != "admin":
        q = q.filter(AllowlistHost.enabled.is_(True))
    return q.order_by(AllowlistHost.category.asc(), AllowlistHost.host.asc()).all()

@router.post("", response_model=AllowlistHostOut)
def add_host(
    body: AllowlistHostCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
):
    host = normalize_host(body.host)
    if not host:
        raise HTTPException(400, "Invalid host")
    # Store apex form when www. provided
    if host.startswith("www."):
        host = host[4:]
    existing = db.query(AllowlistHost).filter(AllowlistHost.host == host).first()
    if existing:
        if not existing.enabled:
            existing.enabled = True
        if body.category:
            existing.category = body.category
        db.commit()
        db.refresh(existing)
        return existing
    row = AllowlistHost(host=host, category=body.category or "admin_added", enabled=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{host_id}", response_model=AllowlistHostOut)
def update_host(
    host_id: int,
    body: AllowlistHostUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
):
    row = db.get(AllowlistHost, host_id)
    if not row:
        raise HTTPException(404, "Host not found")
    if body.enabled is not None:
        row.enabled = body.enabled
    if body.category is not None:
        row.category = body.category
    db.commit()
    db.refresh(row)
    return row


@router.post("/{host_id}/disable", response_model=AllowlistHostOut)
def disable_host(
    host_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
):
    row = db.get(AllowlistHost, host_id)
    if not row:
        raise HTTPException(404, "Host not found")
    row.enabled = False
    db.commit()
    db.refresh(row)
    return row


@router.post("/{host_id}/enable", response_model=AllowlistHostOut)
def enable_host(
    host_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
):
    row = db.get(AllowlistHost, host_id)
    if not row:
        raise HTTPException(404, "Host not found")
    row.enabled = True
    db.commit()
    db.refresh(row)
    return row
