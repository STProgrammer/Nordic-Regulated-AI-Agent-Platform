from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from decimal import Decimal
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from app.db.models.prompt import ModelUsageRecord
from app.db.models.workflow import AgentMessage, WorkflowRun
from app.db.models.workflow import RetrievedSource as PersistedRetrievedSource
from app.db.repositories.case import CaseRepository
from app.db.repositories.rag_answer import RagAnswerRepository
from app.services.audit.service import AuditEventCreate, AuditService
from app.services.auth.principal import Principal, RoleName
from app.services.errors import RagAnswerUnavailableError
from app.services.retrieval.answering import RagAnswerService, resolve_answer_language
from app.services.retrieval.generator import (
    RagGenerationFailure,
    RagGenerationRequest,
    RagGenerationResult,
)
from app.services.retrieval.service import RetrievalService
from app.services.retrieval.types import (
    AnswerLanguage,
    RagAnswerCommand,
    RagAnswerOutcome,
    RetrievalMethod,
    RetrievedSource,
)
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class _Records:
    runs: list[WorkflowRun] = field(default_factory=list)
    sources: list[PersistedRetrievedSource] = field(default_factory=list)
    messages: list[AgentMessage] = field(default_factory=list)
    usages: list[ModelUsageRecord] = field(default_factory=list)

    async def create_run(self, run: WorkflowRun) -> WorkflowRun:
        run.id = uuid4()
        self.runs.append(run)
        return run

    async def add_source(self, source: PersistedRetrievedSource) -> PersistedRetrievedSource:
        self.sources.append(source)
        return source

    async def add_message(self, message: AgentMessage) -> AgentMessage:
        self.messages.append(message)
        return message

    async def add_usage(self, usage: ModelUsageRecord) -> ModelUsageRecord:
        self.usages.append(usage)
        return usage


@dataclass
class _Audit:
    commands: list[AuditEventCreate] = field(default_factory=list)

    async def record_event(self, command: AuditEventCreate) -> None:
        self.commands.append(command)


class _Cases:
    async def get(self, _organization_id: UUID, _case_id: UUID) -> object:
        return object()


@dataclass
class _Retrieval:
    sources: tuple[RetrievedSource, ...]
    calls: list[object] = field(default_factory=list)

    async def search(self, *_args: object, **kwargs: object) -> tuple[RetrievedSource, ...]:
        self.calls.append(kwargs)
        return self.sources


@dataclass
class _Generator:
    result: RagGenerationResult | None = None
    failure: RagGenerationFailure | None = None
    calls: int = 0
    closed: bool = False

    async def generate(self, _request: RagGenerationRequest) -> RagGenerationResult:
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        assert self.result is not None
        return self.result

    async def aclose(self) -> None:
        self.closed = True


def _source() -> RetrievedSource:
    return RetrievedSource(
        document_id=uuid4(),
        document_title="Synthetic policy",
        document_file_type="txt",
        chunk_id=uuid4(),
        page_number=1,
        section_title="Scope",
        source_status="approved",
        rank=1,
        rank_score=0.03,
        retrieval_methods=(RetrievalMethod.SEMANTIC, RetrievalMethod.KEYWORD),
        excerpt="Synthetic approved evidence sufficient for an answer.",
        warning_codes=(),
    )


def _service(
    *, sources: tuple[RetrievedSource, ...], generator: _Generator
) -> tuple[RagAnswerService, _Records, _Audit]:
    session = cast(AsyncSession, AsyncMock(spec=AsyncSession))
    retrieval = _Retrieval(sources)
    service = RagAnswerService(
        session,
        retrieval=cast(RetrievalService, retrieval),
        generator_factory=lambda: generator,
        maximum_answer_characters=500,
        maximum_evidence_sources=3,
        maximum_evidence_characters=500,
        minimum_evidence_sources=1,
        minimum_evidence_characters=10,
        input_price_per_million=Decimal("1"),
        output_price_per_million=Decimal("2"),
    )
    records = _Records()
    audit = _Audit()
    service._cases = cast(CaseRepository, _Cases())
    service._records = cast(RagAnswerRepository, records)
    service._audit = cast(AuditService, audit)
    return service, records, audit


