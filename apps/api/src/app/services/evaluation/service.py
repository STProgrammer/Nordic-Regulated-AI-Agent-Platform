"""Canonical dataset loading and safe tenant-scoped evaluation execution history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from evaluation.contracts import (
    CANONICAL_DATASET_KEYS,
    dataset_content_hash,
    load_canonical_dataset,
)
from evaluation.runners import EvaluationRunReport, evaluate_dataset
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.observability import get_telemetry
from app.db.models.evaluation import EvalCase, EvalDataset, EvalResult, EvalRun
from app.db.repositories.evaluation import (
    EvaluationRepository,
    EvaluationResultSnapshot,
    EvaluationRunSnapshot,
)
from app.services.audit.service import AuditEventCreate, AuditService
from app.services.auth.policy import EvaluationAction, authorize_evaluation_action
from app.services.auth.principal import Principal
from app.services.common.pagination import Page, Pagination
from app.services.common.persistence import stage_write
from app.services.errors import ConflictError, EvaluationUnavailableError, NotFoundError
from app.services.evaluation.dispatch import EvaluationTaskDispatcher
from app.services.evaluation.reporting import (
    EvaluationResultProjection,
    EvaluationRunProjection,
    project_result,
    project_run,
    render_markdown_report,
)

_TERMINAL_STATUSES = frozenset({"completed", "failed"})


@dataclass(frozen=True)
class CanonicalDatasetRecord:
    """Safe global dataset identity exposed to authenticated operators."""

    dataset: EvalDataset


class EvaluationService:
    """Own canonical materialization, Admin operations, and idempotent worker execution."""

    def __init__(
        self, session: AsyncSession, *, dispatcher: EvaluationTaskDispatcher | None = None
    ) -> None:
        self._session = session
        self._records = EvaluationRepository(session)
        self._audit = AuditService(session)
        self._dispatcher = dispatcher

    async def list_canonical_datasets(
        self, principal: Principal
    ) -> tuple[CanonicalDatasetRecord, ...]:
        authorize_evaluation_action(principal, EvaluationAction.READ)
        await self._ensure_all_canonical_datasets()
        return tuple(
            CanonicalDatasetRecord(item) for item in await self._records.list_canonical_datasets()
        )

    async def start(self, principal: Principal, *, dataset_key: str) -> EvaluationRunProjection:
        """Queue one server-selected canonical dataset run for the current organization."""

        authorize_evaluation_action(principal, EvaluationAction.START)
        dataset = await self._ensure_canonical_dataset(dataset_key)
        if await self._records.get_active_run(principal.organization_id, dataset.id) is not None:
            raise ConflictError("Evaluation run")
        run = EvalRun(
            organization_id=principal.organization_id,
            eval_dataset_id=dataset.id,
            dataset_version=dataset.dataset_version,
            dataset_content_hash=dataset.content_hash,
            run_name=f"{dataset.dataset_key}-{dataset.dataset_version}",
            status="queued",
            started_at=datetime.now(UTC),
            summary_metrics={},
            pass_fail="pending",
        )
        await stage_write(
            self._session, lambda: self._records.create_run(run), resource="Evaluation run"
        )
        await self._audit.record_event(
            AuditEventCreate(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="evaluation.run_requested",
                resource_type="evaluation_run",
                resource_id=run.id,
                event_data={
                    "dataset_key": dataset.dataset_key,
                    "dataset_version": dataset.dataset_version,
                    "status": "queued",
                },
            )
        )
        await self._session.commit()
        if self._dispatcher is not None:
            try:
                self._dispatcher.dispatch_evaluation(run.id)
            except Exception as error:
                await self._mark_dispatch_failed(run, principal)
                raise EvaluationUnavailableError() from error
        return project_run(run, dataset_key=dataset.dataset_key, results=())

    async def list_runs(
        self, principal: Principal, *, pagination: Pagination, status: str | None = None
    ) -> Page[EvaluationRunProjection]:
        authorize_evaluation_action(principal, EvaluationAction.READ)
        page = await self._records.list_runs(
            principal.organization_id, pagination=pagination, status=status
        )
        snapshots = await self._records.list_result_snapshots(
            tuple(item.run.id for item in page.items)
        )
        by_run_id: dict[UUID, list[EvaluationResultSnapshot]] = {}
        for snapshot in snapshots:
            by_run_id.setdefault(snapshot.result.eval_run_id, []).append(snapshot)
        return Page(
            items=tuple(
                self._project_snapshot(item, by_run_id.get(item.run.id, [])) for item in page.items
            ),
            limit=page.limit,
            offset=page.offset,
            total=page.total,
        )

    async def get_run(self, principal: Principal, run_id: UUID) -> EvaluationRunProjection:
        authorize_evaluation_action(principal, EvaluationAction.READ)
        return await self._get_run_projection(principal.organization_id, run_id)

    async def get_result(
        self, principal: Principal, run_id: UUID, result_id: UUID
    ) -> EvaluationResultProjection:
        """Read one safe result only after proving its parent run is tenant-owned."""

        authorize_evaluation_action(principal, EvaluationAction.READ)
        snapshot = await self._records.get_run(principal.organization_id, run_id)
        if snapshot is None:
            raise NotFoundError("Evaluation run")
        result = await self._records.get_result_snapshot(snapshot.run.id, result_id)
        if result is None:
            raise NotFoundError("Evaluation result")
        return project_result(result.result, case_key=result.case_key)

    async def export_report(self, principal: Principal, run_id: UUID, *, locale: str) -> str:
        """Render and audit one current-tenant Markdown report after Admin authorization."""

        authorize_evaluation_action(principal, EvaluationAction.EXPORT)
        projection = await self._get_run_projection(principal.organization_id, run_id)
        report = render_markdown_report(projection, locale=locale)
        await self._audit.record_event(
            AuditEventCreate(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="evaluation.report_exported",
                resource_type="evaluation_run",
                resource_id=projection.evaluation_run_id,
                event_data={
                    "dataset_key": projection.dataset_key,
                    "dataset_version": projection.dataset_version,
                    "format": "markdown",
                },
            )
        )
        await self._session.commit()
        return report

    async def execute(self, run_id: UUID) -> str:
        """Reload and complete one queued run; repeated delivery is a harmless no-op."""

        run = await self._records.get_run_for_update(run_id)
        if run is None or run.status != "queued" or run.organization_id is None:
            return "noop"
        organization_id = run.organization_id
        dataset = await self._records.get_dataset_by_id(run.eval_dataset_id)
        if dataset is None:
            await self._mark_worker_failed(run, "dataset_not_available")
            await self._session.commit()
            return "failed"
        try:
            canonical = load_canonical_dataset(dataset.dataset_key)
        except ValueError:
            await self._mark_worker_failed(run, "dataset_not_available")
            await self._session.commit()
            return "failed"
        if (
            canonical.version != run.dataset_version
            or dataset_content_hash(canonical) != run.dataset_content_hash
            or dataset.content_hash != run.dataset_content_hash
        ):
            await self._mark_worker_failed(run, "dataset_identity_mismatch")
            await self._session.commit()
            return "failed"
        cases = {item.case_key: item for item in await self._records.list_cases(dataset.id)}
        if set(cases) != {item.case_key for item in canonical.cases}:
            await self._mark_worker_failed(run, "dataset_cases_unavailable")
            await self._session.commit()
            return "failed"
        try:
            with get_telemetry().span("evaluation.run", {"evaluation.operation": "run"}):
                report = evaluate_dataset(canonical)
        except Exception:
            await self._mark_worker_failed(run, "deterministic_runner_failed")
            await self._session.commit()
            return "failed"
        run.status = "running"
        await self._session.flush()
        for result in report.results:
            await self._records.add_result(
                EvalResult(
                    eval_run_id=run.id,
                    eval_case_id=cases[result.case_key].id,
                    retrieval_score=Decimal(str(result.retrieval_score)),
                    citation_score=Decimal(str(result.citation_score)),
                    faithfulness_score=Decimal(str(result.structural_faithfulness_score)),
                    refusal_score=Decimal(str(result.refusal_score)),
                    risk_score=Decimal(str(result.risk_score)),
                    routing_score=Decimal(str(result.routing_score)),
                    passed=result.passed,
                    failure_reasons={"codes": [code.value for code in result.failure_codes]},
                )
            )
        await self._complete_run(run, dataset, report, organization_id=organization_id)
        await self._session.commit()
        return "completed"

    async def fail_unexpected(self, run_id: UUID) -> None:
        """Safely terminalize a queued/running run after an exhausted worker retry budget."""

        run = await self._records.get_run_for_update(run_id)
        if run is None or run.status in _TERMINAL_STATUSES or run.organization_id is None:
            return
        await self._mark_worker_failed(run, "worker_runtime_unavailable")
        await self._session.commit()

    async def _get_run_projection(
        self, organization_id: UUID, run_id: UUID
    ) -> EvaluationRunProjection:
        snapshot = await self._records.get_run(organization_id, run_id)
        if snapshot is None:
            raise NotFoundError("Evaluation run")
        results = await self._records.list_result_snapshots((snapshot.run.id,))
        return self._project_snapshot(snapshot, results)

    def _project_snapshot(
        self,
        snapshot: EvaluationRunSnapshot,
        results: list[EvaluationResultSnapshot] | tuple[EvaluationResultSnapshot, ...],
    ) -> EvaluationRunProjection:
        return project_run(
            snapshot.run,
            dataset_key=snapshot.dataset_key,
            results=(project_result(item.result, case_key=item.case_key) for item in results),
        )

    async def _ensure_all_canonical_datasets(self) -> None:
        for dataset_key in CANONICAL_DATASET_KEYS:
            await self._ensure_canonical_dataset(dataset_key)

    async def _ensure_canonical_dataset(self, dataset_key: str) -> EvalDataset:
        try:
            canonical = load_canonical_dataset(dataset_key)
        except ValueError as error:
            raise NotFoundError("Evaluation dataset") from error
        content_hash = dataset_content_hash(canonical)
        existing = await self._records.get_canonical_dataset(
            canonical.dataset_key, canonical.version
        )
        if existing is not None:
            if existing.content_hash != content_hash:
                raise ConflictError("Evaluation dataset")
            return existing
        dataset = EvalDataset(
            organization_id=None,
            name=canonical.dataset_key,
            description=canonical.description,
            dataset_key=canonical.dataset_key,
            dataset_version=canonical.version,
            content_hash=content_hash,
            domain="canonical",
            cases=[_persisted_case(item) for item in canonical.cases],
        )
        return await stage_write(
            self._session,
            lambda: self._records.create_dataset(dataset),
            resource="Evaluation dataset",
        )

    async def _complete_run(
        self,
        run: EvalRun,
        dataset: EvalDataset,
        report: EvaluationRunReport,
        *,
        organization_id: UUID,
    ) -> None:
        await self._records.mark_run(
            run,
            status="completed",
            finished_at=datetime.now(UTC),
            summary_metrics=report.safe_summary(),
            pass_fail="pass" if report.passed else "fail",
        )
        await self._audit.record_event(
            AuditEventCreate(
                organization_id=organization_id,
                event_type="evaluation.run_completed",
                resource_type="evaluation_run",
                resource_id=run.id,
                event_data={
                    "dataset_key": dataset.dataset_key,
                    "dataset_version": dataset.dataset_version,
                    "status": "completed",
                    "pass_fail": run.pass_fail,
                    "total_cases": report.total_cases,
                    "passed_cases": report.passed_cases,
                },
            )
        )
        get_telemetry().evaluation_cases(
            passed_cases=report.passed_cases, total_cases=report.total_cases
        )

    async def _mark_dispatch_failed(self, run: EvalRun, principal: Principal) -> None:
        await self._records.mark_run(
            run,
            status="failed",
            finished_at=datetime.now(UTC),
            summary_metrics={"failure_code": "dispatch_unavailable"},
            pass_fail="fail",
        )
        await self._audit.record_event(
            AuditEventCreate(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="evaluation.run_failed",
                resource_type="evaluation_run",
                resource_id=run.id,
                event_data={"status": "failed", "reason_code": "dispatch_unavailable"},
            )
        )
        await self._session.commit()

    async def _mark_worker_failed(self, run: EvalRun, reason_code: str) -> None:
        if run.status in _TERMINAL_STATUSES or run.organization_id is None:
            return
        await self._records.mark_run(
            run,
            status="failed",
            finished_at=datetime.now(UTC),
            summary_metrics={"failure_code": reason_code},
            pass_fail="fail",
        )
        await self._audit.record_event(
            AuditEventCreate(
                organization_id=run.organization_id,
                event_type="evaluation.run_failed",
                resource_type="evaluation_run",
                resource_id=run.id,
                event_data={"status": "failed", "reason_code": reason_code},
            )
        )


def _persisted_case(case: object) -> EvalCase:
    """Store the fixed corpus only; the API never projects its question or fixtures."""

    from evaluation.contracts import EvaluationCase

    if not isinstance(case, EvaluationCase):
        raise TypeError("Evaluation cases must be validated before persistence.")
    return EvalCase(
        case_key=case.case_key,
        input_case={
            "case_key": case.case_key,
            "locale": case.locale.value,
            "domain": case.domain.value,
            "query": case.query,
        },
        expected_behavior={
            "answer_criterion_ids": list(case.expected_answer_criterion_ids),
            "refusal": case.expect_refusal,
            "risk_outcome": case.expected_risk_outcome.value,
            "routing_outcome": case.expected_routing_outcome.value,
        },
        expected_sources={
            "source_keys": list(case.expected_source_keys),
            "citation_keys": list(case.expected_citation_keys),
        },
        expected_risk_level=case.expected_risk_outcome.value,
        tags=[case.locale.value, case.domain.value],
    )
