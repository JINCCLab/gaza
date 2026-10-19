# data_platform — Phase-0 OSINT vertical slice

Minimal end-to-end loop:

**Sign in → KYB Org → OSINT or CV campaign draft → Admin approve → Contributor EN submission (labels or media+annotation) → auto verify stub + manual accept → CreditLedger → Dataset JSONL export**

Stack: **Next.js** (frontend) + **FastAPI** (API) + **SQLite** by default (Postgres via `DATABASE_URL` / optional `docker-compose.yml`) + **Clerk** IdP (local Bearer JWT fallback when keys missing).

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

## With Clerk keys

1. Copy [`.env.example`](./.env.example) into `backend/.env` and `frontend/.env.local`.
2. Set `CLERK_SECRET_KEY`, `CLERK_ISSUER` (or `CLERK_JWKS_URL`), and `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`.
3. In Clerk Dashboard, set each user’s `publicMetadata.role` to `admin` | `buyer` | `contributor`.
4. Restart API + UI → `/sign-in` shows the Clerk widget.

See [docs/auth-clerk.md](./docs/auth-clerk.md) for why Clerk over Supabase Auth, roles via `publicMetadata.role`, and **production** Netlify + FastAPI env vars / redirect URLs. Frontend deploy uses root [`netlify.toml`](./netlify.toml) (`base = frontend`).

Full click-path: [docs/mvp-slice-runbook.md](./docs/mvp-slice-runbook.md).

## Stubbed vs real

| Real in this slice | Stubbed / deferred |
|--------------------|--------------------|
| Clerk JWT + local Bearer session fallback | Production Clerk org sync / webhooks polish |
| Dual templates `osint_label` + `cv_media` (local media upload) | S3 media; ML deepfake / perceptual hash |
| Domain models + SQLite persistence | — |
| KYB status flag approve/reject | Full KYB document workflow |
| Campaign draft → pending_review → active | Pause/close settlement polish |
| OSINT + CV submit (URL/labels or upload+annotation) | Perceptual hash / commercial deepfake stack |
| Allowlist v0 (~30 EN public hosts) + Admin disable | Per-campaign allowlist subset; further founder expand |
| Verification stages 1–7 (heuristic) | Redis worker, deepfake ML, perceptual hash |
| Manual accept/reject queue | Validator marketplace |
| CreditLedger reward + redeem_reserve | On-chain token / TGE |
| Dataset v1 JSONL file export | S3 object storage |

## Layout

```
backend/          FastAPI app
frontend/         Next.js App Router UI
docs/             Runbook + auth notes
.env.example      Clerk + DATABASE_URL template
docker-compose.yml  Optional Postgres
data/             SQLite DB (gitignored)
exports/          Generated JSONL (gitignored)
```
