from typing import Tuple
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models import AllowlistHost


def normalize_host(url_or_host: str) -> str:
    raw = url_or_host.strip().lower()
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    host = parsed.hostname or ""
    if host.startswith("www."):
        return host
    return host


def is_host_allowed(db: Session, source_url: str) -> Tuple[bool, str]:
    host = normalize_host(source_url)
    if not host:
        return False, ""
    hosts = {h.host.lower() for h in db.query(AllowlistHost).all()}
    # Match exact or www./apex variants
    candidates = {host}
    if host.startswith("www."):
        candidates.add(host[4:])
    else:
        candidates.add("www." + host)
    allowed = bool(candidates & hosts)
    return allowed, host
