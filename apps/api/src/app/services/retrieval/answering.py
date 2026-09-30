"""Direct, source-grounded Phase-15 RAG answer orchestration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.observability import get_telemetry
from app.db.models.prompt import ModelUsageRecord
from app.db.models.workflow import (
    AgentMessage,
    WorkflowRun,
)
from app.db.models.workflow import (
    RetrievedSource as PersistedRetrievedSource,
)
from app.db.repositories.case import CaseRepository
from app.db.repositories.rag_answer import RagAnswerRepository
from app.services.audit.service import AuditEventInput, AuditService, JSONValue
from app.services.auth.policy import RetrievalAction, authorize_retrieval_action
from app.services.auth.principal import Principal
from app.services.errors import NotFoundError, RagAnswerUnavailableError, RetrievalUnavailableError
from app.services.retrieval.citations import citations_for_labels, validate_inline_citations
from app.services.retrieval.evidence import assess_evidence, select_answer_evidence
from app.services.retrieval.generator import (
    RagAnswerGenerator,
    RagGenerationFailure,
    RagGenerationRequest,
    RagGenerationResult,
    calculate_cost_estimate,
)
from app.services.retrieval.service import RetrievalService
from app.services.retrieval.types import (
    AnswerEvidenceSource,
    AnswerLanguage,
    RagAnswerCommand,
    RagAnswerOutcome,
    RagAnswerResult,
    RagEvidenceReason,
    RetrievalRequest,
    RetrievalWorkflowContext,
)

_WORKFLOW_NAME = "rag_answer"
_WORKFLOW_VERSION = "phase15-v1"


class RagAnswerService:
    """Coordinate one bounded answer request without introducing graph execution."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        retrieval: RetrievalService,
        generator_factory: Callable[[], RagAnswerGenerator],
        maximum_answer_characters: int,
        maximum_evidence_sources: int,
        maximum_evidence_characters: int,
        minimum_evidence_sources: int,
        minimum_evidence_characters: int,
        input_price_per_million: Decimal | None,
        output_price_per_million: Decimal | None,
    ) -> None:
        self.session = session
        self._retrieval = retrieval
        self._generator_factory = generator_factory
        self._maximum_answer_characters = maximum_answer_characters
        self._maximum_evidence_sources = maximum_evidence_sources
        self._maximum_evidence_characters = maximum_evidence_characters
        self._minimum_evidence_sources = minimum_evidence_sources
        self._minimum_evidence_characters = minimum_evidence_characters
        self._input_price_per_million = input_price_per_million
        self._output_price_per_million = output_price_per_million
        self._cases = CaseRepository(session)
        self._records = RagAnswerRepository(session)
        self._audit = AuditService(session)

    async def answer(self, principal: Principal, command: RagAnswerCommand) -> RagAnswerResult:
        """Produce either a structurally cited answer or a normal safe refusal."""

        authorize_retrieval_action(principal, RetrievalAction.ANSWER)
        language = resolve_answer_language(command.answer_language, principal.preferred_language)
        started_at = datetime.now(UTC)
        started_clock = perf_counter()
        run = await self._add_and_commit_run(principal, command.case_id, language, started_at)
        try:
            retrieved = await self._retrieval.search(
                principal,
                RetrievalRequest(
                    case_id=command.case_id,
                    query=command.question,
                    result_limit=self._maximum_evidence_sources,
                    source_statuses=(),
                    document_ids=(),
                ),
                workflow_context=RetrievalWorkflowContext(run.id),
            )
        except RetrievalUnavailableError:
            await self._finalize_failure(
                principal=principal,
                run=run,
                evidence=(),
                started_clock=started_clock,
                model_failure=None,
                reason_code="retrieval_unavailable",
                language=language,
            )
            raise

        try:
            evidence = select_answer_evidence(
                retrieved,
                maximum_sources=self._maximum_evidence_sources,
                maximum_characters=self._maximum_evidence_characters,
            )
            assessment = assess_evidence(
                evidence,
                minimum_sources=self._minimum_evidence_sources,
                minimum_excerpt_characters=self._minimum_evidence_characters,
            )
        except ValueError as error:
            await self._finalize_failure(
                principal=principal,
                run=run,
                evidence=(),
                started_clock=started_clock,
                model_failure=None,
                reason_code="evidence_inconsistent",
                language=language,
            )
            raise RagAnswerUnavailableError() from error

        if not assessment.is_sufficient:
            answer = localized_refusal(language)
            result = RagAnswerResult(
                run_id=run.id,
                outcome=RagAnswerOutcome.NEEDS_MORE_EVIDENCE,
                language=language,
                answer=answer,
                citations=(),
                evidence_reason=assessment.reason or RagEvidenceReason.INSUFFICIENT_EVIDENCE,
            )
            await self._finalize_result(
                principal=principal,
                run=run,
                evidence=evidence,
                result=result,
                started_clock=started_clock,
                generation=None,
            )
            return result

        try:
            generation = await self._generate(
                RagGenerationRequest(
                    question=command.question,
                    language=language,
                    evidence=evidence,
                )
            )
        except RagGenerationFailure as failure:
            await self._finalize_failure(
                principal=principal,
                run=run,
                evidence=evidence,
                started_clock=started_clock,
                model_failure=failure,
                reason_code=failure.summary,
                language=language,
            )
            raise RagAnswerUnavailableError() from failure

        if generation.refused:
            result = RagAnswerResult(
                run_id=run.id,
                outcome=RagAnswerOutcome.NEEDS_MORE_EVIDENCE,
                language=language,
                answer=localized_refusal(language),
                citations=(),
                evidence_reason=RagEvidenceReason.MODEL_REFUSED,
            )
        else:
            validation = validate_inline_citations(
                generation.answer,
                evidence,
                maximum_answer_characters=self._maximum_answer_characters,
            )
            if generation.language is not language or not validation.is_valid:
                result = RagAnswerResult(
                    run_id=run.id,
                    outcome=RagAnswerOutcome.NEEDS_MORE_EVIDENCE,
                    language=language,
                    answer=localized_refusal(language),
                    citations=(),
                    evidence_reason=RagEvidenceReason.CITATION_VALIDATION_FAILED,
                )
            else:
                result = RagAnswerResult(
                    run_id=run.id,
                    outcome=RagAnswerOutcome.ANSWERED,
                    language=language,
                    answer=generation.answer,
                    citations=citations_for_labels(validation.labels, evidence),
                    evidence_reason=None,
                )
        await self._finalize_result(
            principal=principal,
            run=run,
            evidence=evidence,
            result=result,
            started_clock=started_clock,
            generation=generation,
        )
        return result

    async def _add_and_commit_run(
        self,
        principal: Principal,
        case_id: UUID,
        language: AnswerLanguage,
        started_at: datetime,
    ) -> WorkflowRun:
        # Validate active current-tenant case before adding the durable run; the
        # retrieval service repeats this check as its own policy boundary.
        if await self._cases.get(principal.organization_id, case_id) is None:
            raise NotFoundError("Case")
        run = WorkflowRun(
            organization_id=principal.organization_id,
            case_id=case_id,
            started_by_user_id=principal.user_id,
            workflow_name=_WORKFLOW_NAME,
            workflow_version=_WORKFLOW_VERSION,
            status="running",
            started_at=started_at,
            state_snapshot={"target_language": language.value, "model_called": False},
        )
        try:
            await self._records.add_run(run)
            await self.session.flush()
            await self.session.commit()
        except SQLAlchemyError as error:
            await self.session.rollback()
            raise RagAnswerUnavailableError() from error
        return run

    async def _generate(self, request: RagGenerationRequest) -> RagGenerationResult:
        generator = self._generator_factory()
        result: RagGenerationResult | None = None
        failure: RagGenerationFailure | None = None
        try:
            with get_telemetry().span("model.request", {"model.operation": "rag_answer"}):
                result = await generator.generate(request)
        except RagGenerationFailure as error:
            failure = error
        except Exception as error:
            failure = RagGenerationFailure(provider="configured", model_name="configured")
            failure.__cause__ = error
        finally:
            try:
                await generator.aclose()
            except Exception as error:
                if failure is None:
                    failure = RagGenerationFailure(provider="configured", model_name="configured")
                    failure.__cause__ = error
        if failure is not None:
            raise failure
        if result is None:
            raise RagGenerationFailure(provider="configured", model_name="configured")
        return result

    async def _finalize_result(
        self,
        *,
        principal: Principal,
        run: WorkflowRun,
        evidence: tuple[AnswerEvidenceSource, ...],
        result: RagAnswerResult,
        started_clock: float,
        generation: RagGenerationResult | None,
    ) -> None:
        duration_ms = _duration_ms(started_clock)
        cost = (
            calculate_cost_estimate(
                token_input=generation.token_input,
                token_output=generation.token_output,
                input_price_per_million=self._input_price_per_million,
                output_price_per_million=self._output_price_per_million,
            )
            if generation is not None
            else None
        )
        for source in evidence:
            await self._records.add_source(_persisted_source(principal, run, source))
        if generation is not None:
            await self._records.add_usage(
                ModelUsageRecord(
                    organization_id=principal.organization_id,
                    case_id=run.case_id,
                    workflow_run_id=run.id,
                    provider=generation.provider,
                    model_name=generation.model_name,
                    operation="rag_answer",
                    token_input=generation.token_input,
                    token_output=generation.token_output,
                    cost_estimate=cost,
                    latency_ms=generation.latency_ms,
                    success=True,
                    error_summary=None,
                )
            )
            await self._records.add_message(
                AgentMessage(
                    organization_id=principal.organization_id,
                    case_id=run.case_id,
                    workflow_run_id=run.id,
                    message_type="rag_answer",
                    role="assistant",
                    content=result.answer,
                    structured_output={
                        "outcome": result.outcome.value,
                        "language": result.language.value,
                        "citation_labels": [citation.label for citation in result.citations],
                    },
                    model_provider=generation.provider,
                    model_name=generation.model_name,
                    prompt_version_id=None,
                    token_input=generation.token_input,
                    token_output=generation.token_output,
                    cost_estimate=cost,
                    latency_ms=generation.latency_ms,
                )
            )
        run.finished_at = datetime.now(UTC)
        run.duration_ms = duration_ms
        run.total_tokens = _total_tokens(generation)
        run.total_cost_estimate = cost
        run.status = (
            "completed" if result.outcome is RagAnswerOutcome.ANSWERED else "needs_more_evidence"
        )
        run.error_summary = None
        run.state_snapshot = _state_snapshot(evidence, result, model_called=generation is not None)
        await self._audit.record_event(
            AuditEventInput(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type=(
                    "rag.answer_completed"
                    if result.outcome is RagAnswerOutcome.ANSWERED
                    else "rag.answer_refused"
                ),
                resource_type="workflow_run",
                resource_id=run.id,
                case_id=run.case_id,
                event_data=_audit_data(
                    evidence=evidence,
                    result=result,
                    model_called=generation is not None,
                    model_usage_recorded=generation is not None,
                    duration_recorded=True,
                    cost_recorded=cost is not None,
                ),
            )
        )
        await self._commit_terminal()
        telemetry = get_telemetry()
        telemetry.workflow_run(workflow_name=_WORKFLOW_NAME, outcome=run.status)
        if generation is not None:
            telemetry.model(
                provider=generation.provider,
                model=generation.model_name,
                operation="rag_answer",
                outcome="success",
                latency_ms=generation.latency_ms,
                token_input=generation.token_input,
                token_output=generation.token_output,
                cost_estimate=cost,
            )
        if result.outcome is RagAnswerOutcome.NEEDS_MORE_EVIDENCE:
            reason = (
                result.evidence_reason.value if result.evidence_reason is not None else "unknown"
            )
            telemetry.rag_refusal(reason=reason)

    async def _finalize_failure(
        self,
        *,
        principal: Principal,
        run: WorkflowRun,
        evidence: tuple[AnswerEvidenceSource, ...],
        started_clock: float,
        model_failure: RagGenerationFailure | None,
        reason_code: str,
        language: AnswerLanguage,
    ) -> None:
        for source in evidence:
            await self._records.add_source(_persisted_source(principal, run, source))
        cost = (
            calculate_cost_estimate(
                token_input=model_failure.token_input,
                token_output=model_failure.token_output,
                input_price_per_million=self._input_price_per_million,
                output_price_per_million=self._output_price_per_million,
            )
            if model_failure is not None
            else None
        )
        if model_failure is not None:
            await self._records.add_usage(
                ModelUsageRecord(
                    organization_id=principal.organization_id,
                    case_id=run.case_id,
                    workflow_run_id=run.id,
                    provider=model_failure.provider,
                    model_name=model_failure.model_name,
                    operation="rag_answer",
                    token_input=model_failure.token_input,
                    token_output=model_failure.token_output,
                    cost_estimate=cost,
                    latency_ms=model_failure.latency_ms,
                    success=False,
                    error_summary=model_failure.summary,
                )
            )
        run.finished_at = datetime.now(UTC)
        run.duration_ms = _duration_ms(started_clock)
        run.total_tokens = _total_tokens_from_values(
            model_failure.token_input if model_failure is not None else None,
            model_failure.token_output if model_failure is not None else None,
        )
        run.total_cost_estimate = cost
        run.status = "failed"
        run.error_summary = reason_code
        run.state_snapshot = {
            "target_language": language.value,
            "evidence_source_count": len(evidence),
            "cited_source_count": 0,
            "outcome": "failed",
            "reason_code": reason_code,
            "model_called": model_failure is not None,
        }
        await self._audit.record_event(
            AuditEventInput(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="rag.answer_failed",
                resource_type="workflow_run",
                resource_id=run.id,
                case_id=run.case_id,
                event_data={
                    "language": language.value,
                    "evidence_source_count": len(evidence),
                    "citation_source_count": 0,
                    "outcome": "failed",
                    "reason_code": reason_code,
                    "model_called": model_failure is not None,
                    "model_usage_recorded": model_failure is not None,
                    "duration_recorded": True,
                    "cost_recorded": cost is not None,
                },
            )
        )
        await self._commit_terminal()
        telemetry = get_telemetry()
        telemetry.workflow_run(workflow_name=_WORKFLOW_NAME, outcome="failed")
        if model_failure is not None:
            telemetry.model(
                provider=model_failure.provider,
                model=model_failure.model_name,
                operation="rag_answer",
                outcome="failure",
                latency_ms=model_failure.latency_ms,
                token_input=model_failure.token_input,
                token_output=model_failure.token_output,
                cost_estimate=cost,
            )

    async def _commit_terminal(self) -> None:
        try:
            await self.session.flush()
            await self.session.commit()
        except SQLAlchemyError as error:
            await self.session.rollback()
            raise RagAnswerUnavailableError() from error


