#!/bin/sh
# Compose / container entrypoint: apply schema then exec the main process.
# Postgres → alembic upgrade head; SQLite → create_all (see app.db_migrate).
set -e
cd /repo/backend
python -c "from app.db_migrate import apply_schema; apply_schema()"
exec "$@"
