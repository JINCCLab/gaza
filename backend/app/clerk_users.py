"""Optional Clerk Backend API lookup when session JWT omits email / publicMetadata."""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from app.config import settings


def fetch_clerk_user(user_id: str) -> Optional[Dict[str, Any]]:
    if not settings.clerk_secret_key:
        return None
    url = f"https://api.clerk.com/v1/users/{user_id}"
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(
                url,
                headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
            )
            if r.status_code != 200:
                return None
            return r.json()
    except httpx.HTTPError:
        return None


def enrich_from_clerk_api(subject: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (email, role, display_name) from Clerk Backend API."""
    data = fetch_clerk_user(subject)
    if not data:
        return None, None, None
    email = None
    addrs = data.get("email_addresses") or []
    primary_id = data.get("primary_email_address_id")
    for a in addrs:
        if a.get("id") == primary_id:
            email = a.get("email_address")
            break
    if not email and addrs:
        email = addrs[0].get("email_address")
    meta = data.get("public_metadata") or {}
    role = meta.get("role") if isinstance(meta, dict) else None
    first = data.get("first_name") or ""
    last = data.get("last_name") or ""
    name = f"{first} {last}".strip() or data.get("username")
    return email, role if isinstance(role, str) else None, name if name else None
