"""Pure authorization rules shared by API dependencies and future services."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.services.auth.principal import Principal, RoleName
from app.services.errors import AuthorizationDeniedError, NotFoundError


def ensure_roles(principal: Principal, *required_roles: RoleName) -> None:
    """Require one of the supplied roles, denying by default for an empty set."""

    if not required_roles or principal.roles.isdisjoint(required_roles):
        raise AuthorizationDeniedError()


def guard_tenant_resource(principal: Principal, resource_organization_id: UUID) -> None:
    """Reject a trusted foreign-tenant resource without disclosing its existence."""

    if principal.organization_id != resource_organization_id:
        raise NotFoundError("Resource")


@dataclass(frozen=True)
class ApprovalAuthorizationInput:
    """Trusted future approval data loaded by the owning approval service."""

    organization_id: UUID
    submitted_by_user_id: UUID
    risk_level: str
    requires_approval: bool


def authorize_approval(principal: Principal, approval: ApprovalAuthorizationInput) -> None:
    """Enforce reviewer eligibility and high-risk separation of duties.

    This performs no persistence and deliberately does not expose an approval
    route; Phase 22 must supply its database-derived case input to this policy.
    """

    guard_tenant_resource(principal, approval.organization_id)
    ensure_roles(principal, RoleName.COMPLIANCE_REVIEWER)
    if (
        approval.requires_approval or approval.risk_level.casefold() == "high"
    ) and approval.submitted_by_user_id == principal.user_id:
        raise AuthorizationDeniedError()
