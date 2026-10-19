from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Campaign, Dataset, User
from app.schemas import DatasetOut
from app.services import storage as object_storage
from app.services.export import build_dataset_export

router = APIRouter(prefix="/api", tags=["datasets"])


def _with_url(d: Dataset) -> DatasetOut:
    out = DatasetOut.model_validate(d)
    out.download_url = f"/api/datasets/{d.id}/download"
    if d.export_storage_key:
        out.presigned_url = object_storage.presign_get_url(d.export_storage_key, kind="exports")
    return out


@router.post("/campaigns/{campaign_id}/export", response_model=DatasetOut)
def export_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if user.role == "buyer" and campaign.organization_id != user.org_id:
        raise HTTPException(403, "Forbidden")
    if user.role not in ("buyer", "admin"):
        raise HTTPException(403, "Forbidden")

    dataset = build_dataset_export(db, campaign=campaign, actor_id=user.id)
    db.commit()
    db.refresh(dataset)
    return _with_url(dataset)


@router.get("/datasets", response_model=List[DatasetOut])
def list_datasets(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    campaign_id: Optional[int] = None,
):
    q = db.query(Dataset)
    if user.role == "buyer":
        if not user.org_id:
            return []
        q = q.filter(Dataset.organization_id == user.org_id)
    if campaign_id:
        q = q.filter(Dataset.campaign_id == campaign_id)
    return [_with_url(d) for d in q.order_by(Dataset.id.desc()).all()]


@router.get("/datasets/{dataset_id}/download")
def download_dataset(
    dataset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    redirect: bool = Query(
        False,
        description="If true and S3 presign is available, 302 to the presigned URL",
    ),
):
    dataset = db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(404, "Not found")
    if user.role == "buyer" and dataset.organization_id != user.org_id:
        raise HTTPException(403, "Forbidden")
    if user.role not in ("buyer", "admin"):
        raise HTTPException(403, "Forbidden")
    if not dataset.export_storage_key:
        raise HTTPException(404, "Export file missing")

    if redirect:
        url = object_storage.presign_get_url(dataset.export_storage_key, kind="exports")
        if url:
            return RedirectResponse(url=url, status_code=302)

    raw = object_storage.get_bytes(dataset.export_storage_key, kind="exports")
    filename = object_storage.export_filename(dataset.export_storage_key)
    return Response(
        content=raw,
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/ledger")
def list_ledger(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.models import CreditLedger
    from app.schemas import LedgerOut

    q = db.query(CreditLedger)
    if user.role == "contributor":
        q = q.filter(CreditLedger.user_id == user.id)
    elif user.role == "buyer":
        q = q.filter(CreditLedger.organization_id == user.org_id)
    # admin sees all
    rows = q.order_by(CreditLedger.id.desc()).limit(100).all()
    return [LedgerOut.model_validate(r) for r in rows]
