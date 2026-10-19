#!/usr/bin/env python3
"""End-to-end happy path against a running API (default http://127.0.0.1:8000)."""

from __future__ import annotations

import json
import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def login(c: httpx.Client, email: str) -> tuple[dict[str, str], dict]:
    r = c.post("/api/auth/dev-login", json={"email": email})
    r.raise_for_status()
    data = r.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]


def main() -> None:
    c = httpx.Client(base_url=BASE, timeout=30.0)
    health = c.get("/api/health").json()
    assert health["status"] == "ok", health

    cfg = c.get("/api/auth/config").json()
    assert cfg["mode"] in ("dev", "clerk"), cfg
    if cfg["mode"] != "dev":
        print(
            json.dumps(
                {
                    "ok": False,
                    "skip": "smoke_e2e uses /api/auth/dev-login; run with AUTH_MODE=dev (default without Clerk keys)",
                    "auth": cfg,
                },
                indent=2,
            )
        )
        sys.exit(0)

    seed = c.post("/api/seed").json()
    admin_h, admin = login(c, "admin@demo.local")
    buyer_h, buyer = login(c, "buyer@demo.local")
    contrib_h, contrib = login(c, "contributor@demo.local")
    org_id = buyer["org_id"]
    assert org_id, buyer

    org = c.post(
        f"/api/orgs/{org_id}/kyb",
        headers=admin_h,
        json={"approve": True, "notes": "smoke"},
    ).json()
    assert org["kyb_status"] == "approved", org

    camp = c.post(
        "/api/campaigns",
        headers=buyer_h,
        json={
            "title": "Smoke OSINT",
            "description": "e2e",
            "unit_reward": 10,
            "pool_fund_amount": 100,
        },
    ).json()
    assert camp["status"] == "pending_review", camp

    camp = c.post(
        f"/api/campaigns/{camp['id']}/decide",
        headers=admin_h,
        json={"approve": True, "notes": "ok"},
    ).json()
    assert camp["status"] == "active", camp

    hosts = c.get("/api/allowlist", headers=admin_h).json()
    enabled = [h for h in hosts if h.get("enabled", True)]
    assert len(enabled) >= 15, f"expected allowlist v0 seed, got {len(enabled)}"

    # Allowlist reject path
    bad = c.post(
        "/api/submissions",
        headers=contrib_h,
        json={
            "campaign_id": camp["id"],
            "source_url": "https://not-on-allowlist.example/story",
            "labels": {
                "event_type": "official_briefing",
                "location_public": "Washington, DC",
                "event_time": "2026-04-01",
                "equipment_type": "aircraft",
            },
        },
    ).json()
    assert bad["verification_status"] == "rejected", bad
    assert bad["reject_reason"] == "allowlist_reject", bad
    assert (bad.get("metadata_json") or {}).get("allowlist_failure", {}).get("message"), bad

    sub = c.post(
        "/api/submissions",
        headers=contrib_h,
        json={
            "campaign_id": camp["id"],
            "source_url": "https://www.reuters.com/smoke-article",
            "labels": {
                "event_type": "official_briefing",
                "location_public": "Washington, DC",
                "event_time": "2026-04-01",
                "equipment_type": "aircraft",
            },
        },
    ).json()
    assert sub["verification_status"] == "needs_review", sub

    sub = c.post(
        f"/api/submissions/{sub['id']}/review",
        headers=admin_h,
        json={"accept": True, "reason_code": "quality_ok", "quality_mult": 1.0},
    ).json()
    assert sub["verification_status"] == "accepted", sub
    assert sub["final_reward"] == 10.0, sub

    me = c.get("/api/me", headers=contrib_h).json()
    assert me["credit_balance"] >= 10.0, me
    assert me["role"] == "contributor", me
    assert admin["role"] == "admin" and buyer["role"] == "buyer"

    ds = c.post(f"/api/campaigns/{camp['id']}/export", headers=buyer_h).json()
    assert ds["item_count"] >= 1, ds
    assert ds["version"] >= 1, ds

    dl = c.get(f"/api/datasets/{ds['id']}/download", headers=buyer_h)
    assert dl.status_code == 200, dl.text
    lines = [ln for ln in dl.text.strip().splitlines() if ln]
    assert len(lines) >= 1
    json.loads(lines[0])

    # Unauthenticated protected route must fail
    unauth = c.get("/api/me")
    assert unauth.status_code == 401, unauth.text

    print(
        json.dumps(
            {
                "ok": True,
                "auth_mode": cfg["mode"],
                "campaign_id": camp["id"],
                "submission_id": sub["id"],
                "dataset_id": ds["id"],
                "credits": me["credit_balance"],
                "allowlist_enabled": len(enabled),
                "allowlist_reject_ok": True,
                "bearer_required": True,
                "seed": seed,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
