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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = f"sqlite:///{DATA_DIR / 'data_platform.db'}"
    export_dir: str = str(EXPORT_DIR)
    media_dir: str = str(MEDIA_DIR)
    platform_fee_pct: float = 0.15
    quality_mult_cap: float = 1.5
    # Phase-0 media upload limits (local disk; S3 later)
    media_max_bytes: int = 8 * 1024 * 1024
    media_allowed_types: str = "image/jpeg,image/png,image/webp,video/mp4"

    # Auth — prefer Clerk when keys are present (AUTH_MODE=auto).
    auth_mode: AuthMode = "auto"
    clerk_secret_key: Optional[str] = None
    clerk_publishable_key: Optional[str] = None
    clerk_issuer: Optional[str] = None  # e.g. https://verb-noun-00.clerk.accounts.dev
    clerk_jwks_url: Optional[str] = None  # defaults to {issuer}/.well-known/jwks.json
    # Local-only HS256 secret for AUTH_MODE=dev session tokens (never use in prod).
    dev_jwt_secret: str = "phase0-dev-jwt-secret-change-me"
    dev_jwt_ttl_seconds: int = 60 * 60 * 12

    @field_validator("clerk_secret_key", "clerk_publishable_key", "clerk_issuer", "clerk_jwks_url", mode="before")
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
