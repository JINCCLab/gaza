"""Apply schema: Alembic on Postgres; create_all (+ SQLite column patches) on SQLite."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import inspect

from app.config import settings
from app.database import Base, engine
from app.schema_migrate import ensure_sqlite_columns

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"


def _alembic_upgrade_to_head() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)

    insp = inspect(engine)
    tables = set(insp.get_table_names())
    # Pre-Alembic Postgres volumes used create_all — stamp instead of re-creating.
    if "alembic_version" not in tables and "users" in tables:
        logger.info("Existing schema without alembic_version — stamping head")
        command.stamp(cfg, "head")
        return

    logger.info("Running alembic upgrade head")
    command.upgrade(cfg, "head")


def apply_schema() -> None:
    """
    SQLite (local/dev): Base.metadata.create_all + ensure_sqlite_columns.
    Postgres (and other): alembic upgrade head (see alembic/versions/).
    """
    if settings.database_url.startswith("sqlite") or engine.dialect.name == "sqlite":
        Base.metadata.create_all(bind=engine)
        ensure_sqlite_columns(engine)
        logger.info("SQLite schema via create_all")
        return
    _alembic_upgrade_to_head()
