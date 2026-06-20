from __future__ import annotations

from uuid import uuid4

import pytest
from app.services.auth.policy import (
    ApprovalAuthorizationInput,
    authorize_approval,
    ensure_roles,
    guard_tenant_resource,
)
from app.services.auth.principal import Principal, RoleName
from app.services.errors import AuthorizationDeniedError, NotFoundError


def _principal(*roles: RoleName) -> Principal:
    return Principal(
        user_id=uuid4(),
        organization_id=uuid4(),
        display_name="Synthetic Principal",
        preferred_language="nb",
        roles=frozenset(roles),
    )


def test_no_role_is_denied_by_default() -> None:
    with pytest.raises(AuthorizationDeniedError):
        ensure_roles(_principal(), RoleName.ADMIN)


def test_tenant_guard_hides_foreign_resource() -> None:
    with pytest.raises(NotFoundError):
        guard_tenant_resource(_principal(RoleName.ADMIN), uuid4())


def test_high_risk_submitter_cannot_approve_own_case() -> None:
    principal = _principal(RoleName.COMPLIANCE_REVIEWER, RoleName.CASE_WORKER)
    with pytest.raises(AuthorizationDeniedError):
        authorize_approval(
            principal,
            ApprovalAuthorizationInput(
                organization_id=principal.organization_id,
                submitted_by_user_id=principal.user_id,
                risk_level="high",
                requires_approval=True,
            ),
        )


def test_reviewer_can_approve_other_same_tenant_high_risk_case() -> None:
    principal = _principal(RoleName.COMPLIANCE_REVIEWER)
    authorize_approval(
        principal,
        ApprovalAuthorizationInput(
            organization_id=principal.organization_id,
            submitted_by_user_id=uuid4(),
            risk_level="high",
            requires_approval=True,
        ),
    )
