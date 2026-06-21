"""Make evaluation datasets and runs safely addressable and idempotent.

Revision ID: e25a1c6d7f90
Revises: f24d9a7c4102
Create Date: 2026-06-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e25a1c6d7f90"
down_revision = "f24d9a7c4102"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add durable logical identities without discarding historical synthetic rows."""

    op.add_column("eval_datasets", sa.Column("dataset_key", sa.String(length=64), nullable=True))
    op.add_column("eval_datasets", sa.Column("content_hash", sa.String(length=64), nullable=True))
    op.execute(
        "UPDATE eval_datasets SET dataset_key = 'legacy_' || replace(id::text, '-', ''), "
        "content_hash = repeat('0', 64) WHERE dataset_key IS NULL OR content_hash IS NULL"
    )
    op.alter_column("eval_datasets", "dataset_key", nullable=False)
    op.alter_column("eval_datasets", "content_hash", nullable=False)
    op.alter_column("eval_datasets", "dataset_key", server_default=sa.text("'legacy'"))
    op.alter_column("eval_datasets", "content_hash", server_default=sa.text("repeat('0', 64)"))
    op.create_check_constraint(
        "ck_eval_datasets_global_only", "eval_datasets", "organization_id IS NULL"
    )
    op.create_unique_constraint(
        "uq_eval_datasets_dataset_key_version",
        "eval_datasets",
        ["dataset_key", "dataset_version"],
    )

    op.add_column("eval_cases", sa.Column("case_key", sa.String(length=64), nullable=True))
    op.execute(
        "UPDATE eval_cases SET case_key = 'legacy_' || replace(id::text, '-', '') "
        "WHERE case_key IS NULL"
    )
    op.alter_column("eval_cases", "case_key", nullable=False)
    op.alter_column("eval_cases", "case_key", server_default=sa.text("'legacy'"))
    op.create_unique_constraint(
        "uq_eval_cases_dataset_case_key", "eval_cases", ["eval_dataset_id", "case_key"]
    )
    op.create_index(
        "ix_eval_cases_dataset_case_key",
        "eval_cases",
        ["eval_dataset_id", "case_key"],
        unique=False,
    )

    op.add_column("eval_runs", sa.Column("dataset_version", sa.String(length=100), nullable=True))
    op.add_column(
        "eval_runs", sa.Column("dataset_content_hash", sa.String(length=64), nullable=True)
    )
    op.execute(
        "UPDATE eval_runs AS run SET dataset_version = dataset.dataset_version, "
        "dataset_content_hash = dataset.content_hash FROM eval_datasets AS dataset "
        "WHERE run.eval_dataset_id = dataset.id "
        "AND (run.dataset_version IS NULL OR run.dataset_content_hash IS NULL)"
    )
    op.alter_column("eval_runs", "dataset_version", nullable=False)
    op.alter_column("eval_runs", "dataset_content_hash", nullable=False)
    op.alter_column("eval_runs", "dataset_version", server_default=sa.text("'legacy'"))
    op.alter_column("eval_runs", "dataset_content_hash", server_default=sa.text("repeat('0', 64)"))
    op.create_check_constraint(
        "ck_eval_runs_status", "eval_runs", "status IN ('queued', 'running', 'completed', 'failed')"
    )
    op.create_check_constraint(
        "ck_eval_runs_pass_fail", "eval_runs", "pass_fail IN ('pending', 'pass', 'fail')"
    )
    op.create_index(
        "uq_eval_runs_active_organization_dataset",
        "eval_runs",
        ["organization_id", "eval_dataset_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
    op.create_index(
        "ix_eval_runs_organization_started",
        "eval_runs",
        ["organization_id", "started_at"],
        unique=False,
    )

    op.add_column("eval_results", sa.Column("risk_score", sa.Numeric(12, 8), nullable=True))
    op.add_column("eval_results", sa.Column("routing_score", sa.Numeric(12, 8), nullable=True))
    op.create_unique_constraint(
        "uq_eval_results_run_case", "eval_results", ["eval_run_id", "eval_case_id"]
    )
    op.create_check_constraint(
        "ck_eval_results_risk_score_range",
        "eval_results",
        "risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 1)",
    )
    op.create_check_constraint(
        "ck_eval_results_routing_score_range",
        "eval_results",
        "routing_score IS NULL OR (routing_score >= 0 AND routing_score <= 1)",
    )


def downgrade() -> None:
    """Remove Phase-25 runner identity and metric reinforcement only."""

    op.drop_constraint("ck_eval_results_routing_score_range", "eval_results", type_="check")
    op.drop_constraint("ck_eval_results_risk_score_range", "eval_results", type_="check")
    op.drop_constraint("uq_eval_results_run_case", "eval_results", type_="unique")
    op.drop_column("eval_results", "routing_score")
    op.drop_column("eval_results", "risk_score")
    op.drop_index("ix_eval_runs_organization_started", table_name="eval_runs")
    op.drop_index("uq_eval_runs_active_organization_dataset", table_name="eval_runs")
    op.drop_constraint("ck_eval_runs_pass_fail", "eval_runs", type_="check")
    op.drop_constraint("ck_eval_runs_status", "eval_runs", type_="check")
    op.drop_column("eval_runs", "dataset_content_hash")
    op.drop_column("eval_runs", "dataset_version")
    op.drop_index("ix_eval_cases_dataset_case_key", table_name="eval_cases")
    op.drop_constraint("uq_eval_cases_dataset_case_key", "eval_cases", type_="unique")
    op.drop_column("eval_cases", "case_key")
    op.drop_constraint("uq_eval_datasets_dataset_key_version", "eval_datasets", type_="unique")
    op.drop_constraint("ck_eval_datasets_global_only", "eval_datasets", type_="check")
    op.drop_column("eval_datasets", "content_hash")
    op.drop_column("eval_datasets", "dataset_key")
