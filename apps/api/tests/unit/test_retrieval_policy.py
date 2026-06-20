from __future__ import annotations

from uuid import uuid4

import pytest
from app.services.auth.policy import RetrievalAction, authorize_retrieval_action
from app.services.auth.principal import Principal, RoleName
from app.services.errors import AuthorizationDeniedError, InvalidCommandError
from app.services.retrieval.policy import resolve_source_scope


def _principal(*roles: RoleName) -> Principal:
    return Principal(
        user_id=uuid4(),
        organization_id=uuid4(),
        display_name="Synthetic retrieval user",
        preferred_language="nb",
        roles=frozenset(roles),
    )


@pytest.mark.parametrize(
    "role", [RoleName.ADMIN, RoleName.COMPLIANCE_REVIEWER, RoleName.CASE_WORKER, RoleName.MANAGER]
)
def test_operational_roles_can_search(role: RoleName) -> None:
    authorize_retrieval_action(_principal(role), RetrievalAction.SEARCH)


def test_auditor_cannot_search_and_restricted_or_archived_need_entitlement() -> None:
    auditor = _principal(RoleName.READ_ONLY_AUDITOR)
    with pytest.raises(AuthorizationDeniedError):
        authorize_retrieval_action(auditor, RetrievalAction.SEARCH)
    with pytest.raises(AuthorizationDeniedError):
        resolve_source_scope(
            _principal(RoleName.CASE_WORKER),
            requested_statuses=("restricted",),
            document_ids=(),
        )
    with pytest.raises(InvalidCommandError):
        resolve_source_scope(
            _principal(RoleName.ADMIN), requested_statuses=("archived",), document_ids=()
        )


def test_defaults_and_authorized_nonapproved_statuses_are_explicit() -> None:
    principal = _principal(RoleName.COMPLIANCE_REVIEWER)
    assert resolve_source_scope(
        principal, requested_statuses=(), document_ids=()
    ).source_statuses == ("approved",)
    scope = resolve_source_scope(
        principal,
        requested_statuses=("draft", "deprecated", "restricted", "archived"),
        document_ids=(uuid4(),),
    )
    assert scope.restricted_entitled is True
