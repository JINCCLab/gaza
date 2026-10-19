from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# --- Auth / identity (Bearer JWT — Clerk or local dev) ---


class UserOut(BaseModel):
    id: int
    email: str
    display_name: str
    role: str
    auth_subject: Optional[str] = None
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
    # KYB document stub packet (Phase-0; no vendor verification)
    kyb_legal_name: Optional[str] = None
    kyb_registration_id: Optional[str] = None
    kyb_document_url: Optional[str] = None
    kyb_document_storage_key: Optional[str] = None
    kyb_document_filename: Optional[str] = None
    kyb_document_content_type: Optional[str] = None
    kyb_packet_submitted_at: Optional[datetime] = None
    kyb_packet_ready: bool = False
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class OrgCreate(BaseModel):
    name: str
    intended_use: str


class KybPacketSubmit(BaseModel):
    """Buyer KYB stub: company metadata + optional file URL and/or prior upload storage_key."""

    legal_name: str
    registration_id: str
    document_url: Optional[str] = None
    storage_key: Optional[str] = None
    filename: Optional[str] = None
    content_type: Optional[str] = None


class KybDocumentUploadOut(BaseModel):
    storage_key: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str


class KybDecision(BaseModel):
    approve: bool
    # Admin internal memo (KO OK)
    notes: Optional[str] = None


# --- Campaign ---


class CampaignCreate(BaseModel):
    title: str
    description: str = ""
    # osint_label | cv_media (aliases: osint_labels, cv)
    data_type: str = "osint_label"
    data_class: str = "structured_osint"
    target_region: str = "en_us_asia"
    # Empty → server fills template defaults for the chosen data_type
    requirements_json: Dict[str, Any] = Field(default_factory=dict)
    # Phase-0 CV default false (real scenes only unless Admin later enables)
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
    requirements_json: Dict[str, Any]
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


class BBox(BaseModel):
    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)
    w: float = Field(..., ge=0.0, le=1.0)
    h: float = Field(..., ge=0.0, le=1.0)
    label: Optional[str] = None


class CvAnnotation(BaseModel):
    category: str
    caption: str
    bboxes: List[BBox] = Field(default_factory=list)


class SubmissionCreate(BaseModel):
    campaign_id: int
    # OSINT: required allowlisted URL. CV: media URL and/or storage_key from upload.
    source_url: Optional[str] = ""
    storage_key: Optional[str] = None
    labels: Optional[OsintLabels] = None
    annotation: Optional[CvAnnotation] = None
    claimed_capture_time: Optional[str] = None
    license_claim: str = "public_reporting_fair_use_claim"
    content_type: Optional[str] = None
    sha256: Optional[str] = None
    # Contributor-declared; rejected when campaign.synthetic_allowed is false
    claims_synthetic: bool = False


class SubmissionOut(BaseModel):
    id: int
    campaign_id: int
    contributor_id: int
    source_url: str
    storage_key: Optional[str] = None
    labels_json: Dict[str, Any]
    metadata_json: Dict[str, Any]
    file_hash: Optional[str] = None
    quality_score: Optional[float] = None
    fraud_score: Optional[float] = None
    synthetic_score: Optional[float] = None
    verification_status: str
    reject_reason: Optional[str] = None
    final_reward: Optional[float] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MediaUploadOut(BaseModel):
    storage_key: str
    content_type: str
    size_bytes: int
    sha256: str
    media_url: str


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
    detail_json: Dict[str, Any]
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
    manifest_json: Dict[str, Any]
    created_at: datetime
    download_url: Optional[str] = None
    # Present when STORAGE_BACKEND=s3 (or auto+creds); short-lived GET URL.
    # Prefer /download proxy for auth-gated access; use ?redirect=1 to 302.
    presigned_url: Optional[str] = None

    model_config = {"from_attributes": True}


class AllowlistHostOut(BaseModel):
    id: int
    host: str
    category: str
    enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AllowlistHostCreate(BaseModel):
    host: str
    category: str = "admin_added"


class AllowlistHostUpdate(BaseModel):
    enabled: Optional[bool] = None
    category: Optional[str] = None


class HealthOut(BaseModel):
    status: str
    database: str
    stubbed: List[str]
    verify_mode: str = "sync"
    verify_path: str = "sync"
    redis: str = "unset"
    storage_backend: str = "local"
    storage: str = "ok"


# --- Admin analytics (Phase-0 founder ops) ---


class CountByKey(BaseModel):
    key: str
    count: int


class FunnelRates(BaseModel):
    accepted: int
    rejected: int
    needs_review: int
    pending_verify: int
    decided: int
    accept_rate: Optional[float] = None
    reject_rate: Optional[float] = None


class CreditsSummary(BaseModel):
    rewards_granted_total: float
    reward_entries: int
    pool_funded_total: float
    contributor_balances_total: float


class CampaignAnalyticsRow(BaseModel):
    campaign_id: int
    title: str
    data_type: str
    status: str
    submissions_total: int
    accepted: int
    rejected: int
    needs_review: int
    reward_pool: float
    reward_remaining: float
    credits_granted: float


class AdminAnalyticsOut(BaseModel):
    campaigns_total: int
    campaigns_by_status: List[CountByKey]
    submissions_total: int
    submissions_by_status: List[CountByKey]
    funnel: FunnelRates
    reject_reasons: List[CountByKey]
    credits: CreditsSummary
    orgs_by_kyb: List[CountByKey]
    per_campaign: List[CampaignAnalyticsRow]
