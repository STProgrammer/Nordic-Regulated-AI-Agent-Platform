"""Celery tasks whose only business payload is a document UUID."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from agent_orchestrator.config import AgentSettings
from agent_orchestrator.graphs.approval_graph import ApprovalGraph, ApprovalGraphDependencies
from agent_orchestrator.graphs.approval_types import ApprovalWorkflowState
from agent_orchestrator.graphs.drafting_graph import (
    DraftingCaseInput,
    DraftingEvidenceSource,
    DraftingGraph,
    DraftingGraphDependencies,
)
from agent_orchestrator.graphs.drafting_types import DraftingWorkflowState, OutputLanguage
from agent_orchestrator.graphs.evidence_graph import (
    EvidenceCandidate,
    EvidenceCandidates,
    EvidenceCaseInput,
    EvidenceGraph,
    EvidenceGraphDependencies,
)
from agent_orchestrator.graphs.evidence_types import EvidenceWorkflowState
from agent_orchestrator.graphs.extraction_graph import (
    ExtractionCaseInput,
    ExtractionGraph,
    ExtractionGraphDependencies,
)
from agent_orchestrator.graphs.extraction_types import ExtractionWorkflowState
from agent_orchestrator.graphs.intake_graph import (
    IntakeCaseInput,
    IntakeGraph,
    IntakeGraphDependencies,
)
from agent_orchestrator.graphs.intake_types import (
    IntakeDomain,
    IntakeLanguage,
    IntakePriority,
    IntakeWorkflowState,
    LanguageDetectionResult,
)
from agent_orchestrator.graphs.risk_graph import RiskGraph, RiskGraphDependencies
from agent_orchestrator.graphs.risk_types import RiskWorkflowState
from agent_orchestrator.memory.store import PostgresControlledMemoryStore
from agent_orchestrator.model_providers.factory import build_model_provider
from agent_orchestrator.types import RetryPolicy, RuntimeStatus, WorkflowContext
from celery import Task  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppSettings, get_settings
from app.core.logging import get_logger
from app.core.observability import instrument_celery_task
from app.db.models.workflow import WorkflowRun
from app.db.repositories.case import CaseRepository
from app.db.repositories.document import DocumentRepository
from app.db.repositories.identity import UserRepository, UserRoleRepository
from app.db.session import dispose_database_engines, get_sessionmaker
from app.services.approvals.service import ApprovalWorkflowService
from app.services.auth.principal import Principal, RoleName
from app.services.documents.chunking import CanonicalTextChunker, ChunkingConfig, TiktokenTokenizer
from app.services.documents.dispatch import CeleryDocumentTaskDispatcher
from app.services.documents.embeddings import (
    EmbeddingError,
    FailingEmbeddingProvider,
    build_embedding_provider,
)
from app.services.documents.indexing import DocumentIndexCoordinator, IndexProcessOutcome
from app.services.documents.parsers.language import detect_language
from app.services.documents.parsers.registry import DocumentParserRegistry
from app.services.documents.parsing import DocumentParseCoordinator, ParseProcessOutcome
from app.services.documents.storage import AzureBlobObjectStorage
from app.services.evaluation.service import EvaluationService
from app.services.memory.service import ControlledMemoryService
from app.services.retrieval.service import RetrievalService
from app.services.retrieval.types import RetrievalRequest, RetrievalWorkflowContext
from app.services.workflows.dispatch import CeleryWorkflowTaskDispatcher
from app.services.workflows.drafting import DRAFTING_WORKFLOW_NAME, persist_draft
from app.services.workflows.evidence import (
    EVIDENCE_WORKFLOW_NAME,
    persist_evidence_case_result,
)
from app.services.workflows.extraction import (
    EXTRACTION_WORKFLOW_NAME,
    load_eligible_evidence,
    persist_extracted_fields,
)
from app.services.workflows.intake import INTAKE_WORKFLOW_NAME
from app.services.workflows.orchestrator import (
    SqlAlchemyPromptLoader,
    SqlAlchemyWorkflowPersistence,
    persist_intake_case_result,
)
from app.services.workflows.risk import (
    RISK_WORKFLOW_NAME,
    load_risk_prerequisites,
    persist_risk_assessment,
)
from app.workers.celery_app import celery_app

_logger = get_logger("workers.document_tasks")
_RECONCILIATION_LIMIT = 100


async def _process_evaluation(run_id: UUID, settings: AppSettings) -> str:
    """Reload a UUID-only deterministic evaluation run and persist its safe terminal result."""

    try:
        async with get_sessionmaker(settings)() as session:
            return await EvaluationService(session).execute(run_id)
    finally:
        await dispose_database_engines()


async def _fail_evaluation(run_id: UUID, settings: AppSettings) -> None:
    """Persist a neutral terminal failure after exhausted infrastructure retries."""

    try:
        async with get_sessionmaker(settings)() as session:
            await EvaluationService(session).fail_unexpected(run_id)
    finally:
        await dispose_database_engines()


def _intake_language_detector(
    settings: AppSettings,
) -> Callable[[str], LanguageDetectionResult]:
    """Adapt the parser helper without importing app concerns into graph core."""

    def detect(text: str) -> LanguageDetectionResult:
        result = detect_language(
            text,
            minimum_characters=settings.document_language_minimum_characters,
            confidence_threshold=settings.document_language_confidence_threshold,
        )
        confidence = result.confidence if result.confidence is not None else 0.0
        return LanguageDetectionResult(
            language=IntakeLanguage(result.language), confidence=confidence
        )

    return detect


async def _process_intake_workflow(workflow_run_id: UUID, settings: AppSettings) -> str:
    """Reload a UUID-only queued Intake run and execute it in one short-lived session."""

    try:
        async with get_sessionmaker(settings)() as session:
            # The private worker first resolves tenant identity, then all subsequent
            # lookups are organization scoped. No public repository exposes this path.
            run = await session.scalar(select(WorkflowRun).where(WorkflowRun.id == workflow_run_id))
            if run is None or run.workflow_name != INTAKE_WORKFLOW_NAME or run.status != "queued":
                return "noop"
            context = WorkflowContext(
                workflow_run_id=run.id,
                organization_id=run.organization_id,
                case_id=run.case_id,
                initiated_by_user_id=run.started_by_user_id,
                workflow_name=run.workflow_name,
                workflow_version=run.workflow_version,
            )
            case = await CaseRepository(session).get(context.organization_id, context.case_id)
            user = await UserRepository(session).get(
                context.organization_id, context.initiated_by_user_id
            )
            persistence = SqlAlchemyWorkflowPersistence(session)
            if case is None or user is None or not user.is_active:
                if await persistence.claim_run(context):
                    await persistence.fail_run(
                        context,
                        state_snapshot={
                            "workflow_name": context.workflow_name,
                            "workflow_version": context.workflow_version,
                            "state_schema_version": "v1",
                            "status": "failed",
                        },
                        duration_ms=0,
                        error_code="case_not_available",
                    )
                    await session.commit()
                return "failed"
            outcome = "failed"
            try:
                agent_settings = AgentSettings()
                fixtures = {
                    "intake_classification": {
                        "case_type": "case_support",
                        "recommended_domain": case.domain,
                        "confidence": 0.9,
                        "reason_codes": ["deterministic_fixture"],
                    }
                }
                graph = IntakeGraph(
                    IntakeGraphDependencies(
                        case_input=IntakeCaseInput(title=case.title, description=case.description),
                        prompt_loader=SqlAlchemyPromptLoader(session),
                        model_provider=build_model_provider(
                            agent_settings,
                            deterministic_fixtures=(
                                fixtures if agent_settings.provider == "deterministic" else None
                            ),
                        ),
                        persistence=persistence,
                        language_detector=_intake_language_detector(settings),
                        persist_result=lambda graph_context, state: persist_intake_case_result(
                            session, graph_context, state
                        ),
                        confidence_threshold=agent_settings.intake_confidence_threshold,
                        retry_policy=RetryPolicy(
                            maximum_retries=agent_settings.node_maximum_retries
                        ),
                    )
                )
                state = IntakeWorkflowState(
                    context=context,
                    declared_language=IntakeLanguage(case.language),
                    submitted_domain=IntakeDomain(case.domain),
                    priority=IntakePriority(case.priority),
                )
                result = await graph.run(context, state)
                outcome = result.outcome.status.value
            except Exception:
                # Settings/corrupt persisted enum failures happen before the graph
                # can take ownership. Convert them to one durable neutral outcome.
                if await persistence.claim_run(context):
                    await persistence.fail_run(
                        context,
                        state_snapshot={
                            "workflow_name": context.workflow_name,
                            "workflow_version": context.workflow_version,
                            "state_schema_version": "v1",
                            "status": "failed",
                        },
                        duration_ms=0,
                        error_code="workflow_configuration_unavailable",
                    )
            await session.commit()
            return outcome
    finally:
        await dispose_database_engines()


def _retrieval_service(session: AsyncSession, settings: AppSettings) -> RetrievalService:
    """Build the existing governed hybrid retrieval boundary inside a private worker."""

    return RetrievalService(
        session,
        provider_factory=lambda: build_embedding_provider(settings),
        default_result_limit=settings.retrieval_default_result_limit,
        maximum_result_limit=settings.retrieval_max_result_limit,
        semantic_candidate_limit=settings.retrieval_semantic_candidate_limit,
        keyword_candidate_limit=settings.retrieval_keyword_candidate_limit,
        rank_fusion_constant=settings.retrieval_rank_fusion_constant,
        maximum_query_characters=settings.retrieval_max_query_characters,
        maximum_document_selections=settings.retrieval_max_document_selections,
        maximum_excerpt_characters=settings.retrieval_max_excerpt_characters,
    )


async def _process_evidence_workflow(workflow_run_id: UUID, settings: AppSettings) -> str:
    """Reload a UUID-only queued Evidence run and execute its fixed ten-node graph."""

    try:
        async with get_sessionmaker(settings)() as session:
            run = await session.scalar(select(WorkflowRun).where(WorkflowRun.id == workflow_run_id))
            if run is None or run.workflow_name != EVIDENCE_WORKFLOW_NAME or run.status != "queued":
                return "noop"
            context = WorkflowContext(
                workflow_run_id=run.id,
                organization_id=run.organization_id,
                case_id=run.case_id,
                initiated_by_user_id=run.started_by_user_id,
                workflow_name=run.workflow_name,
                workflow_version=run.workflow_version,
            )
            case = await CaseRepository(session).get(context.organization_id, context.case_id)
            user = await UserRepository(session).get(
                context.organization_id, context.initiated_by_user_id
            )
            persistence = SqlAlchemyWorkflowPersistence(session)
            if case is None or user is None or not user.is_active:
                if await persistence.claim_run(context):
                    await persistence.fail_run(
                        context,
                        state_snapshot={
                            "workflow_name": context.workflow_name,
                            "workflow_version": context.workflow_version,
                            "state_schema_version": "v1",
                            "status": "failed",
                        },
                        duration_ms=0,
                        error_code="case_not_available",
                    )
                    await session.commit()
                return "failed"
            role_names = await UserRoleRepository(session).list_role_names_for_user(
                context.organization_id, user.id
            )
            try:
                principal = Principal(
                    user_id=user.id,
                    organization_id=user.organization_id,
                    display_name=user.display_name,
                    preferred_language=user.preferred_language,
                    roles=frozenset(RoleName(name) for name in role_names),
                )

                async def retrieve(query: str) -> EvidenceCandidates:
                    retrieved = await _retrieval_service(session, settings).search(
                        principal,
                        RetrievalRequest(
                            case_id=context.case_id,
                            query=query,
                            result_limit=5,
                            source_statuses=(),
                            document_ids=(),
                        ),
                        workflow_context=RetrievalWorkflowContext(context.workflow_run_id),
                    )
                    candidates = tuple(
                        EvidenceCandidate(
                            document_id=source.document_id,
                            chunk_id=source.chunk_id,
                            source_status=source.source_status,
                            rank=source.rank,
                            rank_score=source.rank_score,
                            retrieval_methods=tuple(
                                method.value for method in source.retrieval_methods
                            ),
                            excerpt=source.excerpt,
                            warning_codes=tuple(code.value for code in source.warning_codes),
                        )
                        for source in retrieved
                    )
                    return EvidenceCandidates(
                        vector=tuple(
                            candidate
                            for candidate in candidates
                            if "semantic" in candidate.retrieval_methods
                        ),
                        keyword=tuple(
                            candidate
                            for candidate in candidates
                            if "keyword" in candidate.retrieval_methods
                        ),
                    )

                agent_settings = AgentSettings()
                graph = EvidenceGraph(
                    EvidenceGraphDependencies(
                        case_input=EvidenceCaseInput(
                            title=case.title, description=case.description
                        ),
                        retrieve_candidates=retrieve,
                        persistence=persistence,
                        persist_result=lambda graph_context, state, package: (
                            persist_evidence_case_result(session, graph_context, state, package)
                        ),
                        maximum_sources=agent_settings.evidence_maximum_sources,
                        maximum_excerpt_characters=agent_settings.evidence_maximum_excerpt_characters,
                        minimum_sources=agent_settings.evidence_minimum_sources,
                        minimum_excerpt_characters=(
                            agent_settings.evidence_minimum_excerpt_characters
                        ),
                        retry_policy=RetryPolicy(
                            maximum_retries=agent_settings.node_maximum_retries
                        ),
                    )
                )
                result = await graph.run(context, EvidenceWorkflowState(context=context))
                await session.commit()
                return result.outcome.status.value
            except Exception:
                # Fail closed without retaining provider/retrieval exception content.
                if await persistence.claim_run(context):
                    await persistence.fail_run(
                        context,
                        state_snapshot={
                            "workflow_name": context.workflow_name,
                            "workflow_version": context.workflow_version,
                            "state_schema_version": "v1",
                            "status": "failed",
                        },
                        duration_ms=0,
                        error_code="workflow_configuration_unavailable",
                    )
                    await session.commit()
                return "failed"
    finally:
        await dispose_database_engines()


async def _process_extraction_workflow(workflow_run_id: UUID, settings: AppSettings) -> str:
    """Reload one queued Extraction run and compose only its eligible persisted Evidence input."""

    try:
        async with get_sessionmaker(settings)() as session:
            run = await session.scalar(select(WorkflowRun).where(WorkflowRun.id == workflow_run_id))
            if (
                run is None
                or run.workflow_name != EXTRACTION_WORKFLOW_NAME
                or run.status != "queued"
            ):
                return "noop"
            context = WorkflowContext(
                workflow_run_id=run.id,
                organization_id=run.organization_id,
                case_id=run.case_id,
                initiated_by_user_id=run.started_by_user_id,
                workflow_name=run.workflow_name,
                workflow_version=run.workflow_version,
            )
            case = await CaseRepository(session).get(context.organization_id, context.case_id)
            user = await UserRepository(session).get(
                context.organization_id, context.initiated_by_user_id
            )
            persistence = SqlAlchemyWorkflowPersistence(session)
            if case is None or user is None or not user.is_active:
                if await persistence.claim_run(context):
                    await persistence.fail_run(
                        context,
                        state_snapshot={
                            "workflow_name": context.workflow_name,
                            "workflow_version": context.workflow_version,
                            "state_schema_version": "v1",
                            "status": "failed",
                        },
                        duration_ms=0,
                        error_code="case_not_available",
                    )
                    await session.commit()
                return "failed"
            evidence = await load_eligible_evidence(
                session, context.organization_id, context.case_id
            )
            if evidence is None:
                if await persistence.claim_run(context):
                    await persistence.complete_run(
                        context,
                        status=RuntimeStatus.NEEDS_MORE_EVIDENCE,
                        state_snapshot={
                            "workflow_name": context.workflow_name,
                            "workflow_version": context.workflow_version,
                            "state_schema_version": "v1",
                            "status": "needs_more_evidence",
                            "evidence_available": False,
                        },
                        duration_ms=0,
                    )
                    await session.commit()
                return "needs_more_evidence"
            try:
                agent_settings = AgentSettings()
                fixture_fields: list[dict[str, object]] = []
                if evidence.sources:
                    fixture_fields = [
                        {
                            "kind": "reference_numbers",
                            "value": {"references": ["SYNTHETIC-1"]},
                            "source_citation": evidence.sources[0].citation_label,
                            "confidence": 0.9,
                        }
                    ]
                fixtures = {"extraction_fields": {"fields": fixture_fields}}
                graph = ExtractionGraph(
                    ExtractionGraphDependencies(
                        case_input=ExtractionCaseInput(
                            title=case.title,
                            description=case.description,
                            case_type=case.case_type,
                            domain=case.domain,
                            language=case.language,
                        ),
                        evidence_sources=evidence.sources,
                        prompt_loader=SqlAlchemyPromptLoader(session),
                        model_provider=build_model_provider(
                            agent_settings,
                            deterministic_fixtures=(
                                fixtures if agent_settings.provider == "deterministic" else None
                            ),
                        ),
                        persistence=persistence,
                        persist_fields=lambda graph_context, state, fields: (
                            persist_extracted_fields(session, graph_context, state, fields)
                        ),
                        confidence_threshold=agent_settings.extraction_confidence_threshold,
                        retry_policy=RetryPolicy(
                            maximum_retries=agent_settings.node_maximum_retries
                        ),
                    )
                )
                result = await graph.run(context, ExtractionWorkflowState(context=context))
                await session.commit()
                return result.outcome.status.value
            except Exception:
                if await persistence.claim_run(context):
                    await persistence.fail_run(
                        context,
                        state_snapshot={
                            "workflow_name": context.workflow_name,
                            "workflow_version": context.workflow_version,
                            "state_schema_version": "v1",
                            "status": "failed",
                            "evidence_available": True,
                        },
                        duration_ms=0,
                        error_code="workflow_configuration_unavailable",
                    )
                    await session.commit()
                return "failed"
    finally:
        await dispose_database_engines()


async def _process_drafting_workflow(workflow_run_id: UUID, settings: AppSettings) -> str:
    """Reload one queued Drafting run and compose only its eligible Evidence package."""

    try:
        async with get_sessionmaker(settings)() as session:
            run = await session.scalar(select(WorkflowRun).where(WorkflowRun.id == workflow_run_id))
            if run is None or run.workflow_name != DRAFTING_WORKFLOW_NAME or run.status != "queued":
                return "noop"
            context = WorkflowContext(
                workflow_run_id=run.id,
                organization_id=run.organization_id,
                case_id=run.case_id,
                initiated_by_user_id=run.started_by_user_id,
                workflow_name=run.workflow_name,
                workflow_version=run.workflow_version,
            )
            case = await CaseRepository(session).get(context.organization_id, context.case_id)
            user = await UserRepository(session).get(
                context.organization_id, context.initiated_by_user_id
            )
            persistence = SqlAlchemyWorkflowPersistence(session)
            evidence = await load_eligible_evidence(
                session, context.organization_id, context.case_id
            )
            if case is None or user is None or not user.is_active:
                if await persistence.claim_run(context):
                    await persistence.fail_run(
                        context,
                        state_snapshot={
                            "workflow_name": context.workflow_name,
                            "workflow_version": context.workflow_version,
                            "state_schema_version": "v1",
                            "status": "failed",
                            "draft_available": False,
                        },
                        duration_ms=0,
                        error_code="case_not_available",
                    )
                    await session.commit()
                return "failed"
            if evidence is None:
                if await persistence.claim_run(context):
                    await persistence.complete_run(
                        context,
                        status=RuntimeStatus.NEEDS_MORE_EVIDENCE,
                        state_snapshot={
                            "workflow_name": context.workflow_name,
                            "workflow_version": context.workflow_version,
                            "state_schema_version": "v1",
                            "status": "needs_more_evidence",
                            "evidence_available": False,
                            "draft_available": False,
                        },
                        duration_ms=0,
                    )
                    await session.commit()
                return "needs_more_evidence"
            try:
                agent_settings = AgentSettings()
                requested_language = run.state_snapshot.get("target_language", case.language)
                language = OutputLanguage(
                    requested_language if isinstance(requested_language, str) else case.language
                )
                memory_read = await ControlledMemoryService(
                    session,
                    store=PostgresControlledMemoryStore(settings.langgraph_store_url()),
                ).presentation_context_for_drafting(
                    context,
                    requested_language=language,
                    explicit_language=run.state_snapshot.get("language_explicit") is True,
                )
                if (
                    memory_read.presentation.language is not None
                    and run.state_snapshot.get("language_explicit") is not True
                ):
                    language = memory_read.presentation.language
                first_source = evidence.sources[0]
                fixture = {
                    "drafting_response": {
                        # The deterministic fixture must satisfy the same citation-support
                        # guard as a provider response, even when local browser runs retain
                        # prior synthetic source documents in the database.
                        "draft": f"{first_source.excerpt.strip()} [{first_source.citation_label}]",
                        "language": language.value,
                    }
                }
                graph = DraftingGraph(
                    DraftingGraphDependencies(
                        case_input=DraftingCaseInput(case.title, case.description, language),
                        evidence_sources=tuple(
                            DraftingEvidenceSource(
                                citation_label=source.citation_label,
                                chunk_id=source.chunk_id,
                                excerpt=source.excerpt,
                            )
                            for source in evidence.sources
                        ),
                        prompt_loader=SqlAlchemyPromptLoader(session),
                        model_provider=build_model_provider(
                            agent_settings,
                            deterministic_fixtures=(
                                fixture if agent_settings.provider == "deterministic" else None
                            ),
                        ),
                        persistence=persistence,
                        persist_draft=lambda graph_context, state, draft: persist_draft(
                            session, graph_context, state, draft
                        ),
                        retry_policy=RetryPolicy(
                            maximum_retries=agent_settings.node_maximum_retries
                        ),
                        presentation_memory=memory_read.presentation,
                    )
                )
                result = await graph.run(
                    context,
                    DraftingWorkflowState(
                        context=context,
                        target_language=language.value,
                        memory_enabled=memory_read.memory_enabled,
                        memory_considered_count=memory_read.considered_count,
                        memory_applied_count=memory_read.applied_count,
                        memory_outcome_codes=memory_read.outcome_codes,
                    ),
                )
                await session.commit()
                return result.outcome.status.value
            except Exception:
                if await persistence.claim_run(context):
                    await persistence.fail_run(
                        context,
                        state_snapshot={
                            "workflow_name": context.workflow_name,
                            "workflow_version": context.workflow_version,
                            "state_schema_version": "v1",
                            "status": "failed",
                            "evidence_available": True,
                            "draft_available": False,
                        },
                        duration_ms=0,
                        error_code="workflow_configuration_unavailable",
                    )
                    await session.commit()
                return "failed"
    finally:
        await dispose_database_engines()


async def _process_risk_compliance_workflow(workflow_run_id: UUID, settings: AppSettings) -> str:
    """Reload one queued risk run and assess only revalidated persisted signals."""

    try:
        async with get_sessionmaker(settings)() as session:
            run = await session.scalar(select(WorkflowRun).where(WorkflowRun.id == workflow_run_id))
            if run is None or run.workflow_name != RISK_WORKFLOW_NAME or run.status != "queued":
                return "noop"
            context = WorkflowContext(
                workflow_run_id=run.id,
                organization_id=run.organization_id,
                case_id=run.case_id,
                initiated_by_user_id=run.started_by_user_id,
                workflow_name=run.workflow_name,
                workflow_version=run.workflow_version,
            )
            case = await CaseRepository(session).get(context.organization_id, context.case_id)
            user = await UserRepository(session).get(
                context.organization_id, context.initiated_by_user_id
            )
            persistence = SqlAlchemyWorkflowPersistence(session)
            if case is None or user is None or not user.is_active:
                if await persistence.claim_run(context):
                    await persistence.fail_run(
                        context,
                        state_snapshot={
                            "workflow_name": context.workflow_name,
                            "workflow_version": context.workflow_version,
                            "state_schema_version": "v1",
                            "status": "failed",
                        },
                        duration_ms=0,
                        error_code="case_not_available",
                    )
                    await session.commit()
                return "failed"
            prerequisites = await load_risk_prerequisites(
                session, context.organization_id, context.case_id
            )
            if prerequisites is None:
                if await persistence.claim_run(context):
                    await persistence.complete_run(
                        context,
                        status=RuntimeStatus.NEEDS_MORE_EVIDENCE,
                        state_snapshot={
                            "workflow_name": context.workflow_name,
                            "workflow_version": context.workflow_version,
                            "state_schema_version": "v1",
                            "status": "needs_more_evidence",
                        },
                        duration_ms=0,
                    )
                    await session.commit()
                return "needs_more_evidence"
            try:
                agent_settings = AgentSettings()
                graph = RiskGraph(
                    RiskGraphDependencies(
                        signals=prerequisites.signals,
                        persistence=persistence,
                        persist_assessment=lambda graph_context, state, result: (
                            persist_risk_assessment(session, graph_context, state, result)
                        ),
                        retry_policy=RetryPolicy(
                            maximum_retries=agent_settings.node_maximum_retries
                        ),
                    )
                )
                result = await graph.run(context, RiskWorkflowState(context=context))
                approval_run = None
                if (
                    result.outcome.status is RuntimeStatus.COMPLETED
                    and result.state.approval_required
                ):
                    approval_run = await ApprovalWorkflowService(session).create_required_run(
                        context
                    )
                await session.commit()
                if approval_run is not None:
                    try:
                        CeleryWorkflowTaskDispatcher().dispatch_human_approval(approval_run.id)
                    except Exception:
                        _logger.warning("approval.workflow_dispatch_unavailable")
                return result.outcome.status.value
            except Exception:
                if await persistence.claim_run(context):
                    await persistence.fail_run(
                        context,
                        state_snapshot={
                            "workflow_name": context.workflow_name,
                            "workflow_version": context.workflow_version,
                            "state_schema_version": "v1",
                            "status": "failed",
                        },
                        duration_ms=0,
                        error_code="workflow_configuration_unavailable",
                    )
                    await session.commit()
                return "failed"
    finally:
        await dispose_database_engines()


async def _process_human_approval_workflow(workflow_run_id: UUID, settings: AppSettings) -> str:
    """Run the initial approval interruption or one UUID-only persisted reviewer resume."""

    try:
        async with get_sessionmaker(settings)() as session:
            run = await session.scalar(select(WorkflowRun).where(WorkflowRun.id == workflow_run_id))
            if (
                run is None
                or run.workflow_name != "human_approval"
                or run.status not in {"queued", "waiting_for_human_review"}
            ):
                return "noop"
            context = WorkflowContext(
                workflow_run_id=run.id,
                organization_id=run.organization_id,
                case_id=run.case_id,
                initiated_by_user_id=run.started_by_user_id,
                workflow_name=run.workflow_name,
                workflow_version=run.workflow_version,
            )
            persistence = SqlAlchemyWorkflowPersistence(session)
            service = ApprovalWorkflowService(session)
            graph = ApprovalGraph(
                ApprovalGraphDependencies(
                    persistence=persistence,
                    prepare_review_packet=service.prepare_review_packet,
                    mark_interrupted=service.mark_interrupted,
                    load_decision=service.load_decision,
                    resolve_decision=service.resolve_decision,
                    retry_policy=RetryPolicy(maximum_retries=AgentSettings().node_maximum_retries),
                )
            )
            if run.status == "queued":
                result = await graph.run_initial(context, ApprovalWorkflowState(context=context))
            else:
                approval = await service.approval_for_workflow(
                    context.organization_id, context.workflow_run_id
                )
                if approval is None:
                    return "noop"
                result = await graph.run_resume(
                    context,
                    ApprovalWorkflowState(
                        context=context,
                        status=RuntimeStatus.WAITING_FOR_HUMAN_REVIEW,
                        approval_id=approval.id,
                    ),
                )
            await session.commit()
            return result.outcome.status.value
    finally:
        await dispose_database_engines()


def _retry_delay(retries: int) -> int:
    """Small finite exponential backoff suitable for local and production-like queues."""

    return min(60, 1 << (retries + 1))


async def _process_document(document_id: UUID, settings: AppSettings) -> ParseProcessOutcome:
    storage = AzureBlobObjectStorage(
        connection_string=settings.object_storage_connection_string_value(),
        container=settings.object_storage_container,
    )
    try:
        async with get_sessionmaker(settings)() as session:
            coordinator = DocumentParseCoordinator(
                session,
                storage=storage,
                registry=DocumentParserRegistry(
                    maximum_characters=settings.document_parser_max_extracted_characters,
                    maximum_sections=settings.document_parser_max_sections,
                ),
                maximum_input_bytes=settings.document_parser_max_input_bytes,
                language_minimum_characters=settings.document_language_minimum_characters,
                language_confidence_threshold=settings.document_language_confidence_threshold,
            )
            return await coordinator.process(document_id)
    finally:
        await storage.close()
        # Celery invokes each task through ``asyncio.run``. Dispose the
        # loop-bound asyncpg pool before that event loop closes so the next task
        # never inherits a connection from a previous loop.
        await dispose_database_engines()


async def _mark_exhausted(document_id: UUID, settings: AppSettings) -> None:
    storage = AzureBlobObjectStorage(
        connection_string=settings.object_storage_connection_string_value(),
        container=settings.object_storage_container,
    )
    try:
        async with get_sessionmaker(settings)() as session:
            coordinator = DocumentParseCoordinator(
                session,
                storage=storage,
                registry=DocumentParserRegistry(
                    maximum_characters=settings.document_parser_max_extracted_characters,
                    maximum_sections=settings.document_parser_max_sections,
                ),
                maximum_input_bytes=settings.document_parser_max_input_bytes,
                language_minimum_characters=settings.document_language_minimum_characters,
                language_confidence_threshold=settings.document_language_confidence_threshold,
            )
            await coordinator.mark_exhausted_retry(document_id)
    finally:
        await storage.close()
        await dispose_database_engines()


def _index_coordinator(session: AsyncSession, settings: AppSettings) -> DocumentIndexCoordinator:
    """Build short-lived tokenizer/provider adapters only inside a worker task."""

    try:
        provider = build_embedding_provider(settings)
    except EmbeddingError as error:
        # The coordinator still claims the durable row before safely recording a
        # permanent configuration failure; no provider details are persisted.
        provider = FailingEmbeddingProvider(error)
    return DocumentIndexCoordinator(
        session,
        chunker=CanonicalTextChunker(
            tokenizer=TiktokenTokenizer(settings.embedding_tokenizer_encoding),
            config=ChunkingConfig(
                maximum_tokens=settings.document_chunk_max_tokens,
                overlap_tokens=settings.document_chunk_overlap_tokens,
                maximum_chunks=settings.document_chunk_maximum_count,
                configuration_version=settings.embedding_configuration_version,
                embedding_model=settings.embedding_model,
            ),
        ),
        provider=provider,
        embedding_batch_size=settings.embedding_batch_size,
        model_label=settings.embedding_model,
    )


async def _process_index_document(document_id: UUID, settings: AppSettings) -> IndexProcessOutcome:
    coordinator: DocumentIndexCoordinator | None = None
    try:
        async with get_sessionmaker(settings)() as session:
            coordinator = _index_coordinator(session, settings)
            return await coordinator.process(document_id)
    finally:
        if coordinator is not None:
            await coordinator.provider.aclose()
        await dispose_database_engines()


async def _mark_index_exhausted(document_id: UUID, settings: AppSettings) -> None:
    coordinator: DocumentIndexCoordinator | None = None
    try:
        async with get_sessionmaker(settings)() as session:
            coordinator = _index_coordinator(session, settings)
            await coordinator.mark_exhausted_retry(document_id)
    finally:
        if coordinator is not None:
            await coordinator.provider.aclose()
        await dispose_database_engines()


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="app.workers.tasks.parse_document_task",
    acks_late=True,
    ignore_result=True,
)
@instrument_celery_task("document.parse")
def parse_document_task(task: Task, document_id: str) -> str:
    """Parse one UUID-only message with explicit transient retry behavior."""

    try:
        parsed_id = UUID(document_id)
    except ValueError:
        _logger.warning("document.task_invalid_identifier")
        return ParseProcessOutcome.NOOP.value
    settings = get_settings()
    try:
        outcome = asyncio.run(_process_document(parsed_id, settings))
    except Exception as error:
        _logger.warning("document.task_runtime_unavailable", error_type=type(error).__name__)
        outcome = ParseProcessOutcome.TRANSIENT_FAILURE
    if outcome == ParseProcessOutcome.PARSED:
        try:
            # Parsing committed the pending indexing state before this best-effort
            # publication. The reconciler recovers a broker outage safely.
            CeleryDocumentTaskDispatcher().dispatch_index(parsed_id)
        except Exception as error:
            _logger.warning("document.index_dispatch_unavailable", error_type=type(error).__name__)
    if outcome != ParseProcessOutcome.TRANSIENT_FAILURE:
        return outcome.value
    if task.request.retries >= settings.document_parser_task_max_retries:
        try:
            asyncio.run(_mark_exhausted(parsed_id, settings))
        except Exception as error:
            _logger.warning("document.task_exhaustion_unavailable", error_type=type(error).__name__)
        return ParseProcessOutcome.PERMANENT_FAILURE.value
    raise task.retry(countdown=_retry_delay(task.request.retries))


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="app.workers.tasks.index_document_task",
    acks_late=True,
    ignore_result=True,
)
@instrument_celery_task("document.index")
def index_document_task(task: Task, document_id: str) -> str:
    """Index one UUID-only message with explicit bounded retry behavior."""

    try:
        parsed_id = UUID(document_id)
    except ValueError:
        _logger.warning("document.index_task_invalid_identifier")
        return IndexProcessOutcome.NOOP.value
    settings = get_settings()
    try:
        outcome = asyncio.run(_process_index_document(parsed_id, settings))
    except Exception as error:
        _logger.warning("document.index_task_runtime_unavailable", error_type=type(error).__name__)
        outcome = IndexProcessOutcome.TRANSIENT_FAILURE
    if outcome != IndexProcessOutcome.TRANSIENT_FAILURE:
        return outcome.value
    if task.request.retries >= settings.document_indexer_task_max_retries:
        try:
            asyncio.run(_mark_index_exhausted(parsed_id, settings))
        except Exception as error:
            _logger.warning(
                "document.index_task_exhaustion_unavailable", error_type=type(error).__name__
            )
        return IndexProcessOutcome.PERMANENT_FAILURE.value
    raise task.retry(countdown=_retry_delay(task.request.retries))


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="app.workers.tasks.run_intake_workflow_task",
    acks_late=True,
    ignore_result=True,
)
@instrument_celery_task("workflow.intake")
def run_intake_workflow_task(task: Task, workflow_run_id: str) -> str:
    """Execute one UUID-only Intake task with bounded infrastructure retries."""

    try:
        parsed_id = UUID(workflow_run_id)
    except ValueError:
        _logger.warning("workflow.intake_task_invalid_identifier")
        return "noop"
    settings = get_settings()
    try:
        outcome = asyncio.run(_process_intake_workflow(parsed_id, settings))
    except Exception as error:
        _logger.warning("workflow.intake_task_runtime_unavailable", error_type=type(error).__name__)
        if task.request.retries >= settings.document_parser_task_max_retries:
            return "failed"
        raise task.retry(countdown=_retry_delay(task.request.retries)) from error
    return outcome


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="app.workers.tasks.run_evidence_workflow_task",
    acks_late=True,
    ignore_result=True,
)
@instrument_celery_task("workflow.evidence")
def run_evidence_workflow_task(task: Task, workflow_run_id: str) -> str:
    """Execute one UUID-only Evidence task with the existing finite retry boundary."""

    try:
        parsed_id = UUID(workflow_run_id)
    except ValueError:
        _logger.warning("workflow.evidence_task_invalid_identifier")
        return "noop"
    settings = get_settings()
    try:
        outcome = asyncio.run(_process_evidence_workflow(parsed_id, settings))
    except Exception as error:
        _logger.warning(
            "workflow.evidence_task_runtime_unavailable", error_type=type(error).__name__
        )
        if task.request.retries >= settings.document_parser_task_max_retries:
            return "failed"
        raise task.retry(countdown=_retry_delay(task.request.retries)) from error
    return outcome


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="app.workers.tasks.run_extraction_workflow_task",
    acks_late=True,
    ignore_result=True,
)
@instrument_celery_task("workflow.extraction")
def run_extraction_workflow_task(task: Task, workflow_run_id: str) -> str:
    """Execute one UUID-only Extraction task with bounded infrastructure retries."""

    try:
        parsed_id = UUID(workflow_run_id)
    except ValueError:
        _logger.warning("workflow.extraction_task_invalid_identifier")
        return "noop"
    settings = get_settings()
    try:
        outcome = asyncio.run(_process_extraction_workflow(parsed_id, settings))
    except Exception as error:
        _logger.warning(
            "workflow.extraction_task_runtime_unavailable", error_type=type(error).__name__
        )
        if task.request.retries >= settings.document_parser_task_max_retries:
            return "failed"
        raise task.retry(countdown=_retry_delay(task.request.retries)) from error
    return outcome


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="app.workers.tasks.run_drafting_workflow_task",
    acks_late=True,
    ignore_result=True,
)
@instrument_celery_task("workflow.drafting")
def run_drafting_workflow_task(task: Task, workflow_run_id: str) -> str:
    """Execute one UUID-only Drafting task with bounded infrastructure retries."""

    try:
        parsed_id = UUID(workflow_run_id)
    except ValueError:
        _logger.warning("workflow.drafting_task_invalid_identifier")
        return "noop"
    settings = get_settings()
    try:
        outcome = asyncio.run(_process_drafting_workflow(parsed_id, settings))
    except Exception as error:
        _logger.warning(
            "workflow.drafting_task_runtime_unavailable", error_type=type(error).__name__
        )
        if task.request.retries >= settings.document_parser_task_max_retries:
            return "failed"
        raise task.retry(countdown=_retry_delay(task.request.retries)) from error
    return outcome


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="app.workers.tasks.run_risk_compliance_workflow_task",
    acks_late=True,
    ignore_result=True,
)
@instrument_celery_task("workflow.risk_compliance")
def run_risk_compliance_workflow_task(task: Task, workflow_run_id: str) -> str:
    """Execute one UUID-only risk task with the established bounded retry boundary."""

    try:
        parsed_id = UUID(workflow_run_id)
    except ValueError:
        _logger.warning("workflow.risk_compliance_task_invalid_identifier")
        return "noop"
    settings = get_settings()
    try:
        outcome = asyncio.run(_process_risk_compliance_workflow(parsed_id, settings))
    except Exception as error:
        _logger.warning(
            "workflow.risk_compliance_task_runtime_unavailable", error_type=type(error).__name__
        )
        if task.request.retries >= settings.document_parser_task_max_retries:
            return "failed"
        raise task.retry(countdown=_retry_delay(task.request.retries)) from error
    return outcome


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="app.workers.tasks.run_human_approval_workflow_task",
    acks_late=True,
    ignore_result=True,
)
@instrument_celery_task("workflow.approval")
def run_human_approval_workflow_task(task: Task, workflow_run_id: str) -> str:
    """Execute one UUID-only approval interruption/resume task with finite retries."""

    try:
        parsed_id = UUID(workflow_run_id)
    except ValueError:
        _logger.warning("approval.workflow_task_invalid_identifier")
        return "noop"
    settings = get_settings()
    try:
        outcome = asyncio.run(_process_human_approval_workflow(parsed_id, settings))
    except Exception as error:
        _logger.warning(
            "approval.workflow_task_runtime_unavailable", error_type=type(error).__name__
        )
        if task.request.retries >= settings.document_parser_task_max_retries:
            return "failed"
        raise task.retry(countdown=_retry_delay(task.request.retries)) from error
    return outcome


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="app.workers.tasks.run_evaluation_task",
    acks_late=True,
    ignore_result=True,
)
@instrument_celery_task("evaluation.run")
def run_evaluation_task(task: Task, evaluation_run_id: str) -> str:
    """Execute a UUID-only evaluation task with finite infrastructure retries."""

    try:
        parsed_id = UUID(evaluation_run_id)
    except ValueError:
        _logger.warning("evaluation.task_invalid_identifier")
        return "noop"
    settings = get_settings()
    try:
        return asyncio.run(_process_evaluation(parsed_id, settings))
    except Exception as error:
        _logger.warning("evaluation.task_runtime_unavailable", error_type=type(error).__name__)
        if task.request.retries >= settings.document_parser_task_max_retries:
            asyncio.run(_fail_evaluation(parsed_id, settings))
            return "failed"
        raise task.retry(countdown=_retry_delay(task.request.retries)) from error


async def _reconcile(settings: AppSettings) -> tuple[tuple[UUID, ...], tuple[UUID, ...]]:
    try:
        async with get_sessionmaker(settings)() as session:
            repository = DocumentRepository(session)
            async with session.begin():
                await repository.recover_stale_claims(
                    before=datetime.now(UTC)
                    - timedelta(seconds=settings.document_parser_processing_lease_seconds)
                )
                await repository.recover_stale_index_claims(
                    before=datetime.now(UTC)
                    - timedelta(seconds=settings.document_indexer_processing_lease_seconds)
                )
            parser_candidates = await repository.get_processing_candidates(
                limit=_RECONCILIATION_LIMIT
            )
            index_candidates = await repository.get_indexing_candidates(limit=_RECONCILIATION_LIMIT)
            return (
                tuple(document.id for document in parser_candidates),
                tuple(document.id for document in index_candidates),
            )
    finally:
        await dispose_database_engines()


@celery_app.task(  # type: ignore[untyped-decorator]
    name="app.workers.tasks.reconcile_document_tasks", ignore_result=True
)
def reconcile_document_tasks() -> int:
    """Resubmit bounded parsing/indexing work after publish failures or stale claims."""

    settings = get_settings()
    try:
        parser_document_ids, index_document_ids = asyncio.run(_reconcile(settings))
        dispatcher = CeleryDocumentTaskDispatcher()
        for document_id in parser_document_ids:
            dispatcher.dispatch_parse(document_id)
        for document_id in index_document_ids:
            dispatcher.dispatch_index(document_id)
        return len(parser_document_ids) + len(index_document_ids)
    except Exception as error:
        _logger.warning("document.reconciliation_unavailable", error_type=type(error).__name__)
        return 0
