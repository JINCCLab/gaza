#!/usr/bin/env python3
"""End-to-end happy paths (OSINT + CV) against a running API (default http://127.0.0.1:8000).

Works with VERIFY_MODE=sync (inline) and async Redis worker (polls until verify finishes).
"""

from __future__ import annotations

import io
import json
import sys
import time

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
PENDING = frozenset({"submitted", "in_review"})


def login(c: httpx.Client, email: str) -> tuple[dict[str, str], dict]:
    r = c.post("/api/auth/dev-login", json={"email": email})
    r.raise_for_status()
    data = r.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user"]


def wait_verified(
    c: httpx.Client,
    headers: dict,
    submission: dict,
    *,
    timeout_s: float = 30.0,
) -> dict:
    """Poll until automated stages leave submitted/in_review (async worker path)."""
    sid = submission["id"]
    status = submission.get("verification_status")
    if status not in PENDING:
        return submission
    deadline = time.time() + timeout_s
    last = submission
    while time.time() < deadline:
        time.sleep(0.25)
        r = c.get(f"/api/submissions/{sid}", headers=headers)
        r.raise_for_status()
        last = r.json()
        if last.get("verification_status") not in PENDING:
            return last
    raise AssertionError(
        f"submission {sid} still {last.get('verification_status')} after {timeout_s}s "
        f"(is the verify worker running?)"
    )


def ensure_kyb(c: httpx.Client, admin_h: dict, org_id: int) -> None:
    org = c.get(f"/api/orgs/{org_id}", headers=admin_h)
    # get may 403 for admin? admin can get — if pending, approve
    # use KYB endpoint idempotently
    r = c.post(
        f"/api/orgs/{org_id}/kyb",
        headers=admin_h,
        json={"approve": True, "notes": "smoke"},
    )
    r.raise_for_status()
    assert r.json()["kyb_status"] == "approved"


def smoke_osint(c: httpx.Client, admin_h: dict, buyer_h: dict, contrib_h: dict) -> dict:
    camp = c.post(
        "/api/campaigns",
        headers=buyer_h,
        json={
            "title": "Smoke OSINT",
            "description": "e2e osint",
            "data_type": "osint_label",
            "unit_reward": 10,
            "pool_fund_amount": 100,
        },
    ).json()
    assert camp["status"] == "pending_review", camp
    assert camp["data_type"] == "osint_label", camp

    camp = c.post(
        f"/api/campaigns/{camp['id']}/decide",
        headers=admin_h,
        json={"approve": True, "notes": "ok"},
    ).json()
    assert camp["status"] == "active", camp

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
    bad = wait_verified(c, contrib_h, bad)
    assert bad["verification_status"] == "rejected", bad
    assert bad["reject_reason"] == "allowlist_reject", bad

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
    sub = wait_verified(c, contrib_h, sub)
    assert sub["verification_status"] == "needs_review", sub

    sub = c.post(
        f"/api/submissions/{sub['id']}/review",
        headers=admin_h,
        json={"accept": True, "reason_code": "quality_ok", "quality_mult": 1.0},
    ).json()
    assert sub["verification_status"] == "accepted", sub
    assert sub["final_reward"] == 10.0, sub

    ds = c.post(f"/api/campaigns/{camp['id']}/export", headers=buyer_h).json()
    assert ds["item_count"] >= 1, ds
    dl = c.get(f"/api/datasets/{ds['id']}/download", headers=buyer_h)
    assert dl.status_code == 200, dl.text
    return {
        "campaign_id": camp["id"],
        "submission_id": sub["id"],
        "dataset_id": ds["id"],
        "item_count": ds["item_count"],
    }