def resolve_answer_language(
    requested: AnswerLanguage | None, preferred_language: str | None
) -> AnswerLanguage:
    """Resolve output language without headers, browser state, or question translation."""

    if requested is not None:
        return requested
    value = (preferred_language or "").strip().casefold().replace("_", "-")
    if value == "en" or value.startswith("en-"):
        return AnswerLanguage.EN
    if value in {"nb", "no", "norwegian", "norsk"} or value.startswith(("nb-", "no-")):
        return AnswerLanguage.NB
    return AnswerLanguage.NB


def localized_refusal(language: AnswerLanguage) -> str:
    """Return a short deterministic refusal that makes no unsupported factual claim."""

    if language is AnswerLanguage.EN:
        return "I need more approved source material or a clearer question before I can answer."
    return "Jeg trenger flere godkjente kilder eller et tydeligere spørsmål før jeg kan svare."


def _persisted_source(
    principal: Principal, run: WorkflowRun, source: AnswerEvidenceSource
) -> PersistedRetrievedSource:
    return PersistedRetrievedSource(
        organization_id=principal.organization_id,
        case_id=run.case_id,
        workflow_run_id=run.id,
        document_id=source.source.document_id,
        chunk_id=source.source.chunk_id,
        rank=source.source.rank,
        score=Decimal(str(source.source.rank_score)),
        retrieval_method=",".join(method.value for method in source.source.retrieval_methods),
        excerpt=source.excerpt,
        citation_label=source.citation_label,
    )


