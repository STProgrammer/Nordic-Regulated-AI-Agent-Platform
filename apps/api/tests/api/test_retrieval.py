"""Transport contract tests for governed Phase 13 retrieval search."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.api.dependencies import (
    get_authentication_service,
    get_rag_answer_service,
    get_retrieval_service,
)
from app.core.config import AppSettings
from app.main import create_api_app
from app.services.auth.policy import RetrievalAction, authorize_retrieval_action
from app.services.auth.principal import Principal, RoleName
from app.services.errors import AuthorizationDeniedError, NotFoundError
from app.services.retrieval.types import (
    AnswerLanguage,
    RagAnswerCommand,
    RagAnswerOutcome,
    RagAnswerResult,
    RagCitation,
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


@dataclass
class _RagAnswerFake:
    principal: Principal
    case_id: UUID

    def __post_init__(self) -> None:
        self.last_command: RagAnswerCommand | None = None
        self.source = RetrievedSource(
            document_id=uuid4(),
            document_title="Synthetic approved policy",
            document_file_type="txt",
            chunk_id=uuid4(),
            page_number=1,
            section_title="Scope",
            source_status="approved",
            rank=1,
            rank_score=0.02,
            retrieval_methods=(RetrievalMethod.SEMANTIC,),
            excerpt="Synthetic approved excerpt.",
            warning_codes=(),
        )

    async def answer(self, principal: Principal, command: RagAnswerCommand) -> RagAnswerResult:
        authorize_retrieval_action(principal, RetrievalAction.ANSWER)
        if command.case_id != self.case_id:
            raise NotFoundError("Case")
        self.last_command = command
        language = command.answer_language or AnswerLanguage.NB
        return RagAnswerResult(
            run_id=uuid4(),
            outcome=RagAnswerOutcome.ANSWERED,
            language=language,
            answer="Synthetic answer supported by the excerpt. [S1]",
            citations=(
                RagCitation(
                    label="S1",
                    document_id=self.source.document_id,
                    document_title=self.source.document_title,
                    document_file_type=self.source.document_file_type,
                    chunk_id=self.source.chunk_id,
                    page_number=self.source.page_number,
                    section_title=self.source.section_title,
                    excerpt=self.source.excerpt,
                    rank=self.source.rank,
                    retrieval_methods=self.source.retrieval_methods,
                ),
            ),
            evidence_reason=None,
        )


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


def _answer_client(*roles: RoleName) -> tuple[TestClient, _RagAnswerFake]:
    principal = Principal(
        user_id=uuid4(),
        organization_id=uuid4(),
        display_name="Synthetic Answer User",
        preferred_language="nb-NO",
        roles=frozenset(roles),
    )
    answer = _RagAnswerFake(principal, uuid4())
    app = create_api_app(AppSettings(environment="test"))
    app.dependency_overrides[get_authentication_service] = lambda: _AuthenticationFake(principal)
    app.dependency_overrides[get_rag_answer_service] = lambda: answer
    client = TestClient(app)
    client.cookies.set("nordic_session", _SESSION_ID)
    return client, answer


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


def test_answer_returns_only_validated_safe_citations_and_request_metadata() -> None:
    client, answer = _answer_client(RoleName.CASE_WORKER)
    with client:
        response = client.post(
            "/api/retrieval/answer",
            json={
                "case_id": str(answer.case_id),
                "question": "Hva gjelder den syntetiske policyen?",
                "answer_language": "en",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["request_id"] == response.headers["X-Request-ID"]
    assert body["data"]["outcome"] == "answered"
    assert body["data"]["language"] == "en"
    assert body["data"]["answer"].endswith("[S1]")
    assert body["data"]["citations"][0]["label"] == "S1"
    assert set(body["data"]["citations"][0]) == {
        "label",
        "document_id",
        "document_title",
        "document_file_type",
        "chunk_id",
        "page_number",
        "section_title",
        "excerpt",
        "rank",
        "retrieval_methods",
    }
    assert answer.last_command is not None
    assert answer.last_command.answer_language is AnswerLanguage.EN


def test_answer_requires_session_permitted_role_and_closed_input() -> None:
    anonymous, answer = _answer_client(RoleName.ADMIN)
    anonymous.cookies.clear()
    with anonymous:
        unauthenticated = anonymous.post(
            "/api/retrieval/answer",
            json={"case_id": str(answer.case_id), "question": "synthetic"},
        )
    auditor, auditor_answer = _answer_client(RoleName.READ_ONLY_AUDITOR)
    with auditor:
        forbidden = auditor.post(
            "/api/retrieval/answer",
            json={"case_id": str(auditor_answer.case_id), "question": "synthetic"},
        )
    worker, worker_answer = _answer_client(RoleName.CASE_WORKER)
    with worker:
        malformed = worker.post(
            "/api/retrieval/answer",
            json={
                "case_id": str(worker_answer.case_id),
                "question": "   ",
                "model": "caller-controlled",
            },
        )

    assert unauthenticated.status_code == 401
    assert forbidden.status_code == 403
    assert malformed.status_code == 422
