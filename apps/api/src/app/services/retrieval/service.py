"""Policy-first governed hybrid source retrieval; deliberately not RAG answering."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.case import CaseRepository
from app.db.repositories.retrieval import RetrievalRepository
from app.db.repositories.workflow import WorkflowRunRepository
from app.services.audit.service import AuditEventCreate, AuditService, JSONValue
from app.services.auth.policy import (
    CaseAction,
    RetrievalAction,
    authorize_case_action,
    authorize_retrieval_action,
)
from app.services.auth.principal import Principal
from app.services.documents.embeddings import (
    EmbeddingError,
    EmbeddingProvider,
    validate_embedding_result,
)
from app.services.errors import InvalidCommandError, NotFoundError, RetrievalUnavailableError
from app.services.retrieval.merging import (
    bounded_excerpt,
    merge_candidates,
    warning_codes_for_source_status,
)
from app.services.retrieval.policy import resolve_source_scope
from app.services.retrieval.rewriting import DeterministicQueryRewriter, QueryRewriter
from app.services.retrieval.types import (
    RetrievalRequest,
    RetrievalWorkflowContext,
    RetrievedSource,
)


class RetrievalService:
    """The reusable Phase 13 retrieval boundary for HTTP and future workflows."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        provider_factory: Callable[[], EmbeddingProvider],
        query_rewriter: QueryRewriter | None = None,
        default_result_limit: int,
        maximum_result_limit: int,
        semantic_candidate_limit: int,
        keyword_candidate_limit: int,
        rank_fusion_constant: float,
        maximum_query_characters: int,
        maximum_document_selections: int,
        maximum_excerpt_characters: int,
    ) -> None:
        self.session = session
        self._provider_factory = provider_factory
        self._rewriter = query_rewriter or DeterministicQueryRewriter()
        self._default_result_limit = default_result_limit
        self._maximum_result_limit = maximum_result_limit
        self._semantic_candidate_limit = semantic_candidate_limit
        self._keyword_candidate_limit = keyword_candidate_limit
        self._rank_fusion_constant = rank_fusion_constant
        self._maximum_query_characters = maximum_query_characters
        self._maximum_document_selections = maximum_document_selections
        self._maximum_excerpt_characters = maximum_excerpt_characters
        self._cases = CaseRepository(session)
        self._workflows = WorkflowRunRepository(session)
        self._repository = RetrievalRepository(session)
        self._audit = AuditService(session)

    async def search(
        self,
        principal: Principal,
        request: RetrievalRequest,
        *,
        workflow_context: RetrievalWorkflowContext | None = None,
    ) -> tuple[RetrievedSource, ...]:
        """Return only permitted ranked excerpts and one safe success audit event."""

        authorize_case_action(principal, CaseAction.READ)
        authorize_retrieval_action(principal, RetrievalAction.SEARCH)
        result_limit = self._resolve_result_limit(request.result_limit)
        self._validate_document_selection_count(request.document_ids)
        rewritten = self._rewriter.rewrite(
            request.query, maximum_characters=self._maximum_query_characters
        )
        scope = resolve_source_scope(
            principal,
            requested_statuses=request.source_statuses,
            document_ids=request.document_ids,
        )
        case = await self._cases.get(principal.organization_id, request.case_id)
        if case is None:
            raise NotFoundError("Case")
        await self._repository.validate_document_selection(
            principal.organization_id, request.document_ids
        )
        workflow_run_id = await self._verified_workflow_run_id(
            principal.organization_id,
            case.id,
            workflow_context,
        )

        try:
            query_embedding = await self._embed_query(rewritten.semantic_query)
            semantic_candidates = await self._repository.semantic_candidates(
                query_embedding=query_embedding,
                scope=scope,
                candidate_limit=self._semantic_candidate_limit,
                excerpt_fetch_characters=self._maximum_excerpt_characters + 1,
            )
            keyword_candidates = (
                await self._repository.keyword_candidates(
                    full_text_query=rewritten.full_text_query,
                    scope=scope,
                    candidate_limit=self._keyword_candidate_limit,
                    excerpt_fetch_characters=self._maximum_excerpt_characters + 1,
                )
                if rewritten.full_text_query is not None
                else ()
            )
        except (EmbeddingError, SQLAlchemyError) as error:
            raise RetrievalUnavailableError() from error

        merged_candidates = merge_candidates(
            (*semantic_candidates, *keyword_candidates),
            fusion_constant=self._rank_fusion_constant,
        )
        results = tuple(
            RetrievedSource(
                document_id=item.candidate.document_id,
                document_title=item.candidate.document_title,
                document_file_type=item.candidate.document_file_type,
                chunk_id=item.candidate.chunk_id,
                page_number=item.candidate.page_number,
                section_title=item.candidate.section_title,
                source_status=item.candidate.source_status,
                rank=rank,
                rank_score=item.rank_score,
                retrieval_methods=item.retrieval_methods,
                excerpt=bounded_excerpt(
                    item.candidate.excerpt_content,
                    maximum_characters=self._maximum_excerpt_characters,
                ),
                warning_codes=warning_codes_for_source_status(item.candidate.source_status),
            )
            for rank, item in enumerate(merged_candidates[:result_limit], start=1)
        )
        try:
            await self._record_completed_search(
                principal=principal,
                case_id=case.id,
                workflow_run_id=workflow_run_id,
                requested_statuses=scope.source_statuses,
                selected_document_count=len(scope.document_ids),
                query_length=len(rewritten.semantic_query),
                semantic_candidate_count=len(semantic_candidates),
                keyword_candidate_count=len(keyword_candidates),
                merged_candidate_count=len(merged_candidates),
                returned_result_count=len(results),
                retrieval_methods=(
                    ("semantic", "keyword")
                    if rewritten.full_text_query is not None
                    else ("semantic",)
                ),
            )
        except SQLAlchemyError as error:
            raise RetrievalUnavailableError() from error
        return results

    async def _embed_query(self, query: str) -> list[float]:
        """Generate exactly one finite validated query vector and close the provider."""

        provider = self._provider_factory()
        try:
            try:
                vectors = await provider.embed((query,))
                return validate_embedding_result(vectors, expected_count=1)[0]
            except EmbeddingError:
                raise
            except Exception as error:
                raise EmbeddingError(retryable=True) from error
        finally:
            try:
                await provider.aclose()
            except Exception as error:
                raise EmbeddingError(retryable=True) from error

    async def _verified_workflow_run_id(
        self,
        organization_id: UUID,
        case_id: UUID,
        workflow_context: RetrievalWorkflowContext | None,
    ) -> UUID | None:
        if workflow_context is None:
            return None
        run = await self._workflows.get(organization_id, workflow_context.workflow_run_id)
        if run is None or run.case_id != case_id:
            raise NotFoundError("Workflow run")
        return run.id

    def _resolve_result_limit(self, requested_limit: int | None) -> int:
        result_limit = self._default_result_limit if requested_limit is None else requested_limit
        if result_limit <= 0 or result_limit > self._maximum_result_limit:
            raise InvalidCommandError("The retrieval result limit is out of range.")
        return result_limit

    def _validate_document_selection_count(self, document_ids: tuple[UUID, ...]) -> None:
        if len(document_ids) > self._maximum_document_selections:
            raise InvalidCommandError("Too many documents were selected for retrieval.")
        if len(set(document_ids)) != len(document_ids):
            raise InvalidCommandError("Selected document ids must be unique.")

    async def _record_completed_search(
        self,
        *,
        principal: Principal,
        case_id: UUID,
        workflow_run_id: UUID | None,
        requested_statuses: tuple[str, ...],
        selected_document_count: int,
        query_length: int,
        semantic_candidate_count: int,
        keyword_candidate_count: int,
        merged_candidate_count: int,
        returned_result_count: int,
        retrieval_methods: tuple[str, ...],
    ) -> None:
        """Append allowlisted counters; query/source values never enter audit data."""

        event_data: dict[str, JSONValue] = {
            "requested_source_statuses": list(requested_statuses),
            "selected_document_count": selected_document_count,
            "query_length": query_length,
            "semantic_candidate_count": semantic_candidate_count,
            "keyword_candidate_count": keyword_candidate_count,
            "merged_candidate_count": merged_candidate_count,
            "returned_result_count": returned_result_count,
            "retrieval_methods": list(retrieval_methods),
        }
        await self._audit.record_event(
            AuditEventCreate(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="retrieval.search_completed",
                resource_type="workflow_run" if workflow_run_id is not None else "case",
                resource_id=workflow_run_id if workflow_run_id is not None else case_id,
                case_id=case_id,
                event_data=event_data,
            )
        )
