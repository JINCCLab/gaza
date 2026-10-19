from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Organization, User
from app.schemas import OrgOut, UserOut
from app.seed import seed_demo

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/seed")
def seed(db: Session = Depends(get_db)):
    return seed_demo(db)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    """Demo helper: list seed users for role switcher."""
    return db.query(User).order_by(User.id).all()


@router.get("/orgs", response_model=list[OrgOut])
def list_orgs(db: Session = Depends(get_db)):
    return db.query(Organization).order_by(Organization.id).all()
