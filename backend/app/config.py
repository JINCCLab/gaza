from pathlib import Path
from typing import Literal, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
EXPORT_DIR = ROOT / "exports"
MEDIA_DIR = DATA_DIR / "media"
DATA_DIR.mkdir(parents=True, exist_ok=True)
EXPORT_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

AuthMode = Literal["auto", "clerk", "dev"]
VerifyMode = Literal["auto", "sync", "async"]
StorageBackend = Literal["auto", "local", "s3"]
UrlReachabilityMode = Literal["auto", "on", "off"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Unset / default → SQLite file under ./data. Set DATABASE_URL for Postgres
    # (e.g. postgresql+psycopg://dataplat:dataplat@127.0.0.1:5432/data_platform).
    database_url: str = f"sqlite:///{DATA_DIR / 'data_platform.db'}"
    export_dir: str = str(EXPORT_DIR)
    media_dir: str = str(MEDIA_DIR)
    platform_fee_pct: float = 0.15
    quality_mult_cap: float = 1.5
    # Phase-0 media upload limits
    media_max_bytes: int = 8 * 1024 * 1024
    media_allowed_types: str = "image/jpeg,image/png,image/webp,video/mp4"

    # Object storage — local filesystem default; S3-compatible when configured.
    # auto: s3 when S3_BUCKET + access/secret keys set, else local.
    storage_backend: StorageBackend = "auto"
    s3_endpoint_url: Optional[str] = None  # MinIO e.g. http://127.0.0.1:9000
    s3_region: str = "us-east-1"
    s3_access_key_id: Optional[str] = None
    s3_secret_access_key: Optional[str] = None
    s3_bucket: Optional[str] = None
    s3_media_prefix: str = "media/"
    s3_exports_prefix: str = "exports/"
    s3_presign_ttl_seconds: int = 3600

    # Verification — sync blocks the request; async enqueues to Redis worker.
    # auto: async when REDIS_URL is reachable, else sync. VERIFY_MODE=sync forces inline.
    verify_mode: VerifyMode = "auto"
    redis_url: Optional[str] = None  # e.g. redis://127.0.0.1:6379/0
    verify_queue_key: str = "verify:jobs"

    # URL reachability stub (HEAD/short GET; no page scrape). auto/on attempt probe;
    # unreachable → reject. off skips (local offline smoke).
    url_reachability: UrlReachabilityMode = "auto"
    url_reachability_timeout_s: float = 2.0
    # When true, DNS/timeout rejects; when false, only flags metadata (still used if mode=on).
    url_reachability_strict: bool = True

    # Dual-annotator sample (manual review quality). Keep lean — not a labeling workforce.
    # Rate: probability [0,1] that a submission routed to needs_review also requires 2nd accept.
    # First N: force dual on the first N needs_review outcomes per campaign (0 = disabled).
    dual_annotate_rate: float = 0.0
    dual_annotate_first_n: int = 0

    # Auth — prefer Clerk when keys are present (AUTH_MODE=auto).
    auth_mode: AuthMode = "auto"
    clerk_secret_key: Optional[str] = None
    clerk_publishable_key: Optional[str] = None
    clerk_issuer: Optional[str] = None  # e.g. https://verb-noun-00.clerk.accounts.dev
    clerk_jwks_url: Optional[str] = None  # defaults to {issuer}/.well-known/jwks.json
    # Local-only HS256 secret for AUTH_MODE=dev session tokens (never use in prod).
    dev_jwt_secret: str = "phase0-dev-jwt-secret-change-me"
    dev_jwt_ttl_seconds: int = 60 * 60 * 12

    @field_validator(
        "clerk_secret_key",
        "clerk_publishable_key",
        "clerk_issuer",
        "clerk_jwks_url",
        "redis_url",
        "s3_endpoint_url",
        "s3_access_key_id",
        "s3_secret_access_key",
        "s3_bucket",
        mode="before",
    )
    @classmethod
    def empty_str_to_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    def resolved_auth_mode(self) -> Literal["clerk", "dev"]:
        """Effective auth backend after applying AUTH_MODE=auto."""
        if self.auth_mode == "clerk":
            return "clerk"
        if self.auth_mode == "dev":
            return "dev"
        # auto
        if self.clerk_secret_key and (self.clerk_issuer or self.clerk_jwks_url):
            return "clerk"
        return "dev"

    def clerk_jwks_endpoint(self) -> Optional[str]:
        if self.clerk_jwks_url:
            return self.clerk_jwks_url
        if self.clerk_issuer:
            return f"{self.clerk_issuer.rstrip('/')}/.well-known/jwks.json"
        return None


settings = Settings()
