"""Lightweight SQLite column adds for Phase-0 (no Alembic yet)."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_sqlite_columns(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    with engine.begin() as conn:
        if "allowlist_hosts" in tables:
            cols = {c["name"] for c in insp.get_columns("allowlist_hosts")}
            if "enabled" not in cols:
                conn.execute(
                    text(
                        "ALTER TABLE allowlist_hosts ADD COLUMN enabled BOOLEAN NOT NULL DEFAULT 1"
                    )
                )
        if "users" in tables:
            ucols = {c["name"] for c in insp.get_columns("users")}
            if "auth_subject" not in ucols:
                conn.execute(text("ALTER TABLE users ADD COLUMN auth_subject VARCHAR(255)"))
                conn.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_auth_subject "
                        "ON users (auth_subject)"
                    )
                )
        if "submissions" in tables:
            scols = {c["name"] for c in insp.get_columns("submissions")}
            if "storage_key" not in scols:
                conn.execute(
                    text("ALTER TABLE submissions ADD COLUMN storage_key VARCHAR(512)")
                )
