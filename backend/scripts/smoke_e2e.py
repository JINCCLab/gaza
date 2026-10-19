#!/usr/bin/env python3
"""End-to-end happy path against a running API (default http://127.0.0.1:8000)."""

from __future__ import annotations

import json
import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def hdr(uid: int) -> dict[str, str]:
    return {"X-User-Id": str(uid)}


def main() -> None:
    c = httpx.Client(base_url=BASE, timeout=30.0)
    health = c.get("/api/health").json()
    assert health["status"] == "ok", health

    seed = c.post("/api/seed").json()
    users = {u["email"]: u for u in c.get("/api/users").json()}
    admin = users["admin@demo.local"]["id"]
    buyer = users["buyer@demo.local"]["id"]
    contrib = users["contributor@demo.local"]["id"]
    org_id = users["buyer@demo.local"]["org_id"]

    org = c.post(
        f"/api/orgs/{org_id}/kyb",
        headers=hdr(admin),
        json={"approve": True, "notes": "smoke"},
    ).json()
    assert org["kyb_status"] == "approved", org

    camp = c.post(
        "/api/campaigns",
        headers=hdr(buyer),
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
        headers=hdr(admin),
        json={"approve": True, "notes": "ok"},
    ).json()
    assert camp["status"] == "active", camp

    sub = c.post(
        "/api/submissions",
        headers=hdr(contrib),
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
        headers=hdr(admin),
        json={"accept": True, "reason_code": "quality_ok", "quality_mult": 1.0},
    ).json()
    assert sub["verification_status"] == "accepted", sub
    assert sub["final_reward"] == 10.0, sub

    me = c.get("/api/me", headers=hdr(contrib)).json()
    assert me["credit_balance"] >= 10.0, me

    ds = c.post(f"/api/campaigns/{camp['id']}/export", headers=hdr(buyer)).json()
    assert ds["item_count"] >= 1, ds
    assert ds["version"] >= 1, ds

    dl = c.get(f"/api/datasets/{ds['id']}/download", headers=hdr(buyer))
    assert dl.status_code == 200, dl.text
    lines = [ln for ln in dl.text.strip().splitlines() if ln]
    assert len(lines) >= 1
    json.loads(lines[0])

    print(
        json.dumps(
            {
                "ok": True,
                "campaign_id": camp["id"],
                "submission_id": sub["id"],
                "dataset_id": ds["id"],
                "credits": me["credit_balance"],
                "seed": seed,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
