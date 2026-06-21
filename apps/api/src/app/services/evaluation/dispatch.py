"""UUID-only dispatch boundary for a persisted evaluation run."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.core.observability import inject_trace_headers


class EvaluationTaskDispatcher(Protocol):
    """Submit no corpus, tenant, provider, or threshold data to Celery."""

    def dispatch_evaluation(self, evaluation_run_id: UUID) -> None: ...


class CeleryEvaluationTaskDispatcher:
    """Production task dispatch that sends only the durable run identifier."""

    def dispatch_evaluation(self, evaluation_run_id: UUID) -> None:
        from app.workers.tasks import run_evaluation_task

        run_evaluation_task.apply_async(
            args=[str(evaluation_run_id)], headers=inject_trace_headers()
        )
