from typing import Optional, Set, Tuple
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models import AllowlistHost


def normalize_host(url_or_host: str) -> str:
    raw = url_or_host.strip().lower()
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    return parsed.hostname or ""


def apex_and_www(host: str) -> Set[str]:
    host = host.lower().strip()
    if not host:
        return set()
    if host.startswith("www."):
        return {host, host[4:]}
    return {host, "www." + host}


def is_host_allowed(db: Session, source_url: str) -> Tuple[bool, str, Optional[str]]:
    """
    Returns (allowed, host, failure_code).
    Only enabled allowlist rows count. www./apex variants match.
    """
    host = normalize_host(source_url)
    if not host:
        return False, "", "invalid_host"
    allowed_hosts: Set[str] = set()
    for row in db.query(AllowlistHost).filter(AllowlistHost.enabled.is_(True)).all():
        allowed_hosts |= apex_and_www(row.host)
    if apex_and_www(host) & allowed_hosts:
        return True, host, None
    return False, host, "host_not_allowlisted"
