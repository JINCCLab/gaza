"""Lightweight SQLite column adds for local/dev (Postgres uses Alembic)."""

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
        if "campaigns" in tables:
            ccols = {c["name"] for c in insp.get_columns("campaigns")}
            if "ontology_id" not in ccols:
                conn.execute(
                    text("ALTER TABLE campaigns ADD COLUMN ontology_id VARCHAR(64)")
                )
            if "schema_version" not in ccols:
                conn.execute(
                    text("ALTER TABLE campaigns ADD COLUMN schema_version VARCHAR(32)")
                )
        if "organizations" in tables:
            ocols = {c["name"] for c in insp.get_columns("organizations")}
            org_adds = [
                ("kyb_legal_name", "ALTER TABLE organizations ADD COLUMN kyb_legal_name VARCHAR(255)"),
                (
                    "kyb_registration_id",
                    "ALTER TABLE organizations ADD COLUMN kyb_registration_id VARCHAR(128)",
                ),
                (
                    "kyb_document_url",
                    "ALTER TABLE organizations ADD COLUMN kyb_document_url VARCHAR(1024)",
                ),
                (
                    "kyb_document_storage_key",
                    "ALTER TABLE organizations ADD COLUMN kyb_document_storage_key VARCHAR(512)",
                ),
                (
                    "kyb_document_filename",
                    "ALTER TABLE organizations ADD COLUMN kyb_document_filename VARCHAR(255)",
                ),
                (
                    "kyb_document_content_type",
                    "ALTER TABLE organizations ADD COLUMN kyb_document_content_type VARCHAR(128)",
                ),
                (
                    "kyb_packet_submitted_at",
                    "ALTER TABLE organizations ADD COLUMN kyb_packet_submitted_at DATETIME",
                ),
            ]
            for col, ddl in org_adds:
                if col not in ocols:
                    conn.execute(text(ddl))
