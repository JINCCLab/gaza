# FastAPI API / worker — run from repo root via docker compose (build context: ./backend).
# config.py resolves ROOT as parents[2] → /repo when this file lives at /repo/backend/app/config.py
FROM python:3.12-slim

WORKDIR /repo/backend

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts
COPY alembic.ini .
COPY alembic ./alembic

RUN mkdir -p /repo/data/media /repo/exports \
    && chmod +x /repo/backend/scripts/entrypoint.sh

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/repo/backend

EXPOSE 8000

# Entrypoint runs alembic upgrade head (Postgres) or create_all (SQLite) before CMD.
ENTRYPOINT ["/repo/backend/scripts/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
