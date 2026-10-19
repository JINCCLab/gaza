# Auth — Clerk (Phase-0)

## Why Clerk (not Supabase Auth)

| | Clerk | Supabase Auth |
|--|-------|---------------|
| Next.js App Router | First-class `@clerk/nextjs` (Provider, SignIn, session `getToken`) | Possible via SSR helpers; more glue for a separate FastAPI API |
| FastAPI | Verify session JWT via JWKS (+ optional Backend API for email/role) | Verify JWT with project JWKS / secret |
| Roles | `publicMetadata.role` → admin / buyer / contributor | `app_metadata` / custom claims |
| Fit for this repo | **Faster**: UI already Next.js; API is FastAPI + SQLite (no Supabase project required for MVP) | Better if we already standardized on Supabase Postgres + RLS |

**Decision:** Clerk for Phase-0 IdP. Local **dev session JWT** fallback when keys are missing so the KYB→export loop still runs.

## Modes

| `AUTH_MODE` | Behavior |
|-------------|----------|
| `auto` (default) | Clerk if `CLERK_SECRET_KEY` + (`CLERK_ISSUER` or `CLERK_JWKS_URL`); else **dev** |
| `clerk` | Require Clerk (fail closed) |
| `dev` | Force `POST /api/auth/dev-login` HS256 Bearer tokens |

Protected routes expect:

```http
Authorization: Bearer <token>
```

`X-User-Id` is **retired**.

## Roles

Preserved: `admin` | `buyer` | `contributor`.

1. Clerk Dashboard → User → **publicMetadata**: `{ "role": "admin" }` (or buyer / contributor).
2. Else seed email map (`admin@demo.local`, …).
3. Else default `contributor` on first provision.

Local users link via `users.auth_subject` (Clerk user id or `dev:<email>`).

### Setting `publicMetadata.role` (Dashboard)

1. Open [Clerk Dashboard](https://dashboard.clerk.com) → your application → **Users**.
2. Open the user → **Metadata** (or User → Public metadata).
3. Set JSON (exactly one role string):

```json
{ "role": "admin" }
```

Allowed values: `"admin"` | `"buyer"` | `"contributor"`. Save. Sign out/in (or refresh session) so the API re-reads metadata (Backend API enrichment on first provision).

## Run with Clerk keys

1. Copy [`.env.example`](../.env.example) → `backend/.env` and `frontend/.env.local`.
2. Fill `CLERK_SECRET_KEY`, `CLERK_PUBLISHABLE_KEY`, `CLERK_ISSUER`.
3. Set `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` (same publishable key) and `NEXT_PUBLIC_API_URL`.
4. Create three users in Clerk; set `publicMetadata.role` each.
5. Start API + UI; open `/sign-in` (Clerk widget).

## Run without keys (local)

1. Leave Clerk vars empty (`AUTH_MODE=auto` → `dev`).
2. Start API + UI as usual.
3. Open `/sign-in` → pick seeded persona → Bearer JWT stored in `localStorage`.
4. Smoke: `python scripts/smoke_e2e.py` (uses `/api/auth/dev-login`).

## Production setup (no secrets in git)

Paste keys only in host dashboards / local `.env` files. Never commit real `sk_` / `pk_` values.

### 1. Clerk application

1. Create an app at https://dashboard.clerk.com (Development instance for staging; Production for live).
2. Copy **Publishable key** + **Secret key**.
3. Copy **Frontend API / Issuer** URL (`https://….clerk.accounts.dev` or production Clerk domain).
4. **Paths & URLs** → allow your Netlify (and localhost) origins + redirect URLs — see table in [`.env.example`](../.env.example).
5. Create users; set `publicMetadata.role` as above.

### 2. Netlify (Next.js frontend)

Repo root [`netlify.toml`](../netlify.toml) sets `base = "frontend"` and the Next.js build plugin so previews build the App Router app (not the monorepo root).

| Variable | Where | Notes |
|----------|--------|--------|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Netlify env | Same as Clerk publishable key |
| `NEXT_PUBLIC_API_URL` | Netlify env | Public FastAPI base, e.g. `https://api.example.com` (no trailing slash) |
| `CLERK_SECRET_KEY` | Optional on Netlify | Not required for current client-only Clerk widget; add if you enable `clerkMiddleware` later |

Site settings → Environment variables → add for Production (and Deploy Previews if you want Clerk on previews). Redeploy after changing `NEXT_PUBLIC_*`.

### 3. FastAPI host

| Variable | Required | Notes |
|----------|----------|--------|
| `AUTH_MODE` | Recommended `clerk` | Fail closed on public API |
| `CLERK_SECRET_KEY` | Yes | Verifies session JWT + Backend API user enrich |
| `CLERK_ISSUER` or `CLERK_JWKS_URL` | Yes | JWKS for Bearer verification |
| `CLERK_PUBLISHABLE_KEY` | Optional | Documented for parity with local `.env` |
| `DATABASE_URL` | Recommended | Postgres when leaving demo SQLite |
| `DEV_JWT_SECRET` | N/A if `clerk` | Do not rely on dev login in production |

Example bind: `uvicorn app.main:app --host 0.0.0.0 --port $PORT` from `backend/` with deps installed.

### 4. Verify login

1. `GET {API}/api/health` → `stubbed` should mention `auth_clerk_mode_active` (not the dev fallback string).
2. `GET {API}/api/auth/config` → effective mode `clerk`.
3. Open `https://YOUR-SITE/sign-in` → Clerk widget (not persona cards).
4. Sign in → `GET /api/me` with Bearer succeeds; role matches `publicMetadata`.

Korean founder checklist (create app → keys → env → deploy → verify): project store `docs/clerk-deploy-setup.md`.

## API helpers

- `GET /api/auth/config` — effective mode
- `POST /api/auth/dev-login` — `{ "email": "admin@demo.local" }` (dev only)
- `GET /api/auth/personas` — seeded list (dev only)
- `GET /api/me` — requires Bearer
