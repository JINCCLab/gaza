"""Lightweight SQLite column adds for Phase-0 (no Alembic yet)."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_sqlite_columns(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    if "allowlist_hosts" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("allowlist_hosts")}
    with engine.begin() as conn:
        if "enabled" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE allowlist_hosts ADD COLUMN enabled BOOLEAN NOT NULL DEFAULT 1"
                )
            )
