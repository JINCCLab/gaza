from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.routers import allowlist, auth, campaigns, datasets, media, orgs, submissions
from app.schema_migrate import ensure_sqlite_columns
from app.schemas import HealthOut
from app.seed import seed_demo

app = FastAPI(
    title="data_platform Phase-0 API",
    description="Phase-0 dual wedge: OSINT + CV templates — KYB → campaign → submit → verify → credit → export",
    version="0.3.0",
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


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_columns(engine)
    db = SessionLocal()
    try:
        seed_demo(db)
    finally:
        db.close()


@app.get("/api/health", response_model=HealthOut)
def health() -> HealthOut:
    mode = settings.resolved_auth_mode()
    stubbed = [
        "kyb_status_flag_only",
        "verification_stages_1_7_heuristic",
        "fraud_synthetic_scores_stub",
        "no_redis_worker_sync_pipeline",
        "no_s3_local_exports_dir",
        "no_onchain_token",
        "cv_media_local_disk_not_s3",
        "cv_synthetic_deepfake_ml_stub",
        "allowlist_v0_founder_may_expand",
    ]
    if mode == "dev":
        stubbed.insert(0, "auth_dev_jwt_fallback_set_clerk_keys_for_prod")
    else:
        stubbed.insert(0, f"auth_clerk_mode_active")
    return HealthOut(
        status="ok",
        database=settings.database_url.split("://")[0],
        stubbed=stubbed,
    )
