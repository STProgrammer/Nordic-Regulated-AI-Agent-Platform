"""Enforce one final risk assessment for each risk workflow run.

Revision ID: 7a21c9e5b406
Revises: 2f7d0bc4a8e1
Create Date: 2026-06-21
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "7a21c9e5b406"
down_revision = "2f7d0bc4a8e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Make duplicate worker delivery unable to create duplicate assessments."""

    op.create_unique_constraint(
        "uq_risk_assessments_organization_workflow_run",
        "risk_assessments",
        ["organization_id", "workflow_run_id"],
    )


def downgrade() -> None:
    """Remove only the Phase-21 idempotency constraint."""

    op.drop_constraint(
        "uq_risk_assessments_organization_workflow_run",
        "risk_assessments",
        type_="unique",
    )