def _state_snapshot(
    evidence: tuple[AnswerEvidenceSource, ...],
    result: RagAnswerResult,
    *,
    model_called: bool,
) -> dict[str, object]:
    return {
        "target_language": result.language.value,
        "evidence_source_count": len(evidence),
        "cited_source_count": len(result.citations),
        "outcome": result.outcome.value,
        "reason_code": result.evidence_reason.value if result.evidence_reason is not None else None,
        "model_called": model_called,
    }


def _audit_data(
    *,
    evidence: tuple[AnswerEvidenceSource, ...],
    result: RagAnswerResult,
    model_called: bool,
    model_usage_recorded: bool,
    duration_recorded: bool,
    cost_recorded: bool,
) -> dict[str, JSONValue]:
    return {
        "language": result.language.value,
        "evidence_source_count": len(evidence),
        "citation_source_count": len(result.citations),
        "outcome": result.outcome.value,
        "reason_code": result.evidence_reason.value if result.evidence_reason is not None else None,
        "model_called": model_called,
        "model_usage_recorded": model_usage_recorded,
        "duration_recorded": duration_recorded,
        "cost_recorded": cost_recorded,
    }


def _duration_ms(started_clock: float) -> int:
    return max(0, round((perf_counter() - started_clock) * 1_000))


def _total_tokens(generation: RagGenerationResult | None) -> int | None:
    if generation is None:
        return None
    return _total_tokens_from_values(generation.token_input, generation.token_output)


def _total_tokens_from_values(token_input: int | None, token_output: int | None) -> int | None:
    values = tuple(value for value in (token_input, token_output) if value is not None)
    return sum(values) if values else None
