# MVP slice runbook — Phase-0 OSINT vertical

How to run the coding slice and walk the happy path (after IdP auth slice).

## Prerequisites

- Python **3.9+** (backend uses `Optional`/`List`/`Dict` — FastAPI-safe on 3.9; no PEP 604 `X | Y`)
- Node 20+
- Repo branch with `backend/` + `frontend/`
- Optional: Clerk application keys (see [auth-clerk.md](./auth-clerk.md))

## Start services

**Terminal A — API**

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# optional: cp ../.env.example .env  # fill Clerk keys for production IdP
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal B — UI**

```bash
cd frontend
npm install
# optional: frontend/.env.local with NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY + NEXT_PUBLIC_API_URL
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 npm run dev
```

- UI: http://localhost:3000  
- Sign-in: http://localhost:3000/sign-in  
- API docs: http://127.0.0.1:8000/docs  
- Health: `GET /api/health`  
- Auth config: `GET /api/auth/config`

## Auth (Clerk or local session)

**IdP choice: Clerk** — faster Next.js + FastAPI JWT wiring than Supabase Auth for this stack. Details: [auth-clerk.md](./auth-clerk.md).

| Mode | When | How to sign in |
|------|------|----------------|
| **Clerk** | `CLERK_SECRET_KEY` + issuer/JWKS set | UI Clerk widget; API verifies Bearer session JWT |
| **Dev** (default without keys) | Keys missing / `AUTH_MODE=dev` | `/sign-in` persona → `POST /api/auth/dev-login` → Bearer JWT in `localStorage` |

Roles: **admin** / **buyer** / **contributor** (Clerk `publicMetadata.role` or seed emails).

`X-User-Id` / header **Act as** are **retired**. APIs require `Authorization: Bearer <token>`.

Seeded personas (dev):

| Role | Email | Notes |
|------|-------|--------|
| admin | admin@demo.local | Founder ops (KO UI) |
| buyer | buyer@demo.local | Org KYB starts `pending` |
| contributor | contributor@demo.local | EN submit UI |

## Click path (happy path)

1. Open http://localhost:3000/sign-in → sign in as **admin** (persona or Clerk).
2. **Admin → Org KYB** → 승인 (approve) Demo OSINT Intel Firm.
3. Sign out / Switch account → **buyer** → **Create & submit for review** (pool funds with 15% fee stub).
4. Switch to **admin** → **캠페인 사전승인** → 승인/게시.
5. Switch to **contributor** → pick active campaign → keep default Reuters URL (allowlisted) → **Submit**.  
   Status should become `needs_review` after automated stages.  
   Optional: try a non-allowlisted URL — you should see a clear **Allowlist rejection** message.
6. Switch to **admin** → **제출 리뷰 큐** → 수락 (accept). Credits grant on accept.
7. Switch to **buyer** → **Export JSONL** → **Download JSONL**.

Optional API smoke (dev auth; API must be up):

```bash
cd backend && source .venv/bin/activate
python scripts/smoke_e2e.py
```

## Allowlist v0

Seeded on startup from `backend/app/allowlist_v0.py` (~30 public EN hosts). Categories:

| Category | Examples |
|----------|----------|
| `us_wire_national` | reuters.com, apnews.com, nytimes.com, washingtonpost.com, wsj.com, bloomberg.com, usatoday.com |
| `us_defense_outlet` | defenseone.com, defensenews.com, militarytimes.com, breakingdefense.com, airandspaceforces.com |
| `us_gov_military` | defense.gov, navy.mil, army.mil, af.mil, marines.mil, state.gov, whitehouse.gov |
| `asia_en_outlet` | straitstimes.com, scmp.com, japantimes.co.jp, koreaherald.com, channelnewsasia.com, thejakartapost.com, bangkokpost.com |
| `en_international` | bbc.com, theguardian.com |
| `public_eo_archive` | earthobservatory.nasa.gov, usgs.gov |

**Rules:** online-only; enabled hosts only; `www.` / apex both match; Admin can **add** / **disable** / **enable**. Non-allowlisted submit → `reject_reason=allowlist_reject` + EN failure message on Contributor UI. No social dumps / conflict-zone field sources. KR hosts not required in Phase-0. Founder may expand after Buyer interviews.

## Stubbed vs real

**Real**

- **Clerk IdP integration** (+ local Bearer JWT session fallback)
- Org KYB status gate before campaign create
- Campaign status machine (`draft`/`pending_review` → `active`)
- EN OSINT submission schema (source URL + labels JSON)
- Allowlist v0 seed + evaluation + Admin list/add/disable
- Automated verification stage events (tech → schema → provenance → duplicate → fraud → synthetic → quality → route)
- Manual accept/reject + reason / KO memo
- CreditLedger `pool_fund` / `fee` / `reward` / `redeem_reserve`
- Dataset version + local JSONL export download

**Stubbed / not in this slice**

- KYB document upload
- Redis async worker; ML fraud/deepfake
- S3 storage; on-chain token; CV template
- Fiat invoice automation; analytics dashboards
- Per-campaign allowlist subset (global list only for now)

## Safety notes

- Online-only OSINT; no conflict-zone field collection UX
- Contributor/Buyer copy = English; Admin = Korean labels where useful
