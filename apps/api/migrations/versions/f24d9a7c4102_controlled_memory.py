"""Constrain governed memory records and add content-free usage records.

Revision ID: f24d9a7c4102
Revises: c23f4a7b8d91
Create Date: 2026-06-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f24d9a7c4102"
down_revision = "c23f4a7b8d91"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add closed governance metadata without exposing a generic JSON channel."""

    op.add_column("memory_entries", sa.Column("store_key", sa.String(length=64), nullable=True))
    op.add_column("memory_entries", sa.Column("natural_key", sa.String(length=320), nullable=True))
    op.execute("UPDATE memory_entries SET store_key = id::text WHERE store_key IS NULL")
    op.execute(
        "UPDATE memory_entries SET natural_key = memory_type || ':' || id::text "
        "WHERE natural_key IS NULL"
    )
    # Earlier phases deliberately had no memory policy. Existing records are
    # retained for audit/history but made unusable until explicitly recreated
    # through this phase's closed service path.
    op.execute("UPDATE memory_entries SET is_active = false")
    op.alter_column("memory_entries", "store_key", nullable=False)
    op.alter_column("memory_entries", "natural_key", nullable=False)
    op.alter_column("memory_entries", "memory_scope", type_=sa.String(length=32))
    op.alter_column("memory_entries", "memory_type", type_=sa.String(length=64))
    op.alter_column("memory_entries", "source", type_=sa.String(length=64))
    op.create_check_constraint(
        "ck_memory_entries_scope_type_owner",
        "memory_entries",
        "NOT is_active OR ((memory_scope = 'user' AND user_id IS NOT NULL "
        "AND memory_type = 'ui_language_preference') "
        "OR (memory_scope = 'organization' AND user_id IS NULL AND memory_type IN "
        "('workflow_presentation_preference', 'approved_terminology', 'process_hint')))",
    )
    op.create_check_constraint(
        "ck_memory_entries_source_closed",
        "memory_entries",
        "NOT is_active OR source IN ('self_preference', 'admin_approved')",
    )
    op.create_index(
        "uq_memory_entries_active_natural_key",
        "memory_entries",
        ["organization_id", "memory_scope", "user_id", "natural_key"],
        unique=True,
        postgresql_where=sa.text("is_active AND archived_at IS NULL"),
    )
    op.create_index(
        "ix_memory_entries_active_presentation",
        "memory_entries",
        ["organization_id", "memory_scope", "memory_type", "updated_at"],
        unique=False,
        postgresql_where=sa.text("is_active AND archived_at IS NULL"),
    )
    op.create_table(
        "memory_usage_records",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("memory_entry_id", sa.UUID(), nullable=False),
        sa.Column("workflow_run_id", sa.UUID(), nullable=True),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "inserted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.CheckConstraint(
            "operation IN ('drafting_presentation')",
            name="ck_memory_usage_records_operation_closed",
        ),
        sa.CheckConstraint(
            "outcome IN ('applied', 'skipped', 'blocked')",
            name="ck_memory_usage_records_outcome_closed",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_memory_usage_records_organization_id_organizations",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "memory_entry_id"],
            ["memory_entries.organization_id", "memory_entries.id"],
            name="fk_memory_usage_records_organization_entry",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_run_id"],
            ["workflow_runs.id"],
            name="fk_memory_usage_records_workflow_run",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_memory_usage_records"),
    )
    op.create_index(
        "ix_memory_usage_records_organization_inserted",
        "memory_usage_records",
        ["organization_id", "inserted_at"],
        unique=False,
    )
    op.create_index(
        "ix_memory_usage_records_entry_inserted",
        "memory_usage_records",
        ["memory_entry_id", "inserted_at"],
        unique=False,
    )
    op.create_index(
        "ix_memory_usage_records_workflow_inserted",
        "memory_usage_records",
        ["workflow_run_id", "inserted_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove only Phase-24 records and return the legacy table shape."""

    op.drop_index("ix_memory_usage_records_workflow_inserted", table_name="memory_usage_records")
    op.drop_index("ix_memory_usage_records_entry_inserted", table_name="memory_usage_records")
    op.drop_index(
        "ix_memory_usage_records_organization_inserted", table_name="memory_usage_records"
    )
    op.drop_table("memory_usage_records")
    op.drop_index("ix_memory_entries_active_presentation", table_name="memory_entries")
    op.drop_index("uq_memory_entries_active_natural_key", table_name="memory_entries")
    op.drop_constraint("ck_memory_entries_source_closed", "memory_entries", type_="check")
    op.drop_constraint("ck_memory_entries_scope_type_owner", "memory_entries", type_="check")
    op.alter_column("memory_entries", "source", type_=sa.Text())
    op.alter_column("memory_entries", "memory_type", type_=sa.String(length=100))
    op.alter_column("memory_entries", "memory_scope", type_=sa.String(length=100))
    op.drop_column("memory_entries", "natural_key")
    op.drop_column("memory_entries", "store_key")
