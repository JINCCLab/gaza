"""JWT verification for Clerk (JWKS) and local dev HS256 sessions."""

from __future__ import annotations

import time
from functools import lru_cache
from typing import Any, Dict, Optional

import httpx
import jwt
from fastapi import HTTPException
from jwt import PyJWKClient

from app.config import settings


class TokenClaims:
    __slots__ = ("subject", "email", "role", "display_name", "raw")

    def __init__(
        self,
        subject: str,
        email: Optional[str],
        role: Optional[str],
        display_name: Optional[str],
        raw: Dict[str, Any],
    ) -> None:
        self.subject = subject
        self.email = email
        self.role = role
        self.display_name = display_name
        self.raw = raw


@lru_cache(maxsize=1)
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url, cache_keys=True, lifespan=3600)


def issue_dev_token(
    *,
    subject: str,
    email: str,
    role: str,
    display_name: str,
) -> str:
    now = int(time.time())
    payload = {
        "sub": subject,
        "email": email,
        "role": role,
        "name": display_name,
        "iss": "data_platform-dev",
        "aud": "data_platform",
        "iat": now,
        "exp": now + settings.dev_jwt_ttl_seconds,
    }
    return jwt.encode(payload, settings.dev_jwt_secret, algorithm="HS256")


def verify_dev_token(token: str) -> TokenClaims:
    try:
        payload = jwt.decode(
            token,
            settings.dev_jwt_secret,
            algorithms=["HS256"],
            audience="data_platform",
            issuer="data_platform-dev",
        )
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid dev session token: {e}") from e
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Token missing sub")
    return TokenClaims(
        subject=str(sub),
        email=payload.get("email"),
        role=payload.get("role"),
        display_name=payload.get("name"),
        raw=payload,
    )


def verify_clerk_token(token: str) -> TokenClaims:
    jwks_url = settings.clerk_jwks_endpoint()
    if not jwks_url:
        raise HTTPException(
            status_code=503,
            detail="Clerk JWKS not configured (set CLERK_ISSUER or CLERK_JWKS_URL)",
        )
    try:
        client = _jwks_client(jwks_url)
        signing_key = client.get_signing_key_from_jwt(token)
        decode_kwargs: Dict[str, Any] = {
            "algorithms": ["RS256"],
            "options": {"verify_aud": False},
        }
        if settings.clerk_issuer:
            decode_kwargs["issuer"] = settings.clerk_issuer.rstrip("/")
        payload = jwt.decode(token, signing_key.key, **decode_kwargs)
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid Clerk token: {e}") from e
    except (httpx.HTTPError, Exception) as e:
        # PyJWKClient may raise generic errors on network/JWKS failures
        raise HTTPException(status_code=401, detail=f"Clerk JWKS verification failed: {e}") from e

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Clerk token missing sub")

    # Clerk session JWTs expose email variously; publicMetadata.role for app roles.
    email = payload.get("email") or payload.get("primary_email_address")
    meta = payload.get("public_metadata") or payload.get("metadata") or {}
    if not isinstance(meta, dict):
        meta = {}
    role = meta.get("role") or payload.get("role")
    name = payload.get("name") or payload.get("full_name")

    # Default session JWT often omits email — enrich via Clerk Backend API.
    if not email or not role:
        from app.clerk_users import enrich_from_clerk_api

        api_email, api_role, api_name = enrich_from_clerk_api(str(sub))
        email = email or api_email
        role = role or api_role
        name = name or api_name

    return TokenClaims(
        subject=str(sub),
        email=email,
        role=role if isinstance(role, str) else None,
        display_name=name if isinstance(name, str) else None,
        raw=payload,
    )


def verify_access_token(token: str) -> TokenClaims:
    mode = settings.resolved_auth_mode()
    if mode == "clerk":
        return verify_clerk_token(token)
    return verify_dev_token(token)
