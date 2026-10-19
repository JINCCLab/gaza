"""CV media storage — local disk or S3-compatible via storage backend."""

from __future__ import annotations

import hashlib
import uuid
from typing import Tuple

from fastapi import HTTPException, UploadFile

from app.config import settings
from app.services import storage as object_storage

ALLOWED_TYPES = {
    t.strip() for t in settings.media_allowed_types.split(",") if t.strip()
}
EXT_BY_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
}


def media_exists(storage_key: str) -> bool:
    return object_storage.object_exists(storage_key, kind="media")


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
    object_storage.put_bytes(rel, raw, kind="media", content_type=content_type)
    return rel, content_type, size, digest


def read_media_bytes(storage_key: str) -> Tuple[bytes, str]:
    raw = object_storage.get_bytes(storage_key, kind="media")
    key = object_storage.normalize_key(storage_key)
    suffix = ("." + key.rsplit(".", 1)[-1].lower()) if "." in key else ""
    ctype = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".mp4": "video/mp4",
    }.get(suffix, "application/octet-stream")
    return raw, ctype


# Back-compat alias used by older call sites
def resolve_storage_key(storage_key: str):
    """Deprecated path helper — prefer media_exists / read_media_bytes."""
    from pathlib import Path

    from app.config import settings as cfg

    key = object_storage.normalize_key(storage_key)
    root = Path(cfg.media_dir).resolve()
    path = (root / key).resolve()
    if not str(path).startswith(str(root)):
        raise HTTPException(400, "Invalid storage_key path")
    return path
