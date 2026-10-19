from typing import Optional, Set, Tuple
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models import AllowlistHost
from app.services.url_quality import validate_url_shape


def normalize_host(url_or_host: str) -> str:
    raw = url_or_host.strip().lower()
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    host = (parsed.hostname or "").rstrip(".")
    return host


def apex_and_www(host: str) -> Set[str]:
    host = host.lower().strip().rstrip(".")
    if not host:
        return set()
    if host.startswith("www."):
        return {host, host[4:]}
    return {host, "www." + host}


def is_host_allowed(db: Session, source_url: str) -> Tuple[bool, str, Optional[str]]:
    """
    Returns (allowed, host, failure_code).
    Shape checks first (scheme/https, no IP literal, no userinfo), then enabled allowlist.
    www./apex variants match.
    """
    ok, shape_code, _msg = validate_url_shape(source_url)
    if not ok:
        host = normalize_host(source_url) if source_url else ""
        return False, host, shape_code or "invalid_host"

    host = normalize_host(source_url)
    if not host:
        return False, "", "invalid_host"
    allowed_hosts: Set[str] = set()
    for row in db.query(AllowlistHost).filter(AllowlistHost.enabled.is_(True)).all():
        allowed_hosts |= apex_and_www(row.host)
    if apex_and_www(host) & allowed_hosts:
        return True, host, None
    return False, host, "host_not_allowlisted"
