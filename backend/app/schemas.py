from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, HttpUrl


# --- Auth / identity (demo header-based) ---


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str
    role: str
    org_id: Optional[int] = None
    credit_balance: float
    redeem_reserve: float
    reputation_score: float
    kyc_status: str
    terms_accepted: bool
    status: str

    model_config = {"from_attributes": True}


class OrgOut(BaseModel):
    id: int
    name: str
    owner_user_id: int
    kyb_status: str
    intended_use: Optional[str] = None
    kyb_notes: Optional[str] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class OrgCreate(BaseModel):
    name: str
    intended_use: str


class KybDecision(BaseModel):
    approve: bool
    notes: Optional[str] = None


# --- Campaign ---


class CampaignCreate(BaseModel):
    title: str
    description: str = ""
    data_type: str = "osint_label"
    data_class: str = "structured_osint"
    target_region: str = "en_us_asia"
    requirements_json: dict[str, Any] = Field(
        default_factory=lambda: {
            "event_types": ["military_exercise", "equipment_display", "official_briefing"],
            "location_granularity": "public_city_region",
            "equipment_types": ["aircraft", "naval", "ground", "unknown"],
            "label_guide_en": "Tag public open-source items only. Use public city/region location. Include source URL from allowlisted hosts.",
        }
    )
    synthetic_allowed: bool = False
    target_quantity: int = 10
    unit_reward: float = 10.0
    pool_fund_amount: float = 200.0


class CampaignOut(BaseModel):
    id: int
    organization_id: int
    title: str
    description: str
    data_type: str
    data_class: str
    target_region: str
    requirements_json: dict[str, Any]
    synthetic_allowed: bool
    target_quantity: int
    unit_reward: float
    reward_pool: float
    reward_remaining: float
    quality_threshold: float
    status: str
    admin_notes: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CampaignDecision(BaseModel):
    approve: bool
    notes: Optional[str] = None


# --- Submission ---


class OsintLabels(BaseModel):
    event_type: str
    location_public: str
    event_time: str
    equipment_type: str
    notes: Optional[str] = None


class SubmissionCreate(BaseModel):
    campaign_id: int
    source_url: str
    labels: OsintLabels
    claimed_capture_time: Optional[str] = None
    license_claim: str = "public_reporting_fair_use_claim"


class SubmissionOut(BaseModel):
    id: int
    campaign_id: int
    contributor_id: int
    source_url: str
    labels_json: dict[str, Any]
    metadata_json: dict[str, Any]
    file_hash: Optional[str] = None
    quality_score: Optional[float] = None
    fraud_score: Optional[float] = None
    synthetic_score: Optional[float] = None
    verification_status: str
    reject_reason: Optional[str] = None
    final_reward: Optional[float] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewDecision(BaseModel):
    accept: bool
    reason_code: Optional[str] = None
    quality_mult: float = 1.0
    internal_memo_ko: Optional[str] = None


class VerificationEventOut(BaseModel):
    id: int
    submission_id: int
    stage: str
    result: str
    detail_json: dict[str, Any]
    actor_id: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Credits / Dataset / Allowlist ---


class LedgerOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    organization_id: Optional[int] = None
    campaign_id: Optional[int] = None
    submission_id: Optional[int] = None
    type: str
    amount: float
    balance_after: Optional[float] = None
    note: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DatasetOut(BaseModel):
    id: int
    campaign_id: int
    organization_id: int
    version: int
    item_count: int
    export_storage_key: Optional[str] = None
    manifest_json: dict[str, Any]
    created_at: datetime
    download_url: Optional[str] = None

    model_config = {"from_attributes": True}


class AllowlistHostOut(BaseModel):
    id: int
    host: str
    category: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AllowlistHostCreate(BaseModel):
    host: str
    category: str = "admin_added"


class HealthOut(BaseModel):
    status: str
    database: str
    stubbed: list[str]
