"""Repair legacy case domains and enforce the public CaseDomain contract.

Revision ID: a30c6f4d9e12
Revises: e25a1c6d7f90
Create Date: 2026-06-22
"""

from __future__ import annotations

from alembic import op

revision = "a30c6f4d9e12"
down_revision = "e25a1c6d7f90"
branch_labels = None
depends_on = None

_SUPPORTED_DOMAINS = "'public_sector', 'banking', 'energy', 'internal_policy'"
_DOMAIN_REPAIR_SQL = (
    "UPDATE cases SET domain = 'internal_policy' "
    "WHERE domain NOT IN ('public_sector', 'banking', 'energy', 'internal_policy')"
)


def upgrade() -> None:
    """Map legacy synthetic values to internal policy before closing the database contract."""

    op.execute(_DOMAIN_REPAIR_SQL)
    op.create_check_constraint(
        "domain_allowed",
        "cases",
        f"domain IN ({_SUPPORTED_DOMAINS})",
    )


def downgrade() -> None:
    """Remove only the domain guard; repaired legacy rows remain valid canonical data."""

    op.drop_constraint("domain_allowed", "cases", type_="check")
