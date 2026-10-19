"""initial_schema — matches app.models (Phase-0 dual wedge).

Revision ID: af27fe9a0908
Revises:
Create Date: 2026-10-19 05:45:57.781719

users ↔ organizations have a circular FK; create users first without org_id FK,
then organizations, then add users.org_id FK.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "af27fe9a0908"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "allowlist_hosts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("host", name="uq_allowlist_host"),
    )
    op.create_index("ix_allowlist_hosts_host", "allowlist_hosts", ["host"], unique=False)

    # users first (no org_id FK yet — circular with organizations.owner_user_id)
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("auth_subject", sa.String(length=255), nullable=True),
        sa.Column("org_id", sa.Integer(), nullable=True),
        sa.Column("country", sa.String(length=64), nullable=True),
        sa.Column("reputation_score", sa.Float(), nullable=False),
        sa.Column("credit_balance", sa.Float(), nullable=False),
        sa.Column("redeem_reserve", sa.Float(), nullable=False),
        sa.Column("kyc_status", sa.String(length=32), nullable=False),
        sa.Column("terms_accepted", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_auth_subject", "users", ["auth_subject"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("kyb_status", sa.String(length=32), nullable=False),
        sa.Column("intended_use", sa.Text(), nullable=True),
        sa.Column("kyb_notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_foreign_key(
        "fk_users_org_id_organizations",
        "users",
        "organizations",
        ["org_id"],
        ["id"],
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("detail_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("data_type", sa.String(length=64), nullable=False),
        sa.Column("data_class", sa.String(length=64), nullable=False),
        sa.Column("target_region", sa.String(length=128), nullable=False),
        sa.Column("requirements_json", sa.JSON(), nullable=False),
        sa.Column("synthetic_allowed", sa.Boolean(), nullable=False),
        sa.Column("target_quantity", sa.Integer(), nullable=False),
        sa.Column("unit_reward", sa.Float(), nullable=False),
        sa.Column("reward_pool", sa.Float(), nullable=False),
        sa.Column("reward_remaining", sa.Float(), nullable=False),
        sa.Column("quality_threshold", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("export_storage_key", sa.String(length=512), nullable=True),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "submissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("contributor_id", sa.Integer(), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=True),
        sa.Column("labels_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("file_hash", sa.String(length=128), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("fraud_score", sa.Float(), nullable=True),
        sa.Column("synthetic_score", sa.Float(), nullable=True),
        sa.Column("verification_status", sa.String(length=32), nullable=False),
        sa.Column("reject_reason", sa.String(length=128), nullable=True),
        sa.Column("final_reward", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.ForeignKeyConstraint(["contributor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_submissions_file_hash", "submissions", ["file_hash"], unique=False)

    op.create_table(
        "credit_ledger",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("campaign_id", sa.Integer(), nullable=True),
        sa.Column("submission_id", sa.Integer(), nullable=True),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("balance_after", sa.Float(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "verification_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("detail_json", sa.JSON(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("verification_events")
    op.drop_table("credit_ledger")
    op.drop_index("ix_submissions_file_hash", table_name="submissions")
    op.drop_table("submissions")
    op.drop_table("datasets")
    op.drop_table("campaigns")
    op.drop_table("audit_logs")
    op.drop_constraint("fk_users_org_id_organizations", "users", type_="foreignkey")
    op.drop_table("organizations")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_auth_subject", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_allowlist_hosts_host", table_name="allowlist_hosts")
    op.drop_table("allowlist_hosts")
