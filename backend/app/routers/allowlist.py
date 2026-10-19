from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_role
from app.models import AllowlistHost, User
from app.schemas import AllowlistHostCreate, AllowlistHostOut
from app.services.allowlist import normalize_host

router = APIRouter(prefix="/api/allowlist", tags=["allowlist"])


@router.get("", response_model=list[AllowlistHostOut])
def list_hosts(db: Session = Depends(get_db)):
    return db.query(AllowlistHost).order_by(AllowlistHost.host).all()


@router.post("", response_model=AllowlistHostOut)
def add_host(
    body: AllowlistHostCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
):
    host = normalize_host(body.host)
    if not host:
        raise HTTPException(400, "Invalid host")
    existing = db.query(AllowlistHost).filter(AllowlistHost.host == host).first()
    if existing:
        return existing
    row = AllowlistHost(host=host, category=body.category)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
