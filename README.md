# data_platform — Phase-0 OSINT vertical slice

Minimal end-to-end loop:

**Sign in → KYB Org → OSINT or CV campaign draft → Admin approve → Contributor EN submission (labels or media+annotation) → auto verify stub + manual accept → CreditLedger → Dataset JSONL export**

Stack: **Next.js** (frontend) + **FastAPI** (API) + **SQLite** by default (Postgres via `DATABASE_URL` / Compose) + optional **Redis verify worker** + optional **S3/MinIO** object storage + **Clerk** IdP (local Bearer JWT fallback when keys missing).

**Requires Python 3.9+** (uses `Optional`/`List` typing for FastAPI runtime annotations; no PEP 604 `X | Y`).

## Quick start (no Clerk keys)

```bash
# API (Python 3.9+)
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# UI (other terminal)
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 npm run dev
```

Open http://localhost:3000/sign-in — pick a seeded persona (issues a **Bearer JWT** session). The old **Act as** / `X-User-Id` header is retired.

Smoke test (API must be up; uses `/api/auth/dev-login`):

```bash
cd backend && source .venv/bin/activate
python scripts/smoke_e2e.py
```

## Docker Compose (Postgres + Redis + API + worker)

SQLite remains the zero-config local default (`VERIFY_MODE=auto` → **sync** without Redis). For a Postgres + Redis worker stack:

```bash
docker compose up --build db redis api worker
# optional UI: docker compose --profile ui up --build
# optional MinIO (S3-compatible media + exports):
docker compose -f docker-compose.yml -f docker-compose.s3.yml --profile s3 up --build
```

- API: http://127.0.0.1:8000 (`DATABASE_URL` → `db`, `REDIS_URL` → `redis`, `VERIFY_MODE=async`)
- Worker: `python -m app.worker` (same image; shared `api_data` volume for local CV media)
- Storage: local volumes by default; with s3 profile → MinIO bucket `dataplat` (`STORAGE_BACKEND=s3`)
- Postgres: `localhost:5432` — user/pass/db `dataplat` / `dataplat` / `data_platform`
- Redis: `localhost:6379`
- MinIO: API `9000`, console `9001` (profile s3)
- Schema: `create_all` on API startup (no Alembic yet; wipe the `pgdata` volume to reset)

Local smoke without Redis (forces inline verify):

```bash
cd backend && source .venv/bin/activate
VERIFY_MODE=sync uvicorn app.main:app --reload --port 8000
# other terminal:
python scripts/smoke_e2e.py
```

Smoke against Compose API + worker (script polls `in_review`):

```bash
cd backend && source .venv/bin/activate
pip install -r requirements.txt   # needs httpx for the script
python scripts/smoke_e2e.py http://127.0.0.1:8000
```

Host-run API against Compose Postgres only (sync verify):

```bash
docker compose up -d db
cd backend && source .venv/bin/activate
export DATABASE_URL=postgresql+psycopg://dataplat:dataplat@127.0.0.1:5432/data_platform
export VERIFY_MODE=sync
uvicorn app.main:app --reload --port 8000
```

## With Clerk keys

1. Copy [`.env.example`](./.env.example) into `backend/.env` and `frontend/.env.local`.
2. Set `CLERK_SECRET_KEY`, `CLERK_ISSUER` (or `CLERK_JWKS_URL`), and `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`.
3. In Clerk Dashboard, set each user’s `publicMetadata.role` to `admin` | `buyer` | `contributor`.
4. Restart API + UI → `/sign-in` shows the Clerk widget.

See [docs/auth-clerk.md](./docs/auth-clerk.md) for why Clerk over Supabase Auth, roles via `publicMetadata.role`, and **production** Netlify + FastAPI env vars / redirect URLs. Frontend deploy uses [`frontend/netlify.toml`](./frontend/netlify.toml) (set Netlify UI Base directory = `frontend`).

Full click-path: [docs/mvp-slice-runbook.md](./docs/mvp-slice-runbook.md).

## Stubbed vs real

| Real in this slice | Stubbed / deferred |
|--------------------|--------------------|
| Clerk JWT + local Bearer session fallback | Production Clerk org sync / webhooks polish |
| Dual templates `osint_label` + `cv_media` (local or S3 media) | ML deepfake / perceptual hash |
| Domain models + SQLite default / Postgres via `DATABASE_URL` + Compose | Alembic migrations (create_all for now) |
| KYB status flag approve/reject | Full KYB document workflow |
| Campaign draft → pending_review → active | Pause/close settlement polish |
| OSINT + CV submit (URL/labels or upload+annotation) | Perceptual hash / commercial deepfake stack |
| Allowlist v0 (~30 EN public hosts) + Admin disable | Per-campaign allowlist subset; further founder expand |
| Verification stages 1–7 (heuristic) + Redis worker / sync fallback | Deepfake ML, perceptual hash |
| Manual accept/reject queue | Validator marketplace |
| CreditLedger reward + redeem_reserve | On-chain token / TGE |
| Dataset JSONL export (local or S3; proxy + optional presign) | CDN / lifecycle policies polish |

## Layout

```
backend/          FastAPI app
frontend/         Next.js App Router UI
docs/             Runbook + auth notes
.env.example      Clerk + DATABASE_URL template
docker-compose.yml     Postgres + Redis + API + worker (+ optional UI / MinIO profiles)
docker-compose.s3.yml  MinIO overlay (STORAGE_BACKEND=s3 on api/worker)
backend/Dockerfile     API / worker image (`python -m app.worker`)
frontend/Dockerfile    UI image (`--profile ui`)
data/                  SQLite DB + media (gitignored; unused when S3)
exports/               Generated JSONL (gitignored; unused when S3)
```
