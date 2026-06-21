"""Scoped persistence for canonical evaluation datasets and tenant execution history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.evaluation import EvalCase, EvalDataset, EvalResult, EvalRun
from app.services.common.pagination import Page, Pagination


@dataclass(frozen=True)
class EvaluationRunSnapshot:
    """A tenant-owned run paired with the safe canonical dataset key."""

    run: EvalRun
    dataset_key: str


@dataclass(frozen=True)
class EvaluationResultSnapshot:
    """A result paired only with its safe logical case key."""

    result: EvalResult
    case_key: str


class EvaluationRepository:
    """Keep every read bound either to a global canonical dataset or one organization."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_canonical_dataset(
        self, dataset_key: str, dataset_version: str
    ) -> EvalDataset | None:
        return cast(
            EvalDataset | None,
            await self.session.scalar(
                select(EvalDataset).where(
                    EvalDataset.organization_id.is_(None),
                    EvalDataset.dataset_key == dataset_key,
                    EvalDataset.dataset_version == dataset_version,
                )
            ),
        )

    async def get_dataset_by_id(self, dataset_id: UUID) -> EvalDataset | None:
        return cast(
            EvalDataset | None,
            await self.session.scalar(
                select(EvalDataset).where(
                    EvalDataset.id == dataset_id, EvalDataset.organization_id.is_(None)
                )
            ),
        )

    async def list_canonical_datasets(self) -> tuple[EvalDataset, ...]:
        statement = (
            select(EvalDataset)
            .where(EvalDataset.organization_id.is_(None))
            .order_by(
                asc(EvalDataset.dataset_key), asc(EvalDataset.dataset_version), asc(EvalDataset.id)
            )
        )
        return tuple((await self.session.scalars(statement)).all())

    async def create_dataset(self, dataset: EvalDataset) -> EvalDataset:
        self.session.add(dataset)
        return dataset

    async def list_cases(self, dataset_id: UUID) -> tuple[EvalCase, ...]:
        statement = (
            select(EvalCase)
            .where(EvalCase.eval_dataset_id == dataset_id)
            .order_by(asc(EvalCase.case_key), asc(EvalCase.id))
        )
        return tuple((await self.session.scalars(statement)).all())

    async def get_run(self, organization_id: UUID, run_id: UUID) -> EvaluationRunSnapshot | None:
        row = (
            await self.session.execute(
                select(EvalRun, EvalDataset.dataset_key)
                .join(EvalDataset, EvalDataset.id == EvalRun.eval_dataset_id)
                .where(
                    EvalRun.organization_id == organization_id,
                    EvalRun.id == run_id,
                )
            )
        ).one_or_none()
        if row is None:
            return None
        run, dataset_key = row
        return EvaluationRunSnapshot(run=run, dataset_key=dataset_key)

    async def get_run_for_update(self, run_id: UUID) -> EvalRun | None:
        return cast(
            EvalRun | None,
            await self.session.scalar(
                select(EvalRun).where(EvalRun.id == run_id).with_for_update()
            ),
        )

    async def get_active_run(self, organization_id: UUID, dataset_id: UUID) -> EvalRun | None:
        return cast(
            EvalRun | None,
            await self.session.scalar(
                select(EvalRun)
                .where(
                    EvalRun.organization_id == organization_id,
                    EvalRun.eval_dataset_id == dataset_id,
                    EvalRun.status.in_(("queued", "running")),
                )
                .order_by(desc(EvalRun.started_at), desc(EvalRun.id))
            ),
        )

    async def create_run(self, run: EvalRun) -> EvalRun:
        self.session.add(run)
        return run

    async def list_runs(
        self, organization_id: UUID, *, pagination: Pagination, status: str | None = None
    ) -> Page[EvaluationRunSnapshot]:
        predicates = [EvalRun.organization_id == organization_id]
        if status is not None:
            predicates.append(EvalRun.status == status)
        total = await self.session.scalar(select(func.count(EvalRun.id)).where(*predicates))
        statement = (
            select(EvalRun, EvalDataset.dataset_key)
            .join(EvalDataset, EvalDataset.id == EvalRun.eval_dataset_id)
            .where(*predicates)
            .order_by(desc(EvalRun.started_at), desc(EvalRun.id))
            .limit(pagination.limit)
            .offset(pagination.offset)
        )
        rows = (await self.session.execute(statement)).all()
        return Page(
            items=tuple(
                EvaluationRunSnapshot(run=run, dataset_key=dataset_key) for run, dataset_key in rows
            ),
            limit=pagination.limit,
            offset=pagination.offset,
            total=int(total or 0),
        )

    async def list_results(self, run_id: UUID) -> tuple[EvalResult, ...]:
        statement = (
            select(EvalResult)
            .join(EvalCase, EvalCase.id == EvalResult.eval_case_id)
            .where(EvalResult.eval_run_id == run_id)
            .order_by(asc(EvalCase.case_key), asc(EvalResult.id))
        )
        return tuple((await self.session.scalars(statement)).all())

    async def list_result_snapshots(
        self, run_ids: tuple[UUID, ...]
    ) -> tuple[EvaluationResultSnapshot, ...]:
        """Load safe result keys for a page of already tenant-scoped runs in one query."""

        if not run_ids:
            return ()
        statement = (
            select(EvalResult, EvalCase.case_key)
            .join(EvalCase, EvalCase.id == EvalResult.eval_case_id)
            .where(EvalResult.eval_run_id.in_(run_ids))
            .order_by(asc(EvalResult.eval_run_id), asc(EvalCase.case_key), asc(EvalResult.id))
        )
        return tuple(
            EvaluationResultSnapshot(result=result, case_key=case_key)
            for result, case_key in (await self.session.execute(statement)).all()
        )

    async def get_result_snapshot(
        self, run_id: UUID, result_id: UUID
    ) -> EvaluationResultSnapshot | None:
        row = (
            await self.session.execute(
                select(EvalResult, EvalCase.case_key)
                .join(EvalCase, EvalCase.id == EvalResult.eval_case_id)
                .where(EvalResult.eval_run_id == run_id, EvalResult.id == result_id)
            )
        ).one_or_none()
        if row is None:
            return None
        result, case_key = row
        return EvaluationResultSnapshot(result=result, case_key=case_key)

    async def result_case_keys(self, run_id: UUID) -> dict[UUID, str]:
        """Resolve only safe logical case keys for an already scoped run projection."""

        rows = (
            await self.session.execute(
                select(EvalResult.id, EvalCase.case_key)
                .join(EvalCase, EvalCase.id == EvalResult.eval_case_id)
                .where(EvalResult.eval_run_id == run_id)
            )
        ).all()
        return {result_id: case_key for result_id, case_key in rows}

    async def add_result(self, result: EvalResult) -> EvalResult:
        self.session.add(result)
        return result

    async def mark_run(
        self,
        run: EvalRun,
        *,
        status: str,
        finished_at: datetime | None,
        summary_metrics: dict[str, object],
        pass_fail: str,
    ) -> EvalRun:
        run.status = status
        run.finished_at = finished_at
        run.summary_metrics = summary_metrics
        run.pass_fail = pass_fail
        return run