def smoke_cv(c: httpx.Client, admin_h: dict, buyer_h: dict, contrib_h: dict) -> dict:
    camp = c.post(
        "/api/campaigns",
        headers=buyer_h,
        json={
            "title": "Smoke CV public scenes",
            "description": "e2e cv_media",
            "data_type": "cv_media",
            "synthetic_allowed": False,
            "unit_reward": 12,
            "pool_fund_amount": 120,
        },
    ).json()
    assert camp["status"] == "pending_review", camp
    assert camp["data_type"] == "cv_media", camp
    assert camp["data_class"] == "public_scene_cv", camp
    assert camp["synthetic_allowed"] is False, camp
    assert "parade_public" in (camp.get("requirements_json") or {}).get("categories", []), camp

    camp = c.post(
        f"/api/campaigns/{camp['id']}/decide",
        headers=admin_h,
        json={"approve": True, "notes": "CV 정책 통과"},
    ).json()
    assert camp["status"] == "active", camp

    # Synthetic claim rejected when synthetic_allowed=false
    syn = c.post(
        "/api/submissions",
        headers=contrib_h,
        json={
            "campaign_id": camp["id"],
            "source_url": "https://www.defense.gov/smoke-parade.jpg",
            "annotation": {
                "category": "parade_public",
                "caption": "Public parade vehicle (synthetic claim)",
                "bboxes": [{"x": 0.1, "y": 0.1, "w": 0.4, "h": 0.5, "label": "vehicle"}],
            },
            "claims_synthetic": True,
            "license_claim": "public_official_media",
        },
    ).json()
    syn = wait_verified(c, contrib_h, syn)
    assert syn["verification_status"] == "rejected", syn
    assert syn["reject_reason"] == "synthetic_not_allowed", syn

    # Bad category
    bad_cat = c.post(
        "/api/submissions",
        headers=contrib_h,
        json={
            "campaign_id": camp["id"],
            "source_url": "https://www.defense.gov/other.jpg",
            "annotation": {
                "category": "battlefield_ops",
                "caption": "should fail",
                "bboxes": [],
            },
        },
    ).json()
    bad_cat = wait_verified(c, contrib_h, bad_cat)
    assert bad_cat["verification_status"] == "rejected", bad_cat
    assert bad_cat["reject_reason"] == "schema_policy", bad_cat

    # Upload tiny PNG + annotation
    # 1x1 PNG
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    up = c.post(
        "/api/media/upload",
        headers=contrib_h,
        files={"file": ("scene.png", io.BytesIO(png), "image/png")},
    )
    up.raise_for_status()
    media = up.json()
    assert media["storage_key"], media

    sub = c.post(
        "/api/submissions",
        headers=contrib_h,
        json={
            "campaign_id": camp["id"],
            "storage_key": media["storage_key"],
            "content_type": media["content_type"],
            "sha256": media["sha256"],
            "annotation": {
                "category": "museum_exhibit",
                "caption": "Museum exhibit aircraft display (public)",
                "bboxes": [{"x": 0.2, "y": 0.2, "w": 0.5, "h": 0.4, "label": "aircraft"}],
            },
            "license_claim": "museum_public_photography_ok",
            "claims_synthetic": False,
        },
    ).json()
    sub = wait_verified(c, contrib_h, sub)
    assert sub["verification_status"] == "needs_review", sub
    assert sub["storage_key"] == media["storage_key"], sub

    # Duplicate reject
    dup = c.post(
        "/api/submissions",
        headers=contrib_h,
        json={
            "campaign_id": camp["id"],
            "storage_key": media["storage_key"],
            "content_type": media["content_type"],
            "sha256": media["sha256"],
            "annotation": {
                "category": "museum_exhibit",
                "caption": "Museum exhibit aircraft display (public)",
                "bboxes": [{"x": 0.2, "y": 0.2, "w": 0.5, "h": 0.4, "label": "aircraft"}],
            },
            "license_claim": "museum_public_photography_ok",
        },
    ).json()
    dup = wait_verified(c, contrib_h, dup)
    assert dup["verification_status"] == "rejected", dup
    assert dup["reject_reason"] == "duplicate", dup

    sub = c.post(
        f"/api/submissions/{sub['id']}/review",
        headers=admin_h,
        json={
            "accept": True,
            "reason_code": "quality_ok",
            "quality_mult": 1.0,
            "internal_memo_ko": "CV 공개 장면 수락",
        },
    ).json()
    assert sub["verification_status"] == "accepted", sub
    assert sub["final_reward"] == 12.0, sub

    ds = c.post(f"/api/campaigns/{camp['id']}/export", headers=buyer_h).json()
    assert ds["item_count"] >= 1, ds
    assert ds["manifest_json"]["data_type"] == "cv_media", ds
    dl = c.get(f"/api/datasets/{ds['id']}/download", headers=buyer_h)
    assert dl.status_code == 200, dl.text
    row = json.loads(dl.text.strip().splitlines()[0])
    assert row.get("annotation") or row.get("labels"), row
    assert row.get("storage_key"), row

    return {
        "campaign_id": camp["id"],
        "submission_id": sub["id"],
        "dataset_id": ds["id"],
        "item_count": ds["item_count"],
        "synthetic_reject_ok": True,
        "duplicate_reject_ok": True,
        "upload_ok": True,
    }


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
                    "skip": "smoke_e2e uses /api/auth/dev-login; run with AUTH_MODE=dev",
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
    ensure_kyb(c, admin_h, org_id)

    hosts = c.get("/api/allowlist", headers=admin_h).json()
    enabled = [h for h in hosts if h.get("enabled", True)]
    assert len(enabled) >= 15, f"expected allowlist v0 seed, got {len(enabled)}"

    osint = smoke_osint(c, admin_h, buyer_h, contrib_h)
    cv = smoke_cv(c, admin_h, buyer_h, contrib_h)

    me = c.get("/api/me", headers=contrib_h).json()
    assert me["credit_balance"] >= 22.0, me  # 10 OSINT + 12 CV

    unauth = c.get("/api/me")
    assert unauth.status_code == 401, unauth.text

    # Admin analytics — founder ops summary (admin-only)
    forbidden = c.get("/api/admin/analytics", headers=buyer_h)
    assert forbidden.status_code == 403, forbidden.text
    analytics = c.get("/api/admin/analytics", headers=admin_h)
    assert analytics.status_code == 200, analytics.text
    a = analytics.json()
    assert a["submissions_total"] >= 2, a
    assert a["funnel"]["accepted"] >= 2, a
    assert a["credits"]["rewards_granted_total"] >= 22.0, a
    assert isinstance(a["campaigns_by_status"], list), a
    assert isinstance(a["per_campaign"], list) and len(a["per_campaign"]) >= 1, a

    print(
        json.dumps(
            {
                "ok": True,
                "auth_mode": cfg["mode"],
                "verify_mode": health.get("verify_mode"),
                "verify_path": health.get("verify_path"),
                "redis": health.get("redis"),
                "storage_backend": health.get("storage_backend"),
                "storage": health.get("storage"),
                "osint": osint,
                "cv": cv,
                "credits": me["credit_balance"],
                "analytics": {
                    "campaigns_total": a["campaigns_total"],
                    "submissions_total": a["submissions_total"],
                    "accept_rate": a["funnel"]["accept_rate"],
                    "rewards_granted": a["credits"]["rewards_granted_total"],
                    "per_campaign": len(a["per_campaign"]),
                },
                "allowlist_enabled": len(enabled),
                "roles": {
                    "admin": admin["role"],
                    "buyer": buyer["role"],
                    "contributor": contrib["role"],
                },
                "seed": seed,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
