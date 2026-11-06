"""updated chunk.fts column

Revision ID: edd05e5cefa8
Revises: 8b1aa3c307ba
Create Date: 2026-09-22 03:09:09.298737

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'edd05e5cefa8'
down_revision: Union[str, Sequence[str], None] = '8b1aa3c307ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.alter_column(
        "chunks",
        "fts",
        existing_type=postgresql.TSVECTOR(),
        computed=sa.Computed(
            "to_tsvector('english', content)",
            persisted=True,
        ),
    )


def downgrade():
    op.alter_column(
        "chunks",
        "fts",
        existing_type=postgresql.TSVECTOR(),
        computed=None,
    )