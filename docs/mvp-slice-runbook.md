# MVP slice runbook — Phase-0 dual wedge (OSINT + CV)

How to run the coding slice and walk OSINT and CV happy paths (same platform).

## Prerequisites

- Python **3.9+** (backend uses `Optional`/`List`/`Dict` — FastAPI-safe on 3.9; no PEP 604 `X | Y`)
- Node 20+
- Repo branch with `backend/` + `frontend/`
- Optional: Docker + Compose (Postgres + Redis + API + verify worker; MinIO via `--profile s3`)
- Optional: Clerk application keys (see [auth-clerk.md](./auth-clerk.md); production checklist in project store `docs/clerk-deploy-setup.md`)

## Object storage (local vs S3)

| Mode | Env | Behavior |
|------|-----|----------|
| **local** (default) | unset / `STORAGE_BACKEND=local` | CV media → `data/media/`; exports → `exports/` |
| **s3** | `STORAGE_BACKEND=s3` (or `auto` + `S3_BUCKET` + keys) | Same logical keys in bucket (`media/…`, `exports/…`) via boto3 |
| **MinIO (Compose)** | `docker compose -f docker-compose.yml -f docker-compose.s3.yml --profile s3 up --build` | API/worker get `S3_ENDPOINT_URL=http://minio:9000`, bucket `dataplat` |

Download: `GET /api/datasets/{id}/download` always **proxies** bytes (auth-gated). With S3, response JSON also includes `presigned_url`; pass `?redirect=1` to 302 to the presigned GET. Health: `storage_backend`, `storage`.

## Database

| Mode | How | Schema |
|------|-----|--------|
| **SQLite (default)** | Leave `DATABASE_URL` unset → `./data/data_platform.db` | `Base.metadata.create_all` + `ensure_sqlite_columns` (Alembic skipped) |
| **Postgres (Compose)** | `docker compose up --build db redis api worker` | Container **entrypoint** + API startup: `alembic upgrade head` (`backend/alembic/versions/`) |
| **Postgres (host API)** | `docker compose up -d db` then `DATABASE_URL=postgresql+psycopg://dataplat:dataplat@127.0.0.1:5432/data_platform` | Same — `apply_schema()` / `alembic upgrade head` on boot |

Driver: `psycopg` v3 (`postgresql+psycopg://…` in SQLAlchemy). Credentials match `docker-compose.yml`.

Manual migrate (host):

```bash
cd backend && source .venv/bin/activate
export DATABASE_URL=postgresql+psycopg://dataplat:dataplat@127.0.0.1:5432/data_platform
alembic upgrade head
# new revision after model changes:
# alembic revision --autogenerate -m "describe_change"
```

Pre-Alembic Postgres volumes (schema from old `create_all`) are **stamped** to head on first boot so existing data is kept. Wipe with `docker compose down -v` for a clean migrate.

## Verification (sync vs Redis worker)

| Mode | Env | Behavior |
|------|-----|----------|
| **sync** | `VERIFY_MODE=sync` (or no Redis) | `POST /api/submissions` runs `run_automated_stages` on the request thread → `needs_review` / `rejected` |
| **async** | `VERIFY_MODE=async` + `REDIS_URL` + worker | Create returns `in_review`; worker BRPOPs `verify:jobs` and runs the same pipeline |
| **auto** (default) | `VERIFY_MODE=auto` | Async when `REDIS_URL` is reachable; otherwise sync |

If Redis is down while `VERIFY_MODE=async|auto`, the API **sync-fallbacks** (same pipeline inline). Health exposes `verify_mode`, `verify_path`, `redis`.

Worker (host):

```bash
cd backend && source .venv/bin/activate
export REDIS_URL=redis://127.0.0.1:6379/0
export VERIFY_MODE=async   # on the API process
python -m app.worker
```

## Start services

### Option A — local SQLite (no Docker, sync verify)

**Terminal A — API**

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# optional: cp ../.env.example .env  # fill Clerk keys for production IdP
# default VERIFY_MODE=auto with no REDIS_URL → sync inline
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal B — UI**

```bash
cd frontend
npm install
# optional: frontend/.env.local with NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY + NEXT_PUBLIC_API_URL
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 npm run dev
```

### Option B — Docker Compose (Postgres + Redis + API + worker)

```bash
docker compose up --build db redis api worker
# optional Next.js UI: docker compose --profile ui up --build
# optional MinIO object storage:
# docker compose -f docker-compose.yml -f docker-compose.s3.yml --profile s3 up --build
```

- UI: http://localhost:3000  
- Sign-in: http://localhost:3000/sign-in  
- API docs: http://127.0.0.1:8000/docs  
- Health: `GET /api/health` (`verify_path=async`, `redis=ok`, `storage_backend=local|s3`)  
- Auth config: `GET /api/auth/config`  
- MinIO console (profile s3): http://127.0.0.1:9001 (`minioadmin` / `minioadmin`)

## Auth (Clerk or local session)

**IdP choice: Clerk** — see [auth-clerk.md](./auth-clerk.md).

| Mode | When | How to sign in |
|------|------|----------------|
| **Clerk** | `CLERK_SECRET_KEY` + issuer/JWKS set | UI Clerk widget; API verifies Bearer session JWT |
| **Dev** (default without keys) | Keys missing / `AUTH_MODE=dev` | `/sign-in` persona → `POST /api/auth/dev-login` → Bearer JWT in `localStorage` |

