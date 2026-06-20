"""Transport contract tests for governed Phase 13 retrieval search."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.api.dependencies import get_authentication_service, get_retrieval_service
from app.core.config import AppSettings
from app.main import create_api_app
from app.services.auth.policy import RetrievalAction, authorize_retrieval_action
from app.services.auth.principal import Principal, RoleName
from app.services.errors import AuthorizationDeniedError, NotFoundError
from app.services.retrieval.types import (
    RetrievalMethod,
    RetrievalRequest,
    RetrievalWarningCode,
    RetrievedSource,
)
from fastapi.testclient import TestClient

_SESSION_ID = "synthetic_retrieval_session_012345678901234567890123456"


class _AuthenticationFake:
    def __init__(self, principal: Principal) -> None:
        self.principal = principal

    async def resolve_principal(self, session_id: str) -> Principal | None:
        return self.principal if session_id == _SESSION_ID else None


@dataclass
class _RetrievalFake:
    principal: Principal
    case_id: UUID

    def __post_init__(self) -> None:
        self.last_request: RetrievalRequest | None = None
        self.source = RetrievedSource(
            document_id=uuid4(),
            document_title="Synthetic policy",
            document_file_type="txt",
            chunk_id=uuid4(),
            page_number=1,
            section_title="Scope",
            source_status="deprecated",
            rank=1,
            rank_score=0.032,
            retrieval_methods=(RetrievalMethod.SEMANTIC, RetrievalMethod.KEYWORD),
            excerpt="Synthetic bounded excerpt.",
            warning_codes=(RetrievalWarningCode.SOURCE_DEPRECATED,),
        )

    async def search(
        self, principal: Principal, request: RetrievalRequest
    ) -> tuple[RetrievedSource, ...]:
        authorize_retrieval_action(principal, RetrievalAction.SEARCH)
        if request.case_id != self.case_id:
            raise NotFoundError("Case")
        if "restricted" in request.source_statuses and RoleName.ADMIN not in principal.roles:
            raise AuthorizationDeniedError()
        self.last_request = request
        return (self.source,)


def _client(*roles: RoleName) -> tuple[TestClient, _RetrievalFake]:
    principal = Principal(
        user_id=uuid4(),
        organization_id=uuid4(),
        display_name="Synthetic Retrieval User",
        preferred_language="nb",
        roles=frozenset(roles),
    )
    retrieval = _RetrievalFake(principal, uuid4())
    app = create_api_app(AppSettings(environment="test"))
    app.dependency_overrides[get_authentication_service] = lambda: _AuthenticationFake(principal)
    app.dependency_overrides[get_retrieval_service] = lambda: retrieval
    client = TestClient(app)
    client.cookies.set("nordic_session", _SESSION_ID)
    return client, retrieval


def test_search_returns_only_the_safe_ranked_source_view() -> None:
    client, retrieval = _client(RoleName.CASE_WORKER)
    with client:
        response = client.post(
            "/api/retrieval/search",
            json={
                "case_id": str(retrieval.case_id),
                "query": "synthetic policy",
                "source_statuses": ["deprecated"],
                "limit": 1,
            },
        )

    assert response.status_code == 200
    source = response.json()["data"][0]
    assert source["rank"] == 1
    assert source["retrieval_methods"] == ["semantic", "keyword"]
    assert source["warning_codes"] == ["source_deprecated"]
    for forbidden in (
        "embedding",
        "content",
        "metadata",
        "offset",
        "storage_key",
        "checksum",
        "citation",
        "answer",
    ):
        assert forbidden not in source
    assert retrieval.last_request is not None
    assert retrieval.last_request.source_statuses == ("deprecated",)


def test_search_requires_session_role_and_validates_closed_input() -> None:
    anonymous, retrieval = _client(RoleName.ADMIN)
    anonymous.cookies.clear()
    with anonymous:
        unauthenticated = anonymous.post(
            "/api/retrieval/search",
            json={"case_id": str(retrieval.case_id), "query": "synthetic"},
        )
    auditor, auditor_retrieval = _client(RoleName.READ_ONLY_AUDITOR)
    with auditor:
        forbidden = auditor.post(
            "/api/retrieval/search",
            json={"case_id": str(auditor_retrieval.case_id), "query": "synthetic"},
        )
    worker, worker_retrieval = _client(RoleName.CASE_WORKER)
    with worker:
        malformed = worker.post(
            "/api/retrieval/search",
            json={
                "case_id": str(worker_retrieval.case_id),
                "query": "synthetic",
                "workflow_run_id": str(uuid4()),
            },
        )

    assert unauthenticated.status_code == 401
    assert forbidden.status_code == 403
    assert malformed.status_code == 422


def test_search_rejects_duplicate_document_selection_and_denies_restricted_source() -> None:
    client, retrieval = _client(RoleName.CASE_WORKER)
    document_id = uuid4()
    with client:
        duplicate = client.post(
            "/api/retrieval/search",
            json={
                "case_id": str(retrieval.case_id),
                "query": "synthetic",
                "document_ids": [str(document_id), str(document_id)],
            },
        )
        restricted = client.post(
            "/api/retrieval/search",
            json={
                "case_id": str(retrieval.case_id),
                "query": "synthetic",
                "source_statuses": ["restricted"],
            },
        )

    assert duplicate.status_code == 422
    assert restricted.status_code == 403
