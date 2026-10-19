"""Organizations + Phase-0 KYB document stub (no vendor ID verification)."""

from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_role
from app.models import AuditLog, Organization, User, utcnow
from app.schemas import (
    KybDecision,
    KybDocumentUploadOut,
    KybPacketSubmit,
    OrgCreate,
    OrgOut,
)
from app.services import storage as object_storage

router = APIRouter(prefix="/api/orgs", tags=["orgs"])

# Lightweight KYB stubs: PDF / images / plain text (not a verification vendor)
_KYB_ALLOWED_TYPES = frozenset(
    {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
        "text/plain",
    }
)
_KYB_EXT = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "text/plain": ".txt",
}
_KYB_MAX_BYTES = 5 * 1024 * 1024  # 5 MiB stub cap


def _packet_ready(org: Organization) -> bool:
    has_meta = bool((org.kyb_legal_name or "").strip() and (org.kyb_registration_id or "").strip())
    has_doc = bool(
        (org.kyb_document_url or "").strip() or (org.kyb_document_storage_key or "").strip()
    )
    return has_meta and has_doc


def org_to_out(org: Organization) -> OrgOut:
    return OrgOut(
        id=org.id,
        name=org.name,
        owner_user_id=org.owner_user_id,
        kyb_status=org.kyb_status,
        intended_use=org.intended_use,
        kyb_notes=org.kyb_notes,
        kyb_legal_name=org.kyb_legal_name,
        kyb_registration_id=org.kyb_registration_id,
        kyb_document_url=org.kyb_document_url,
        kyb_document_storage_key=org.kyb_document_storage_key,
        kyb_document_filename=org.kyb_document_filename,
        kyb_document_content_type=org.kyb_document_content_type,
        kyb_packet_submitted_at=org.kyb_packet_submitted_at,
        kyb_packet_ready=_packet_ready(org),
        status=org.status,
        created_at=org.created_at,
    )


def _require_org_member_or_admin(user: User, org: Organization) -> None:
    if user.role == "admin":
        return
    if user.org_id != org.id:
        raise HTTPException(403, "Forbidden")


@router.post("", response_model=OrgOut)
def create_org(
    body: OrgCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("buyer")),
):
    if user.org_id:
        raise HTTPException(400, "Buyer already belongs to an org")
    org = Organization(
        name=body.name,
        owner_user_id=user.id,
        kyb_status="pending",
        intended_use=body.intended_use,
    )
    db.add(org)
    db.flush()
    user.org_id = org.id
    db.add(
        AuditLog(
            actor_id=user.id,
            action="org_create",
            entity_type="organization",
            entity_id=org.id,
            detail_json={"name": org.name},
        )
    )
    db.commit()
    db.refresh(org)
    return org_to_out(org)


@router.get("/{org_id}", response_model=OrgOut)
def get_org(org_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Org not found")
    _require_org_member_or_admin(user, org)
    return org_to_out(org)


@router.post("/{org_id}/kyb/upload", response_model=KybDocumentUploadOut)
async def upload_kyb_document(
    org_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("buyer")),
):
    """Store a lightweight KYB stub file (PDF/image/txt). No ID-vendor check."""
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Org not found")
    if user.org_id != org.id:
        raise HTTPException(403, "Forbidden")
    if org.kyb_status == "approved":
        raise HTTPException(400, "KYB already approved; packet is locked")

    content_type = (file.content_type or "").split(";")[0].strip().lower() or "application/octet-stream"
    if content_type not in _KYB_ALLOWED_TYPES:
        raise HTTPException(
            400,
            f"Unsupported KYB content_type={content_type}. Allowed: {sorted(_KYB_ALLOWED_TYPES)}",
        )
    raw = await file.read()
    size = len(raw)
    if size == 0:
        raise HTTPException(400, "Empty file")
    if size > _KYB_MAX_BYTES:
        raise HTTPException(400, f"File too large ({size} bytes); max {_KYB_MAX_BYTES}")

    digest = hashlib.sha256(raw).hexdigest()
    ext = _KYB_EXT.get(content_type, ".bin")
    filename = (file.filename or f"kyb{ext}").strip() or f"kyb{ext}"
    # Sanitize filename for display only; storage key is uuid-based
    safe_name = filename.replace("/", "_").replace("\\", "_")[:200]
    rel = f"kyb/org{org.id}/{uuid.uuid4().hex}{ext}"
    object_storage.put_bytes(rel, raw, kind="media", content_type=content_type)

    db.add(
        AuditLog(
            actor_id=user.id,
            action="kyb_document_upload",
            entity_type="organization",
            entity_id=org.id,
            detail_json={
                "storage_key": rel,
                "filename": safe_name,
                "content_type": content_type,
                "size_bytes": size,
                "sha256": digest,
            },
        )
    )
    db.commit()
    return KybDocumentUploadOut(
        storage_key=rel,
        filename=safe_name,
        content_type=content_type,
        size_bytes=size,
        sha256=digest,
    )


