"""Local media storage for Phase-0 CV uploads (S3 later)."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Tuple

from fastapi import HTTPException, UploadFile

from app.config import settings

ALLOWED_TYPES = {
    t.strip() for t in settings.media_allowed_types.split(",") if t.strip()
}
EXT_BY_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
}


def media_root() -> Path:
    root = Path(settings.media_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_storage_key(storage_key: str) -> Path:
    """Resolve a relative storage_key under media_dir; reject path traversal."""
    key = (storage_key or "").lstrip("/").replace("\\", "/")
    if not key or ".." in key.split("/"):
        raise HTTPException(400, "Invalid storage_key")
    path = (media_root() / key).resolve()
    root = media_root().resolve()
    if not str(path).startswith(str(root)):
        raise HTTPException(400, "Invalid storage_key path")
    return path


async def save_upload(file: UploadFile, *, contributor_id: int) -> Tuple[str, str, int, str]:
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            400,
            f"Unsupported content_type={content_type}. Allowed: {sorted(ALLOWED_TYPES)}",
        )
    raw = await file.read()
    size = len(raw)
    if size == 0:
        raise HTTPException(400, "Empty file")
    if size > settings.media_max_bytes:
        raise HTTPException(
            400,
            f"File too large ({size} bytes); max {settings.media_max_bytes}",
        )
    digest = hashlib.sha256(raw).hexdigest()
    ext = EXT_BY_TYPE.get(content_type, ".bin")
    rel = f"u{contributor_id}/{uuid.uuid4().hex}{ext}"
    dest = resolve_storage_key(rel)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)
    return rel, content_type, size, digest


def read_media_bytes(storage_key: str) -> Tuple[bytes, str]:
    path = resolve_storage_key(storage_key)
    if not path.is_file():
        raise HTTPException(404, "Media not found")
    suffix = path.suffix.lower()
    ctype = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".mp4": "video/mp4",
    }.get(suffix, "application/octet-stream")
    return path.read_bytes(), ctype
