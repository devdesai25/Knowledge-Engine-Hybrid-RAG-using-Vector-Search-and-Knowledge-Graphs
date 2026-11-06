"""fix chunk fts generated column

Revision ID: 3abbf792aa0d
Revises: edd05e5cefa8
Create Date: 2026-09-24 01:51:35.071235

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3abbf792aa0d'
down_revision: Union[str, Sequence[str], None] = 'edd05e5cefa8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.drop_column("chunks", "fts")

    op.add_column(
        "chunks",
        sa.Column(
            "fts",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('english', content)",
                persisted=True,
            ),
            nullable=False,
        ),
    )


def downgrade():
    op.drop_column("chunks", "fts")

    op.add_column(
        "chunks",
        sa.Column(
            "fts",
            postgresql.TSVECTOR(),
            nullable=False,
        ),
    )

