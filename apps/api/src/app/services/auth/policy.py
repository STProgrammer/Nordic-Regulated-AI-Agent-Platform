"""Pure authorization rules shared by API dependencies and future services."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
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


class CaseAction(StrEnum):
    """The small Case Management action vocabulary enforced by the backend."""

    READ = "read"
    SUBMIT = "submit"
    EDIT = "edit"
    ARCHIVE = "archive"
    APPROVE_OR_REJECT = "approve_or_reject"


_CASE_ACTION_ROLES: dict[CaseAction, frozenset[RoleName]] = {
    CaseAction.READ: frozenset(
        {
            RoleName.ADMIN,
            RoleName.COMPLIANCE_REVIEWER,
            RoleName.CASE_WORKER,
            RoleName.MANAGER,
            RoleName.READ_ONLY_AUDITOR,
        }
    ),
    CaseAction.SUBMIT: frozenset({RoleName.ADMIN, RoleName.CASE_WORKER, RoleName.MANAGER}),
    CaseAction.EDIT: frozenset({RoleName.ADMIN, RoleName.CASE_WORKER, RoleName.MANAGER}),
    CaseAction.ARCHIVE: frozenset({RoleName.ADMIN, RoleName.CASE_WORKER, RoleName.MANAGER}),
    CaseAction.APPROVE_OR_REJECT: frozenset({RoleName.ADMIN, RoleName.COMPLIANCE_REVIEWER}),
}


def authorize_case_action(principal: Principal, action: CaseAction) -> None:
    """Apply the Case Management action matrix to one trusted principal."""

    ensure_roles(principal, *_CASE_ACTION_ROLES[action])


class DocumentAction(StrEnum):
    """Document actions introduced incrementally with their owning endpoints."""

    UPLOAD = "upload"
    READ = "read"
    REPROCESS = "reprocess"
    REINDEX = "reindex"
    UPDATE_SOURCE_STATUS = "update_source_status"


_DOCUMENT_ACTION_ROLES: dict[DocumentAction, frozenset[RoleName]] = {
    DocumentAction.UPLOAD: frozenset({RoleName.ADMIN, RoleName.CASE_WORKER, RoleName.MANAGER}),
    DocumentAction.READ: frozenset(
        {
            RoleName.ADMIN,
            RoleName.COMPLIANCE_REVIEWER,
            RoleName.CASE_WORKER,
            RoleName.MANAGER,
            RoleName.READ_ONLY_AUDITOR,
        }
    ),
    DocumentAction.REPROCESS: frozenset({RoleName.ADMIN, RoleName.CASE_WORKER, RoleName.MANAGER}),
    DocumentAction.REINDEX: frozenset({RoleName.ADMIN, RoleName.CASE_WORKER, RoleName.MANAGER}),
    DocumentAction.UPDATE_SOURCE_STATUS: frozenset({RoleName.ADMIN, RoleName.COMPLIANCE_REVIEWER}),
}


def authorize_document_action(principal: Principal, action: DocumentAction) -> None:
    """Apply the narrow Phase 10 document upload permission matrix."""

    ensure_roles(principal, *_DOCUMENT_ACTION_ROLES[action])


class RetrievalAction(StrEnum):
    """Retrieval actions deliberately exclude read-only audit inspection."""

    SEARCH = "search"
    ANSWER = "answer"


_RETRIEVAL_ACTION_ROLES: dict[RetrievalAction, frozenset[RoleName]] = {
    RetrievalAction.SEARCH: frozenset(
        {
            RoleName.ADMIN,
            RoleName.COMPLIANCE_REVIEWER,
            RoleName.CASE_WORKER,
            RoleName.MANAGER,
        }
    ),
    RetrievalAction.ANSWER: frozenset(
        {
            RoleName.ADMIN,
            RoleName.COMPLIANCE_REVIEWER,
            RoleName.CASE_WORKER,
            RoleName.MANAGER,
        }
    ),
}

_RESTRICTED_SOURCE_ROLES = frozenset({RoleName.ADMIN, RoleName.COMPLIANCE_REVIEWER})


def authorize_retrieval_action(principal: Principal, action: RetrievalAction) -> None:
    """Apply the narrow source-search role matrix before any content query."""

    ensure_roles(principal, *_RETRIEVAL_ACTION_ROLES[action])


def has_restricted_source_entitlement(principal: Principal) -> bool:
    """Return whether a principal may explicitly request restricted sources."""

    return not principal.roles.isdisjoint(_RESTRICTED_SOURCE_ROLES)


class AuditAction(StrEnum):
    """Read-only audit inspection; audit mutation is intentionally not an action."""

    READ = "read"


_AUDIT_ACTION_ROLES: dict[AuditAction, frozenset[RoleName]] = {
    AuditAction.READ: frozenset(
        {RoleName.ADMIN, RoleName.COMPLIANCE_REVIEWER, RoleName.READ_ONLY_AUDITOR}
    )
}


def authorize_audit_action(principal: Principal, action: AuditAction) -> None:
    """Apply the tenant-wide, read-only audit inspection role matrix."""

    ensure_roles(principal, *_AUDIT_ACTION_ROLES[action])


class MemoryAction(StrEnum):
    """Controlled memory has a deliberately Admin-only organization boundary."""

    CONFIGURE = "configure"
    INSPECT = "inspect"
    MANAGE = "manage"


def authorize_memory_action(principal: Principal, action: MemoryAction) -> None:
    """Require an active Administrator for every organization memory operation."""

    _ = action
    ensure_roles(principal, RoleName.ADMIN)


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
    ensure_roles(principal, RoleName.ADMIN, RoleName.COMPLIANCE_REVIEWER)
    if (
        approval.requires_approval or approval.risk_level.casefold() == "high"
    ) and approval.submitted_by_user_id == principal.user_id:
        raise AuthorizationDeniedError()
