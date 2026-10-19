from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_role
from app.models import User
from app.schemas import MediaUploadOut
from app.services import media as media_service

router = APIRouter(prefix="/api/media", tags=["media"])


@router.post("/upload", response_model=MediaUploadOut)
async def upload_media(
    file: UploadFile = File(...),
    user: User = Depends(require_role("contributor")),
    db: Session = Depends(get_db),
):
    """CV media upload (local disk or S3). Returns storage_key for /api/submissions."""
    _ = db  # session available for future audit rows
    rel, content_type, size, digest = await media_service.save_upload(
        file, contributor_id=user.id
    )
    return MediaUploadOut(
        storage_key=rel,
        content_type=content_type,
        size_bytes=size,
        sha256=digest,
        media_url=f"/api/media/{rel}",
    )


@router.get("/{storage_key:path}")
def get_media(
    storage_key: str,
    _user: User = Depends(get_current_user),
):
    raw, content_type = media_service.read_media_bytes(storage_key)
    return Response(content=raw, media_type=content_type)
