# data_platform — Phase-0 OSINT vertical slice

Minimal end-to-end loop:

**KYB Org → OSINT campaign draft → Admin approve → Contributor EN submission → auto verify stub + manual accept → CreditLedger → Dataset JSONL export**

Stack: **Next.js** (frontend) + **FastAPI** (API) + **SQLite** by default (Postgres via `DATABASE_URL` / optional `docker-compose.yml`).

## Quick start

```bash
# API
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

Open http://localhost:3000 — use the **Act as** role switcher (demo auth via `X-User-Id`).

Smoke test (API must be up):

```bash
cd backend && source .venv/bin/activate
python scripts/smoke_e2e.py
```

Full click-path: see [docs/mvp-slice-runbook.md](https://github.com/JINCCLab/gaza) in the Project store, or `/cursor/stores/.../docs/mvp-slice-runbook.md` when working in Cursor Project context.

## Stubbed vs real

| Real in this slice | Stubbed / deferred |
|--------------------|--------------------|
| Domain models + SQLite persistence | Clerk/Supabase auth → header demo users |
| KYB status flag approve/reject | Full KYB document workflow |
| Campaign draft → pending_review → active | Pause/close settlement polish |
| OSINT submit (URL + labels JSON) | CV template, media upload |
| Allowlist host check (config + Admin add) | Founder-filled production host list |
| Verification stages 1–7 (heuristic) | Redis worker, deepfake ML, perceptual hash |
| Manual accept/reject queue | Validator marketplace |
| CreditLedger reward + redeem_reserve | On-chain token / TGE |
| Dataset v1 JSONL file export | S3 object storage |

## Layout

```
backend/          FastAPI app
frontend/         Next.js App Router UI
docker-compose.yml  Optional Postgres
data/             SQLite DB (gitignored)
exports/          Generated JSONL (gitignored)
```
