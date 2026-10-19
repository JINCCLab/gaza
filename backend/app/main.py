from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import SessionLocal
from app.db_migrate import apply_schema
from app.routers import (
    allowlist,
    analytics,
    auth,
    campaigns,
    datasets,
    media,
    ontology,
    orgs,
    submissions,
)
from app.schemas import HealthOut
from app.seed import seed_demo
from app.services.queue import effective_verify_path, redis_status
from app.services.storage import ensure_bucket, storage_health

app = FastAPI(
    title="data_platform Phase-0 API",
    description="Phase-0 dual wedge: OSINT + CV templates — KYB → campaign → submit → verify → credit → export",
    version="0.10.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(orgs.router)
app.include_router(campaigns.router)
app.include_router(submissions.router)
app.include_router(datasets.router)
app.include_router(allowlist.router)
app.include_router(media.router)
app.include_router(analytics.router)
app.include_router(ontology.router)


@app.on_event("startup")
def on_startup() -> None:
    # SQLite: create_all + column patches. Postgres: alembic upgrade head
    # (see app/db_migrate.py + alembic/versions/). Pre-Alembic PG volumes get stamped.
    apply_schema()
    ensure_bucket()
    db = SessionLocal()
    try:
        seed_demo(db)
    finally:
        db.close()


@app.get("/api/health", response_model=HealthOut)
def health() -> HealthOut:
    mode = settings.resolved_auth_mode()
    path = effective_verify_path()
    rstatus = redis_status()
    s_backend, s_status = storage_health()
    stubbed = [
        "kyb_document_stub_no_id_vendor",
        "verification_stages_1_7_heuristic",
        "fraud_synthetic_scores_stub",
        "no_onchain_token",
        "cv_synthetic_deepfake_ml_stub",
        "allowlist_v0_founder_may_expand",
        "analytics_phase0_summary_only",
        "ontology_seed_json_no_runtime_editor",
        "url_reachability_head_stub_no_scrape",
        "dual_annotate_sample_not_workforce",
    ]
    if s_backend == "local":
        stubbed.insert(0, "storage_local_disk_set_s3_for_object_storage")
    else:
        stubbed.insert(0, "storage_s3_compatible_active")
    if path == "sync":
        stubbed.insert(0, "verify_sync_inline_set_redis_for_async_worker")
    else:
        stubbed.insert(0, "verify_async_redis_worker_active")
    if mode == "dev":
        stubbed.insert(0, "auth_dev_jwt_fallback_set_clerk_keys_for_prod")
    else:
        stubbed.insert(0, "auth_clerk_mode_active")
    return HealthOut(
        status="ok",
        database=settings.database_url.split("://")[0],
        stubbed=stubbed,
        verify_mode=settings.verify_mode,
        verify_path=path,
        redis=rstatus,
        storage_backend=s_backend,
        storage=s_status,
    )
