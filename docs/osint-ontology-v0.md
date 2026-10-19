# OSINT ontology / label schema v0

Phase-0 **versioned** label ontology for structured OSINT (and a companion CV public-scene schema). Seed JSON only — no runtime editor, no ID vendor, no targeting fields.

## Identifiers

| ontology_id   | schema_version | data_type     | Seed file |
|---------------|----------------|---------------|-----------|
| `osint_label` | `0.1.0`        | `osint_label` | `backend/app/ontology/osint_v0.json` |
| `cv_media`    | `0.1.0`        | `cv_media`    | `backend/app/ontology/cv_v0.json` |

Campaigns **pin** `ontology_id` + `schema_version` at create time (default = current seed for that `data_type`).

## OSINT required labels (`0.1.0`)

| Field | Type | Notes |
|-------|------|--------|
| `event_type` | enum | `military_exercise`, `equipment_display`, `official_briefing`, `port_call_public`, `airshow_public` |
| `location_public` | string | Public city/region or named public facility |
| `event_time` | string | Reported date/time (ISO preferred) |
| `equipment_type` | enum | `aircraft`, `naval`, `ground`, `missile_system_public`, `unknown` |
| `source_url` | URL (submission) | Allowlisted public EN host |

Campaign-level (not a submission label): `location_granularity` ∈ `public_city_region` \| `public_facility_named` \| `country_only`.

Optional: `notes` (no PII).

## Safety constraints (legal / open OSINT)

**In scope:** online-only public open-source reporting from allowlisted EN news/official hosts.

**Out of scope / forbidden themes in the schema:**

- civilian targeting intent
- individual PII
- conflict-zone field collection
- sub-city geocoordinate precision as a required field

## Validation

Automated verify stage `schema_policy`:

- Loads the ontology pinned on the campaign
- Rejects (`verification_status=rejected`, `reject_reason=schema_policy`) on missing required fields or enum mismatch
- Allowlist / provenance remains a separate stage

## API

- `GET /api/ontology` — list versions (auth)
- `GET /api/ontology/{ontology_id}?version=0.1.0` — full seed document
- Campaign create accepts optional `ontology_id` / `schema_version`; response echoes pins
- UI: `/admin/ontology` (Admin + Buyer)

## Editing (MVP)

Change the seed JSON under `backend/app/ontology/`, bump `schema_version`, redeploy. Do not mutate a pinned version in place once campaigns reference it — add `0.2.0` instead.

## Runbook

See [mvp-slice-runbook.md](./mvp-slice-runbook.md) (ontology pointer + click path).
