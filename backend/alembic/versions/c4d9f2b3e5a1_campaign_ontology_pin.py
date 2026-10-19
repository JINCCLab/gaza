"""campaign ontology_id + schema_version pins

Revision ID: c4d9f2b3e5a1
Revises: b3c8e1a2d4f0
Create Date: 2026-10-19 06:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4d9f2b3e5a1"
down_revision: Union[str, None] = "b3c8e1a2d4f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("campaigns", sa.Column("ontology_id", sa.String(length=64), nullable=True))
    op.add_column("campaigns", sa.Column("schema_version", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("campaigns", "schema_version")
    op.drop_column("campaigns", "ontology_id")
