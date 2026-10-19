from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32))  # contributor | buyer | admin
    # IdP subject: Clerk user id, or "dev:<email>" for local sessions
    auth_subject: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    org_id: Mapped[Optional[int]] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reputation_score: Mapped[float] = mapped_column(Float, default=0.0)
    credit_balance: Mapped[float] = mapped_column(Float, default=0.0)
    redeem_reserve: Mapped[float] = mapped_column(Float, default=0.0)
    kyc_status: Mapped[str] = mapped_column(String(32), default="not_required")
    terms_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    organization: Mapped[Optional["Organization"]] = relationship(
        back_populates="members", foreign_keys=[org_id]
    )
    submissions: Mapped[list["Submission"]] = relationship(back_populates="contributor")
    ledger_entries: Mapped[list["CreditLedger"]] = relationship(back_populates="user")


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    kyb_status: Mapped[str] = mapped_column(String(32), default="pending")  # pending|approved|rejected
    intended_use: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    kyb_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    members: Mapped[list[User]] = relationship(
        back_populates="organization", foreign_keys=[User.org_id]
    )
    campaigns: Mapped[list["Campaign"]] = relationship(back_populates="organization")


class AllowlistHost(Base):
    __tablename__ = "allowlist_hosts"
    __table_args__ = (UniqueConstraint("host", name="uq_allowlist_host"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    host: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[str] = mapped_column(String(128), default="admin_added")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    data_type: Mapped[str] = mapped_column(String(64), default="osint_label")
    data_class: Mapped[str] = mapped_column(String(64), default="structured_osint")
    target_region: Mapped[str] = mapped_column(String(128), default="en_us_asia")
    requirements_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    synthetic_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    target_quantity: Mapped[int] = mapped_column(Integer, default=10)
    unit_reward: Mapped[float] = mapped_column(Float, default=10.0)
    reward_pool: Mapped[float] = mapped_column(Float, default=0.0)
    reward_remaining: Mapped[float] = mapped_column(Float, default=0.0)
    quality_threshold: Mapped[float] = mapped_column(Float, default=0.7)
    status: Mapped[str] = mapped_column(
        String(32), default="draft"
    )  # draft|pending_review|active|paused|closed|rejected
    admin_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    organization: Mapped[Organization] = relationship(back_populates="campaigns")
    submissions: Mapped[list["Submission"]] = relationship(back_populates="campaign")
    datasets: Mapped[list["Dataset"]] = relationship(back_populates="campaign")


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"))
    contributor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    source_url: Mapped[str] = mapped_column(String(1024), default="")
    # Local media path key for CV uploads (relative under data/media/)
    storage_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    labels_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    file_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fraud_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    synthetic_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    verification_status: Mapped[str] = mapped_column(
        String(32), default="submitted"
    )  # submitted|in_review|needs_review|accepted|rejected
    reject_reason: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    final_reward: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    campaign: Mapped[Campaign] = relationship(back_populates="submissions")
    contributor: Mapped[User] = relationship(back_populates="submissions")
    verification_events: Mapped[list["VerificationEvent"]] = relationship(
        back_populates="submission"
    )


class VerificationEvent(Base):
    __tablename__ = "verification_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"))
    stage: Mapped[str] = mapped_column(String(64))
    result: Mapped[str] = mapped_column(String(32))  # pass|fail|flag|needs_review|accepted|rejected
    detail_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    submission: Mapped[Submission] = relationship(back_populates="verification_events")


class CreditLedger(Base):
    __tablename__ = "credit_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    organization_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    campaign_id: Mapped[Optional[int]] = mapped_column(ForeignKey("campaigns.id"), nullable=True)
    submission_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("submissions.id"), nullable=True
    )
    type: Mapped[str] = mapped_column(
        String(32)
    )  # pool_fund|reward|clawback|adjustment|redeem_reserve|fee
    amount: Mapped[float] = mapped_column(Float)
    balance_after: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    user: Mapped[Optional[User]] = relationship(back_populates="ledger_entries")


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"))
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    export_storage_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    campaign: Mapped[Campaign] = relationship(back_populates="datasets")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(128))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    detail_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
