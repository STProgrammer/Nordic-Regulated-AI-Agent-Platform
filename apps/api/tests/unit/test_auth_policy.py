from __future__ import annotations

from uuid import uuid4

import pytest
from app.services.auth.policy import (
    ApprovalAuthorizationInput,
    CaseAction,
    DocumentAction,
    RetrievalAction,
    authorize_approval,
    authorize_case_action,
    authorize_document_action,
    authorize_retrieval_action,
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


def test_case_action_policy_keeps_read_only_auditors_read_only() -> None:
    auditor = _principal(RoleName.READ_ONLY_AUDITOR)
    authorize_case_action(auditor, CaseAction.READ)
    with pytest.raises(AuthorizationDeniedError):
        authorize_case_action(auditor, CaseAction.SUBMIT)


def test_case_approval_transition_can_be_performed_by_a_reviewer() -> None:
    authorize_case_action(_principal(RoleName.COMPLIANCE_REVIEWER), CaseAction.APPROVE_OR_REJECT)


@pytest.mark.parametrize(
    "role",
    [RoleName.ADMIN, RoleName.COMPLIANCE_REVIEWER, RoleName.CASE_WORKER, RoleName.MANAGER],
)
def test_rag_answer_matches_the_permitted_retrieval_role_matrix(role: RoleName) -> None:
    authorize_retrieval_action(_principal(role), RetrievalAction.ANSWER)


def test_read_only_auditor_cannot_generate_rag_answers() -> None:
    with pytest.raises(AuthorizationDeniedError):
        authorize_retrieval_action(_principal(RoleName.READ_ONLY_AUDITOR), RetrievalAction.ANSWER)


@pytest.mark.parametrize("role", [RoleName.ADMIN, RoleName.CASE_WORKER, RoleName.MANAGER])
def test_document_upload_is_allowed_for_minimum_case_submission_roles(role: RoleName) -> None:
    authorize_document_action(_principal(role), DocumentAction.UPLOAD)


@pytest.mark.parametrize("role", [RoleName.COMPLIANCE_REVIEWER, RoleName.READ_ONLY_AUDITOR])
def test_document_upload_is_denied_for_non_upload_roles(role: RoleName) -> None:
    with pytest.raises(AuthorizationDeniedError):
        authorize_document_action(_principal(role), DocumentAction.UPLOAD)


@pytest.mark.parametrize("role", list(RoleName))
def test_document_read_matches_case_read_role_matrix(role: RoleName) -> None:
    authorize_document_action(_principal(role), DocumentAction.READ)


@pytest.mark.parametrize("role", [RoleName.ADMIN, RoleName.CASE_WORKER, RoleName.MANAGER])
def test_document_reprocess_is_limited_to_upload_roles(role: RoleName) -> None:
    authorize_document_action(_principal(role), DocumentAction.REPROCESS)


@pytest.mark.parametrize("role", [RoleName.COMPLIANCE_REVIEWER, RoleName.READ_ONLY_AUDITOR])
def test_document_reprocess_denies_non_owner_roles(role: RoleName) -> None:
    with pytest.raises(AuthorizationDeniedError):
        authorize_document_action(_principal(role), DocumentAction.REPROCESS)


@pytest.mark.parametrize("role", [RoleName.ADMIN, RoleName.CASE_WORKER, RoleName.MANAGER])
def test_document_reindex_is_limited_to_mutating_document_roles(role: RoleName) -> None:
    authorize_document_action(_principal(role), DocumentAction.REINDEX)


@pytest.mark.parametrize("role", [RoleName.COMPLIANCE_REVIEWER, RoleName.READ_ONLY_AUDITOR])
def test_document_reindex_denies_read_only_roles(role: RoleName) -> None:
    with pytest.raises(AuthorizationDeniedError):
        authorize_document_action(_principal(role), DocumentAction.REINDEX)


@pytest.mark.parametrize("role", [RoleName.ADMIN, RoleName.COMPLIANCE_REVIEWER])
def test_document_source_status_governance_is_limited_to_authorized_roles(role: RoleName) -> None:
    authorize_document_action(_principal(role), DocumentAction.UPDATE_SOURCE_STATUS)


@pytest.mark.parametrize(
    "role", [RoleName.CASE_WORKER, RoleName.MANAGER, RoleName.READ_ONLY_AUDITOR]
)
def test_document_source_status_governance_denies_non_governance_roles(role: RoleName) -> None:
    with pytest.raises(AuthorizationDeniedError):
        authorize_document_action(_principal(role), DocumentAction.UPDATE_SOURCE_STATUS)
