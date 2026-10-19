"""kyb document stub columns on organizations

Revision ID: b3c8e1a2d4f0
Revises: af27fe9a0908
Create Date: 2026-10-19 06:05:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3c8e1a2d4f0"
down_revision: Union[str, None] = "af27fe9a0908"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("kyb_legal_name", sa.String(length=255), nullable=True))
    op.add_column(
        "organizations", sa.Column("kyb_registration_id", sa.String(length=128), nullable=True)
    )
    op.add_column(
        "organizations", sa.Column("kyb_document_url", sa.String(length=1024), nullable=True)
    )
    op.add_column(
        "organizations",
        sa.Column("kyb_document_storage_key", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "organizations", sa.Column("kyb_document_filename", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "organizations",
        sa.Column("kyb_document_content_type", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "organizations", sa.Column("kyb_packet_submitted_at", sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("organizations", "kyb_packet_submitted_at")
    op.drop_column("organizations", "kyb_document_content_type")
    op.drop_column("organizations", "kyb_document_filename")
    op.drop_column("organizations", "kyb_document_storage_key")
    op.drop_column("organizations", "kyb_document_url")
    op.drop_column("organizations", "kyb_registration_id")
    op.drop_column("organizations", "kyb_legal_name")