@router.post("/{org_id}/kyb/packet", response_model=OrgOut)
def submit_kyb_packet(
    org_id: int,
    body: KybPacketSubmit,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("buyer")),
):
    """Submit / update KYB stub packet: legal name, registration id, URL and/or uploaded key."""
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Org not found")
    if user.org_id != org.id:
        raise HTTPException(403, "Forbidden")
    if org.kyb_status == "approved":
        raise HTTPException(400, "KYB already approved; packet is locked")

    legal = (body.legal_name or "").strip()
    reg = (body.registration_id or "").strip()
    if not legal or not reg:
        raise HTTPException(400, "legal_name and registration_id are required")

    doc_url = (body.document_url or "").strip() or None
    storage_key = (body.storage_key or "").strip() or None
    if storage_key:
        storage_key = object_storage.normalize_key(storage_key)
        if not storage_key.startswith(f"kyb/org{org.id}/"):
            raise HTTPException(400, "storage_key must be from this org's KYB upload")
        if not object_storage.object_exists(storage_key, kind="media"):
            raise HTTPException(400, "storage_key not found — upload first")

    if not doc_url and not storage_key:
        raise HTTPException(
            400,
            "Provide document_url and/or storage_key (upload via POST .../kyb/upload)",
        )

    org.kyb_legal_name = legal
    org.kyb_registration_id = reg
    org.kyb_document_url = doc_url
    if storage_key:
        org.kyb_document_storage_key = storage_key
        if body.filename:
            org.kyb_document_filename = body.filename.strip()[:255]
        if body.content_type:
            org.kyb_document_content_type = body.content_type.strip()[:128]
    elif body.filename and not org.kyb_document_storage_key:
        org.kyb_document_filename = body.filename.strip()[:255]
    org.kyb_packet_submitted_at = utcnow()
    # Re-submit after reject → back to pending
    if org.kyb_status == "rejected":
        org.kyb_status = "pending"

    db.add(
        AuditLog(
            actor_id=user.id,
            action="kyb_packet_submit",
            entity_type="organization",
            entity_id=org.id,
            detail_json={
                "legal_name": legal,
                "registration_id": reg,
                "document_url": doc_url,
                "storage_key": org.kyb_document_storage_key,
                "packet_ready": _packet_ready(org),
            },
        )
    )
    db.commit()
    db.refresh(org)
    return org_to_out(org)


@router.get("/{org_id}/kyb/document")
def download_kyb_document(
    org_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Download uploaded KYB stub file (admin or org member). URL-only packets have no binary."""
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Org not found")
    _require_org_member_or_admin(user, org)
    key = org.kyb_document_storage_key
    if not key:
        raise HTTPException(404, "No uploaded KYB document (URL-only stub or not submitted)")
    raw = object_storage.get_bytes(key, kind="media")
    ctype = org.kyb_document_content_type or "application/octet-stream"
    filename = org.kyb_document_filename or "kyb-document"
    return Response(
        content=raw,
        media_type=ctype,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{org_id}/kyb", response_model=OrgOut)
def decide_kyb(
    org_id: int,
    body: KybDecision,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin")),
):
    """Admin approve/reject KYB. Optional KO memo in notes. Flag flow unchanged."""
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(404, "Org not found")
    org.kyb_status = "approved" if body.approve else "rejected"
    org.kyb_notes = body.notes
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="kyb_decision",
            entity_type="organization",
            entity_id=org.id,
            detail_json={
                "kyb_status": org.kyb_status,
                "notes": body.notes,
                "packet_ready": _packet_ready(org),
                "legal_name": org.kyb_legal_name,
                "registration_id": org.kyb_registration_id,
            },
        )
    )
    db.commit()
    db.refresh(org)
    return org_to_out(org)
