"""Add the durable document indexing lifecycle.

Revision ID: 2f7d0bc4a8e1
Revises: d69ce722c102
Create Date: 2026-06-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "2f7d0bc4a8e1"
down_revision = "d69ce722c102"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add independent index state without altering the Phase 4 chunk indexes."""

    op.add_column(
        "documents",
        sa.Column(
            "indexing_status",
            sa.String(length=50),
            server_default=sa.text("'not_ready'"),
            nullable=False,
        ),
    )
    op.add_column("documents", sa.Column("indexing_error", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "ck_documents_indexing_status_valid",
        "documents",
        "indexing_status IN ('not_ready', 'pending', 'indexing', 'indexed', 'failed')",
    )
    op.create_index("ix_documents_indexing_status", "documents", ["indexing_status"])
    # Phase 11's parsed state is the durable eligibility contract. A corrupt
    # historical row without canonical text fails safely in the worker rather
    # than silently being skipped by the migration.
    op.execute("UPDATE documents SET indexing_status = 'pending' WHERE parsing_status = 'parsed'")


def downgrade() -> None:
    """Remove only Phase 12 lifecycle additions, preserving retrieval storage."""

    op.drop_index("ix_documents_indexing_status", table_name="documents")
    op.drop_constraint("ck_documents_indexing_status_valid", "documents", type_="check")
    op.drop_column("documents", "indexed_at")
    op.drop_column("documents", "indexing_error")
    op.drop_column("documents", "indexing_status")