def _principal() -> Principal:
    return Principal(
        user_id=uuid4(),
        organization_id=uuid4(),
        display_name="Synthetic user",
        preferred_language="nb-NO",
        roles=frozenset({RoleName.CASE_WORKER}),
    )


def _command() -> RagAnswerCommand:
    return RagAnswerCommand(case_id=uuid4(), question="Hva gjelder policyen?", answer_language=None)


def test_answer_persists_complete_cited_run_and_content_free_terminal_audit() -> None:
    generator = _Generator(
        result=RagGenerationResult(
            answer="Policyen gjelder den syntetiske saken. [S1]",
            refused=False,
            language=AnswerLanguage.NB,
            provider="test",
            model_name="test-model",
            token_input=10,
            token_output=20,
            latency_ms=4,
        )
    )
    service, records, audit = _service(sources=(_source(),), generator=generator)

    result = asyncio.run(service.answer(_principal(), _command()))

    assert result.outcome is RagAnswerOutcome.ANSWERED
    assert result.citations[0].label == "S1"
    assert records.runs[0].status == "completed"
    assert records.runs[0].workflow_name == "rag_answer"
    assert len(records.sources) == len(records.messages) == len(records.usages) == 1
    assert records.sources[0].citation_label == "S1"
    assert records.usages[0].success is True
    command = audit.commands[0]
    event_data = command.event_data
    assert command.event_type == "rag.answer_completed"
    assert all(key not in event_data for key in {"query", "excerpt", "chunk_id", "score", "token"})
    assert generator.closed is True


def test_preliminary_refusal_never_calls_a_model_or_creates_model_records() -> None:
    generator = _Generator(
        result=RagGenerationResult(
            answer="Should not run [S1]",
            refused=False,
            language=AnswerLanguage.NB,
            provider="test",
            model_name="test-model",
            token_input=1,
            token_output=1,
            latency_ms=1,
        )
    )
    service, records, audit = _service(sources=(), generator=generator)

    result = asyncio.run(service.answer(_principal(), _command()))

    assert result.outcome is RagAnswerOutcome.NEEDS_MORE_EVIDENCE
    assert result.citations == ()
    assert generator.calls == 0
    assert records.runs[0].status == "needs_more_evidence"
    assert records.messages == []
    assert records.usages == []
    assert audit.commands[0].event_type == "rag.answer_refused"


def test_invalid_citations_are_refused_and_the_generated_answer_is_not_exposed() -> None:
    generator = _Generator(
        result=RagGenerationResult(
            answer="Unsupported label. [S9]",
            refused=False,
            language=AnswerLanguage.NB,
            provider="test",
            model_name="test-model",
            token_input=1,
            token_output=1,
            latency_ms=1,
        )
    )
    service, records, _audit = _service(sources=(_source(),), generator=generator)

    result = asyncio.run(service.answer(_principal(), _command()))

    assert result.outcome is RagAnswerOutcome.NEEDS_MORE_EVIDENCE
    assert result.evidence_reason is not None
    assert "S9" not in result.answer
    assert records.messages[0].content == result.answer
    assert records.runs[0].status == "needs_more_evidence"


def test_provider_failure_is_recorded_before_neutral_error_is_raised() -> None:
    generator = _Generator(failure=RagGenerationFailure(provider="test", model_name="test-model"))
    service, records, audit = _service(sources=(_source(),), generator=generator)

    with pytest.raises(RagAnswerUnavailableError):
        asyncio.run(service.answer(_principal(), _command()))

    assert records.runs[0].status == "failed"
    assert records.usages[0].success is False
    assert audit.commands[0].event_type == "rag.answer_failed"


def test_language_resolution_prefers_explicit_request_then_known_preference() -> None:
    assert resolve_answer_language(AnswerLanguage.EN, "nb-NO") is AnswerLanguage.EN
    assert resolve_answer_language(None, "en-GB") is AnswerLanguage.EN
    assert resolve_answer_language(None, "norwegian") is AnswerLanguage.NB
    assert resolve_answer_language(None, "unknown") is AnswerLanguage.NB
