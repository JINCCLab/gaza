"""Object storage abstraction: local filesystem (default) or S3-compatible (MinIO/AWS)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal, Optional, Tuple

from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger(__name__)

StorageBackendName = Literal["local", "s3"]


def normalize_key(key: str) -> str:
    key = (key or "").lstrip("/").replace("\\", "/")
    if not key or ".." in key.split("/"):
        raise HTTPException(400, "Invalid storage key")
    return key


def resolved_storage_backend() -> StorageBackendName:
    mode = settings.storage_backend
    if mode == "local":
        return "local"
    if mode == "s3":
        return "s3"
    # auto: S3 when bucket + credentials present
    if settings.s3_bucket and settings.s3_access_key_id and settings.s3_secret_access_key:
        return "s3"
    return "local"


def _s3_client():
    import boto3
    from botocore.client import Config

    kwargs = {
        "service_name": "s3",
        "region_name": settings.s3_region,
        "aws_access_key_id": settings.s3_access_key_id,
        "aws_secret_access_key": settings.s3_secret_access_key,
        "config": Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    }
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
    return boto3.client(**kwargs)


def _s3_object_key(logical_key: str, *, kind: Literal["media", "exports"]) -> str:
    """Map logical app keys to bucket object keys with optional prefixes."""
    key = normalize_key(logical_key)
    if kind == "media":
        prefix = (settings.s3_media_prefix or "media/").lstrip("/")
        if not prefix.endswith("/"):
            prefix += "/"
        if key.startswith(prefix):
            return key
        return f"{prefix}{key}"
    prefix = (settings.s3_exports_prefix or "exports/").lstrip("/")
    if not prefix.endswith("/"):
        prefix += "/"
    if key.startswith(prefix):
        return key
    # Accept bare filenames from older local absolute paths
    if key.startswith("exports/"):
        return key
    return f"{prefix}{Path(key).name}"


def _local_media_path(logical_key: str) -> Path:
    key = normalize_key(logical_key)
    root = Path(settings.media_dir).resolve()
    path = (root / key).resolve()
    if not str(path).startswith(str(root)):
        raise HTTPException(400, "Invalid storage key path")
    return path


def _local_export_path(logical_key: str) -> Path:
    """Resolve export key; supports relative exports/… and legacy absolute paths."""
    raw = (logical_key or "").strip()
    if not raw:
        raise HTTPException(400, "Invalid export key")
    p = Path(raw)
    if p.is_absolute():
        return p
    key = normalize_key(raw)
    root = Path(settings.export_dir).resolve()
    # exports/campaign_1_v1.jsonl → export_dir/campaign_1_v1.jsonl
    if key.startswith("exports/"):
        path = (root / key[len("exports/") :]).resolve()
    else:
        path = (root / Path(key).name).resolve()
    if not str(path).startswith(str(root)):
        raise HTTPException(400, "Invalid export key path")
    return path


def put_bytes(
    logical_key: str,
    data: bytes,
    *,
    kind: Literal["media", "exports"],
    content_type: str = "application/octet-stream",
) -> str:
    """
    Persist bytes. Returns the canonical logical key to store in the DB.
    Media: relative key under media/ (e.g. u1/abc.png).
    Exports: exports/<filename>.
    """
    backend = resolved_storage_backend()
    if kind == "media":
        key = normalize_key(logical_key)
        if backend == "s3":
            client = _s3_client()
            obj_key = _s3_object_key(key, kind="media")
            client.put_object(
                Bucket=settings.s3_bucket,
                Key=obj_key,
                Body=data,
                ContentType=content_type,
            )
            return key
        path = _local_media_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    # exports
    key = normalize_key(logical_key)
    if not key.startswith("exports/"):
        key = f"exports/{Path(key).name}"
    if backend == "s3":
        client = _s3_client()
        obj_key = _s3_object_key(key, kind="exports")
        client.put_object(
            Bucket=settings.s3_bucket,
            Key=obj_key,
            Body=data,
            ContentType=content_type,
        )
        return key
    path = _local_export_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return key


def get_bytes(logical_key: str, *, kind: Literal["media", "exports"]) -> bytes:
    backend = resolved_storage_backend()
    if kind == "media":
        key = normalize_key(logical_key)
        if backend == "s3":
            try:
                client = _s3_client()
                obj = client.get_object(Bucket=settings.s3_bucket, Key=_s3_object_key(key, kind="media"))
                return obj["Body"].read()
            except Exception as e:  # noqa: BLE001
                logger.debug("S3 get media failed: %s", e)
                raise HTTPException(404, "Media not found") from e
        path = _local_media_path(key)
        if not path.is_file():
            raise HTTPException(404, "Media not found")
        return path.read_bytes()

    # exports — tolerate legacy absolute paths even when backend is s3 (local leftover)
    raw = (logical_key or "").strip()
    if not raw:
        raise HTTPException(404, "Export file missing")
    abs_candidate = Path(raw)
    if abs_candidate.is_absolute() and abs_candidate.is_file():
        return abs_candidate.read_bytes()

    key = raw if raw.startswith("exports/") or Path(raw).is_absolute() else f"exports/{Path(raw).name}"
    if not Path(key).is_absolute():
        key = normalize_key(key if key.startswith("exports/") else f"exports/{Path(key).name}")

    if backend == "s3":
        try:
            client = _s3_client()
            obj = client.get_object(Bucket=settings.s3_bucket, Key=_s3_object_key(key, kind="exports"))
            return obj["Body"].read()
        except Exception as e:  # noqa: BLE001
            # Fall back to local file if present (mixed deploys)
            local = _local_export_path(key)
            if local.is_file():
                return local.read_bytes()
            logger.debug("S3 get export failed: %s", e)
            raise HTTPException(404, "Export file missing") from e

    path = _local_export_path(key if not abs_candidate.is_absolute() else raw)
    if not path.is_file():
        raise HTTPException(404, "Export file missing")
    return path.read_bytes()


def object_exists(logical_key: str, *, kind: Literal["media", "exports"]) -> bool:
    try:
        if kind == "media":
            key = normalize_key(logical_key)
            if resolved_storage_backend() == "s3":
                client = _s3_client()
                client.head_object(Bucket=settings.s3_bucket, Key=_s3_object_key(key, kind="media"))
                return True
            return _local_media_path(key).is_file()
        raw = (logical_key or "").strip()
        if not raw:
            return False
        p = Path(raw)
        if p.is_absolute():
            return p.is_file()
        key = normalize_key(raw if raw.startswith("exports/") else f"exports/{Path(raw).name}")
        if resolved_storage_backend() == "s3":
            try:
                client = _s3_client()
                client.head_object(Bucket=settings.s3_bucket, Key=_s3_object_key(key, kind="exports"))
                return True
            except Exception:  # noqa: BLE001
                return _local_export_path(key).is_file()
        return _local_export_path(key).is_file()
    except HTTPException:
        return False
    except Exception as e:  # noqa: BLE001
        logger.debug("object_exists failed: %s", e)
        return False


def export_filename(logical_key: str) -> str:
    raw = (logical_key or "").strip()
    if not raw:
        return "export.jsonl"
    return Path(raw).name


def presign_get_url(logical_key: str, *, kind: Literal["media", "exports"]) -> Optional[str]:
    """Return a short-lived GET URL when on S3; None for local (use API proxy)."""
    if resolved_storage_backend() != "s3":
        return None
    try:
        client = _s3_client()
        key = normalize_key(logical_key) if kind == "media" else (
            normalize_key(logical_key)
            if logical_key.startswith("exports/")
            else f"exports/{Path(logical_key).name}"
        )
        if Path(logical_key).is_absolute():
            key = f"exports/{Path(logical_key).name}"
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket, "Key": _s3_object_key(key, kind=kind)},
            ExpiresIn=settings.s3_presign_ttl_seconds,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("presign failed: %s", e)
        return None


def ensure_bucket() -> None:
    """Create bucket if missing (MinIO / fresh AWS). Best-effort; ignore if exists."""
    if resolved_storage_backend() != "s3" or not settings.s3_bucket:
        return
    try:
        client = _s3_client()
        existing = {b["Name"] for b in client.list_buckets().get("Buckets", [])}
        if settings.s3_bucket not in existing:
            params = {"Bucket": settings.s3_bucket}
            # us-east-1 cannot set LocationConstraint on some endpoints
            if settings.s3_region and settings.s3_region != "us-east-1":
                params["CreateBucketConfiguration"] = {"LocationConstraint": settings.s3_region}
            client.create_bucket(**params)
            logger.info("Created S3 bucket %s", settings.s3_bucket)
    except Exception as e:  # noqa: BLE001
        logger.warning("ensure_bucket skipped/failed: %s", e)


def storage_health() -> Tuple[str, str]:
    """Return (backend, status) for /api/health."""
    backend = resolved_storage_backend()
    if backend == "local":
        return "local", "ok"
    try:
        client = _s3_client()
        client.head_bucket(Bucket=settings.s3_bucket)
        return "s3", "ok"
    except Exception as e:  # noqa: BLE001
        logger.debug("S3 health failed: %s", e)
        return "s3", "down"
