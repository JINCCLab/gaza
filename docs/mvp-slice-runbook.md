# MVP slice runbook — Phase-0 OSINT vertical

How to run the first coding slice and walk the happy path.

## Prerequisites

- Python **3.9+** (backend uses `Optional`/`List`/`Dict` — FastAPI-safe on 3.9; no PEP 604 `X | Y`)
- Node 20+
- Repo branch with `backend/` + `frontend/` (this slice)

## Start services

**Terminal A — API**

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal B — UI**

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 npm run dev
```

- UI: http://localhost:3000  
- API docs: http://127.0.0.1:8000/docs  
- Health: `GET /api/health` (lists stubbed areas)

Demo users are seeded on API startup:

| Role | Email | Notes |
|------|-------|--------|
| admin | admin@demo.local | Founder ops (KO UI) |
| buyer | buyer@demo.local | Org KYB starts `pending` |
| contributor | contributor@demo.local | EN submit UI |

Auth is **demo-only**: the UI sends `X-User-Id` (use the header **Act as** switcher).

## Click path (happy path)

1. Open http://localhost:3000 → switch to **admin**.
2. **Admin → Org KYB** → 승인 (approve) Demo OSINT Intel Firm.
3. Switch to **buyer** → **Create & submit for review** (pool funds with 15% fee stub).
4. Switch to **admin** → **캠페인 사전승인** → 승인/게시.
5. Switch to **contributor** → pick active campaign → keep default Reuters URL (allowlisted) → **Submit**.  
   Status should become `needs_review` after automated stages.
6. Switch to **admin** → **제출 리뷰 큐** → 수락 (accept). Credits grant on accept.
7. Switch to **buyer** → **Export JSONL** → **Download JSONL**.

Optional API smoke (same path without UI):

```bash
cd backend && source .venv/bin/activate
python scripts/smoke_e2e.py
```

## Stubbed vs real

**Real**

- Org KYB status gate before campaign create
- Campaign status machine (`draft`/`pending_review` → `active`)
- EN OSINT submission schema (source URL + labels JSON)
- Allowlist host evaluation + Admin host add
- Automated verification stage events (tech → schema → provenance → duplicate → fraud → synthetic → quality → route)
- Manual accept/reject + reason / KO memo
- CreditLedger `pool_fund` / `fee` / `reward` / `redeem_reserve`
- Dataset version + local JSONL export download

**Stubbed / not in this slice**

- Real IdP (Clerk/Supabase); KYB document upload
- Redis async worker; ML fraud/deepfake
- S3 storage; on-chain token; CV template
- Fiat invoice automation; analytics dashboards
- Production EN allowlist domains (placeholders only)

## Safety notes

- Online-only OSINT; no conflict-zone field collection UX
- Contributor/Buyer copy = English; Admin = Korean labels where useful
