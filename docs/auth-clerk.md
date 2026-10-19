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

## API helpers

- `GET /api/auth/config` — effective mode
- `POST /api/auth/dev-login` — `{ "email": "admin@demo.local" }` (dev only)
- `GET /api/auth/personas` — seeded list (dev only)
- `GET /api/me` — requires Bearer