Roles: **admin** / **buyer** / **contributor**. APIs require `Authorization: Bearer <token>` (`X-User-Id` retired).

| Role | Email | Notes |
|------|-------|--------|
| admin | admin@demo.local | Founder ops (KO UI) |
| buyer | buyer@demo.local | Org KYB starts `pending` |
| contributor | contributor@demo.local | EN submit UI (OSINT + CV) |

## Campaign templates (dual wedge)

| `data_type` | `data_class` | Contributor payload | Notes |
|-------------|--------------|---------------------|--------|
| `osint_label` | `structured_osint` | allowlisted source URL + event/location/time/equipment labels | Pins ontology `osint_label@0.1.0` by default — [osint-ontology-v0.md](./osint-ontology-v0.md) |
| `cv_media` | `public_scene_cv` | media **upload** and/or allowlisted URL + annotation `{category, caption, bboxes[]}` | Pins `cv_media@0.1.0`; `synthetic_allowed=false` by default |

Ontology API: `GET /api/ontology`, `GET /api/ontology/{id}?version=…`. UI: `/admin/ontology`.

CV category whitelist (defaults): `parade_public`, `museum_exhibit`, `official_promo`, `public_airshow`, `open_training_viewing`.

## Click path — OSINT

1. `/sign-in` → **buyer** → KYB stub packet (legal name + registration id + URL and/or file upload).
2. **admin** → Org KYB 문서 확인 → 승인 (KO 메모 가능). (ops metrics: `/admin/analytics`)
3. **buyer** → template `osint_label` → Create & submit for review.
4. **admin** → 캠페인 사전승인 → 승인/게시.
5. **contributor** → Reuters (allowlisted) URL + labels → Submit → (`in_review` if async) → `needs_review`.
6. **admin** → 수락 → credits.
7. **buyer** → Export / Download JSONL.

## Click path — CV

1. KYB already approved (same org).
2. **buyer** → template **`cv_media`** → Create & submit (`synthetic_allowed=false`).
3. **admin** → 승인/게시.
4. **contributor** → pick CV campaign → upload PNG/JPEG/WebP/MP4 **or** allowlisted media URL → category + caption + bboxes → Submit → (`in_review` if async) → `needs_review`.  
   - Synthetic claim with `synthetic_allowed=false` → auto-reject `synthetic_not_allowed`.  
   - Duplicate same media+anno → `duplicate`.  
   - Non-allowlisted URL (when URL used) → `allowlist_reject`.
5. **admin** → 수락 (or **민감거절** / 합성 의심 거절).
6. **buyer** → Export JSONL (includes `storage_key` + annotation).

## API smoke (both paths)

```bash
cd backend && source .venv/bin/activate
# Sync (default local): VERIFY_MODE=sync or no Redis
python scripts/smoke_e2e.py
# against Compose API + worker (polls in_review → terminal):
# python scripts/smoke_e2e.py http://127.0.0.1:8000
```

Covers KYB stub packet upload + admin approve, OSINT allowlist reject + accept/export, and CV upload + synthetic reject + duplicate reject + accept/export. Works on SQLite or Postgres equally (same API). Async mode: script polls until verify leaves `submitted`/`in_review`.

## Allowlist v0

Seeded from `backend/app/allowlist_v0.py` (~30 public EN hosts). Online-only; no social dumps / conflict-zone field sources. Admin can add/disable/enable. Applies to OSINT URLs and CV media URLs (uploads skip host check but still require license claim + category whitelist).

## Stubbed vs real

**Real**

- Clerk IdP (+ local Bearer JWT fallback)
- Dual templates: `osint_label` | `cv_media` on one platform
- CV media upload (`data/media/` or S3) + annotation schema
- CV verification stages (type/schema/allowlist-or-upload provenance/duplicate/synthetic gate)
- Redis verify queue + `python -m app.worker` (Compose `redis` + `worker`); sync fallback
- S3-compatible object storage (MinIO profile / AWS via `S3_*`); local disk fallback
- Postgres schema via **Alembic** (`alembic upgrade head`); SQLite local `create_all`
- Shared manual review queue, CreditLedger, Dataset JSONL export (proxy + optional presign)
- Admin analytics summary: `GET /api/admin/analytics` + UI `/admin/analytics` (campaign status, submission outcomes, accept/reject rates, credits, per-campaign counts)
- KYB document **stub**: buyer `POST /api/orgs/{id}/kyb/packet` (+ optional `/kyb/upload`); admin views packet + approve/reject with KO memo (`POST .../kyb`)
- Versioned ontology: seed JSON `osint_label@0.1.0` / `cv_media@0.1.0`; campaigns pin `ontology_id`+`schema_version`; verify rejects schema mismatches — see [osint-ontology-v0.md](./osint-ontology-v0.md)

**Stubbed / deferred**

- Real KYB / ID-verification vendor; ML deepfake / perceptual hash
- On-chain token; fiat automation; full BI / charting
- Per-campaign allowlist subset
- Runtime ontology editor (edit seed JSON + bump version instead)

## Safety notes

- Online-only; no conflict-zone field collection UX
- CV public scenes only (parade / museum / official promo / airshow / open viewing)
- `synthetic_allowed=false` Phase-0 default
- Contributor/Buyer = English; Admin = Korean labels where useful
