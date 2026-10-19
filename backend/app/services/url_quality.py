"""URL normalization, shape checks, and lightweight reachability (no page scrape)."""

from __future__ import annotations

import ipaddress
import logging
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

logger = logging.getLogger(__name__)

# Tracking params stripped for duplicate hashing (keep meaningful path/query).
_STRIP_QUERY_KEYS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
    }
)


def validate_url_shape(url: str) -> Tuple[bool, Optional[str], str]:
    """
    Stronger allowlist-adjacent checks before host match.
    Returns (ok, failure_code, message).
    """
    raw = (url or "").strip()
    if not raw:
        return False, "empty_url", "Source URL is required."
    if len(raw) > 2000:
        return False, "url_too_long", "Source URL exceeds 2000 characters."
    if "://" not in raw:
        return False, "missing_scheme", "URL must include https:// (http/https only)."
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        return False, "bad_scheme", "Only http/https URLs are allowed for Phase-0 OSINT."
    if parsed.username or parsed.password:
        return False, "url_userinfo", "URLs must not include username/password."
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        return False, "invalid_host", "Could not parse a hostname from the URL."
    # Block raw IPs — Stage-0 wants named public EN hosts on the allowlist.
    try:
        ipaddress.ip_address(host)
        return False, "ip_literal", "IP-literal hosts are not allowed; use an allowlisted domain."
    except ValueError:
        pass
    if "." not in host and host != "localhost":
        return False, "invalid_host", f"Hostname '{host}' looks invalid."
    return True, None, ""


def normalize_url_for_hash(url: str) -> str:
    """Canonical form for duplicate detection (scheme/host lower, no fragment, strip trackers)."""
    raw = (url or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "https").lower()
    host = (parsed.hostname or "").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    # Filter tracking query params; keep stable order
    q = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in _STRIP_QUERY_KEYS
    ]
    q.sort(key=lambda kv: (kv[0], kv[1]))
    query = urlencode(q, doseq=True)
    # Drop fragment; drop default ports
    netloc = host
    if parsed.port and not (
        (scheme == "https" and parsed.port == 443) or (scheme == "http" and parsed.port == 80)
    ):
        netloc = f"{host}:{parsed.port}"
    return urlunparse((scheme, netloc, path, "", query, ""))


def check_url_reachability(
    url: str,
    *,
    timeout_s: float = 2.0,
    enabled: bool = True,
) -> Dict[str, Any]:
    """
    Lightweight connectivity stub: HEAD (fallback GET) with short timeout.
    Does not download or parse page bodies aggressively.
    Reachable = TCP/HTTP response received (including 4xx). Unreachable = DNS/timeout/conn error.
    """
    result: Dict[str, Any] = {
        "checked": False,
        "reachable": None,
        "status_code": None,
        "error": None,
        "method": None,
    }
    if not enabled:
        result["skipped"] = True
        return result
    ok_shape, code, _ = validate_url_shape(url)
    if not ok_shape:
        result["checked"] = True
        result["reachable"] = False
        result["error"] = code
        return result

    result["checked"] = True
    try:
        import httpx

        with httpx.Client(
            timeout=timeout_s,
            follow_redirects=True,
            max_redirects=3,
            # Don't send a heavy browser UA; this is a health probe only.
            headers={"User-Agent": "data_platform-phase0-urlcheck/0.1"},
        ) as client:
            try:
                resp = client.head(url)
                # Some hosts reject HEAD — fall back to GET with no body read beyond headers
                if resp.status_code in (405, 501):
                    resp = client.get(url)
                    result["method"] = "GET"
                else:
                    result["method"] = "HEAD"
            except httpx.HTTPError:
                resp = client.get(url)
                result["method"] = "GET"
            result["status_code"] = resp.status_code
            result["reachable"] = True
            return result
    except Exception as e:  # noqa: BLE001 — network stub must never crash verify
        # DNS / timeout / connection
        err_name = type(e).__name__
        result["reachable"] = False
        result["error"] = err_name
        logger.debug("URL reachability failed for %s: %s", url, e)
        return result


def contributor_reject_message(reason: str, detail: Optional[Dict[str, Any]] = None) -> str:
    """Clear EN copy for contributor UI (codes stay machine-stable)."""
    detail = detail or {}
    catalog = {
        "technical_invalid": "Submission failed a technical check (URL/media missing or invalid).",
        "schema_policy": (
            "Labels do not match the campaign ontology "
            "(required fields or enum values). Check event_type / equipment_type / category."
        ),
        "allowlist_reject": (
            detail.get("message")
            or "Source host is not on the Phase-0 allowlist (or is disabled). "
            "Use a public EN news/official host."
        ),
        "url_shape_reject": detail.get("message")
        or "URL shape is invalid (https only, no IP literals, no credentials).",
        "url_unreachable": (
            "Could not reach the source URL (DNS/timeout/connection). "
            "Confirm the link is publicly reachable, then resubmit."
        ),
        "duplicate": "Duplicate of an existing submission for this campaign (normalized URL + labels).",
        "synthetic_not_allowed": (
            "This campaign disallows synthetic media (synthetic_allowed=false)."
        ),
        "provenance": "Provenance check failed (license claim or source policy).",
        "manual_reject": "Rejected by Admin review.",
    }
    if reason in catalog:
        return catalog[reason]
    # Ontology error codes nested under schema
    if reason.endswith("_not_in_enum") or reason.startswith("missing_"):
        return catalog["schema_policy"]
    return f"Rejected ({reason})."
