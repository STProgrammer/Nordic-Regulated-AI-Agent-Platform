"""Add durable pending-review lifecycle fields to the approvals placeholder.

Revision ID: b83a4f9d0e17
Revises: 7a21c9e5b406
Create Date: 2026-06-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b83a4f9d0e17"
down_revision = "7a21c9e5b406"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Evolve historical decision rows without fabricating a reviewer for pending work."""

    op.add_column(
        "approvals",
        sa.Column("status", sa.String(length=50), nullable=True, server_default="pending"),
    )
    op.add_column("approvals", sa.Column("assigned_user_id", sa.UUID(), nullable=True))
    op.add_column("approvals", sa.Column("drafting_workflow_run_id", sa.UUID(), nullable=True))
    op.add_column("approvals", sa.Column("risk_assessment_id", sa.UUID(), nullable=True))
    op.add_column(
        "approvals", sa.Column("interrupted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("approvals", sa.Column("resumed_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        """
        UPDATE approvals
        SET
            status = CASE decision
                WHEN 'approve' THEN 'approved'
                WHEN 'edit_and_approve' THEN 'approved'
                WHEN 'approved' THEN 'approved'
                WHEN 'reject' THEN 'rejected'
                WHEN 'rejected' THEN 'rejected'
                WHEN 'request_more_evidence' THEN 'needs_more_evidence'
                WHEN 'needs_more_evidence' THEN 'needs_more_evidence'
                ELSE 'needs_more_evidence'
            END,
            decision = CASE decision
                WHEN 'approve' THEN 'approve'
                WHEN 'edit_and_approve' THEN 'edit_and_approve'
                WHEN 'approved' THEN 'approve'
                WHEN 'reject' THEN 'reject'
                WHEN 'rejected' THEN 'reject'
                WHEN 'request_more_evidence' THEN 'request_more_evidence'
                WHEN 'needs_more_evidence' THEN 'request_more_evidence'
                -- The old placeholder accepted free-form values. A migration cannot
                -- safely infer a final outcome, so preserve the record as the
                -- closed, non-final needs-more-evidence outcome.
                ELSE 'request_more_evidence'
            END
        """
    )
    op.alter_column("approvals", "status", nullable=False, server_default="pending")
    op.alter_column("approvals", "reviewer_user_id", nullable=True)
    op.alter_column("approvals", "decision", nullable=True)
    op.alter_column("approvals", "decision_at", nullable=True)
    op.create_foreign_key(
        "fk_approvals_organization_assigned_user",
        "approvals",
        "users",
        ["organization_id", "assigned_user_id"],
        ["organization_id", "id"],
    )
    op.create_foreign_key(
        "fk_approvals_organization_drafting_workflow_run",
        "approvals",
        "workflow_runs",
        ["organization_id", "drafting_workflow_run_id"],
        ["organization_id", "id"],
    )
    op.create_foreign_key(
        "fk_approvals_risk_assessment_id",
        "approvals",
        "risk_assessments",
        ["risk_assessment_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_approvals_organization_workflow_run",
        "approvals",
        ["organization_id", "workflow_run_id"],
    )
    op.create_check_constraint(
        "approval_status_valid",
        "approvals",
        "status IN ('pending', 'assigned', 'approved', 'rejected', 'needs_more_evidence')",
    )
    op.create_check_constraint(
        "approval_decision_valid",
        "approvals",
        "decision IS NULL OR decision IN "
        "('approve', 'edit_and_approve', 'reject', 'request_more_evidence')",
    )
    op.create_index(
        "ix_approvals_organization_status_assigned_inserted",
        "approvals",
        ["organization_id", "status", "assigned_user_id", "inserted_at"],
        unique=False,
    )
    op.create_index(
        "uq_approvals_one_active_case",
        "approvals",
        ["organization_id", "case_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'assigned')"),
    )


def downgrade() -> None:
    """Remove only the Phase-22 review-lifecycle additions."""

    op.drop_index("uq_approvals_one_active_case", table_name="approvals")
    op.drop_index("ix_approvals_organization_status_assigned_inserted", table_name="approvals")
    op.drop_constraint("approval_decision_valid", "approvals", type_="check")
    op.drop_constraint("approval_status_valid", "approvals", type_="check")
    op.drop_constraint("uq_approvals_organization_workflow_run", "approvals", type_="unique")
    op.drop_constraint("fk_approvals_risk_assessment_id", "approvals", type_="foreignkey")
    op.drop_constraint(
        "fk_approvals_organization_drafting_workflow_run", "approvals", type_="foreignkey"
    )
    op.drop_constraint("fk_approvals_organization_assigned_user", "approvals", type_="foreignkey")
    op.alter_column("approvals", "decision_at", nullable=False)
    op.alter_column("approvals", "decision", nullable=False)
    op.alter_column("approvals", "reviewer_user_id", nullable=False)
    op.drop_column("approvals", "resumed_at")
    op.drop_column("approvals", "interrupted_at")
    op.drop_column("approvals", "risk_assessment_id")
    op.drop_column("approvals", "drafting_workflow_run_id")
    op.drop_column("approvals", "assigned_user_id")
    op.drop_column("approvals", "status")
