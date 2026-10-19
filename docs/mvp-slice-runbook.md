# MVP slice runbook — Phase-0 dual wedge (OSINT + CV)

How to run the coding slice and walk OSINT and CV happy paths (same platform).

## Prerequisites

- Python **3.9+** (backend uses `Optional`/`List`/`Dict` — FastAPI-safe on 3.9; no PEP 604 `X | Y`)
- Node 20+
- Repo branch with `backend/` + `frontend/`
- Optional: Clerk application keys (see [auth-clerk.md](./auth-clerk.md); production checklist in project store `docs/clerk-deploy-setup.md`)

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
| `osint_label` | `structured_osint` | allowlisted source URL + event/location/time/equipment labels | Phase-0 first wedge |
| `cv_media` | `public_scene_cv` | media **upload** and/or allowlisted URL + annotation `{category, caption, bboxes[]}` | `synthetic_allowed=false` by default |

CV category whitelist (defaults): `parade_public`, `museum_exhibit`, `official_promo`, `public_airshow`, `open_training_viewing`.

## Click path — OSINT

1. `/sign-in` → **admin** → Org KYB 승인.
2. **buyer** → template `osint_label` → Create & submit for review.
3. **admin** → 캠페인 사전승인 → 승인/게시.
4. **contributor** → Reuters (allowlisted) URL + labels → Submit → `needs_review`.
5. **admin** → 수락 → credits.
6. **buyer** → Export / Download JSONL.

## Click path — CV

1. KYB already approved (same org).
2. **buyer** → template **`cv_media`** → Create & submit (`synthetic_allowed=false`).
3. **admin** → 승인/게시.
4. **contributor** → pick CV campaign → upload PNG/JPEG/WebP/MP4 **or** allowlisted media URL → category + caption + bboxes → Submit → `needs_review`.  
   - Synthetic claim with `synthetic_allowed=false` → auto-reject `synthetic_not_allowed`.  
   - Duplicate same media+anno → `duplicate`.  
   - Non-allowlisted URL (when URL used) → `allowlist_reject`.
5. **admin** → 수락 (or **민감거절** / 합성 의심 거절).
6. **buyer** → Export JSONL (includes `storage_key` + annotation).

## API smoke (both paths)

```bash
cd backend && source .venv/bin/activate
python scripts/smoke_e2e.py
```

Covers OSINT allowlist reject + accept/export, and CV upload + synthetic reject + duplicate reject + accept/export.

## Allowlist v0

Seeded from `backend/app/allowlist_v0.py` (~30 public EN hosts). Online-only; no social dumps / conflict-zone field sources. Admin can add/disable/enable. Applies to OSINT URLs and CV media URLs (uploads skip host check but still require license claim + category whitelist).

## Stubbed vs real

**Real**

- Clerk IdP (+ local Bearer JWT fallback)
- Dual templates: `osint_label` | `cv_media` on one platform
- CV local media upload (`data/media/`) + annotation schema
- CV verification stages (type/schema/allowlist-or-upload provenance/duplicate/synthetic gate)
- Shared manual review queue, CreditLedger, Dataset JSONL export

**Stubbed / deferred**

- KYB document upload; Redis worker; ML deepfake / perceptual hash
- S3 object storage (local disk for CV media)
- On-chain token; fiat automation; analytics dashboards
- Per-campaign allowlist subset

## Safety notes

- Online-only; no conflict-zone field collection UX
- CV public scenes only (parade / museum / official promo / airshow / open viewing)
- `synthetic_allowed=false` Phase-0 default
- Contributor/Buyer = English; Admin = Korean labels where useful
