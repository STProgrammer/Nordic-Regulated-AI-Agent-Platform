"""Single Redis-backed Celery application for private document parsing."""

from __future__ import annotations

from celery import Celery  # type: ignore[import-untyped]
from kombu import Queue  # type: ignore[import-untyped]

from app.core.config import get_settings

_settings = get_settings()

celery_app = Celery(
    "nordic_document_parser",
    broker=_settings.redis_async_url(),
    include=["app.workers.tasks"],
)
celery_app.conf.update(
    task_default_queue="document-parser",
    task_queues=(Queue("document-parser"), Queue("document-indexer"), Queue("agent-orchestrator")),
    task_routes={
        "app.workers.tasks.parse_document_task": {"queue": "document-parser"},
        "app.workers.tasks.reconcile_document_tasks": {"queue": "document-parser"},
        "app.workers.tasks.index_document_task": {"queue": "document-indexer"},
        "app.workers.tasks.run_intake_workflow_task": {"queue": "agent-orchestrator"},
    },
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_ignore_result=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_concurrency=_settings.document_parser_worker_concurrency,
    task_time_limit=_settings.document_parser_task_timeout_seconds,
    task_soft_time_limit=max(1, _settings.document_parser_task_timeout_seconds - 5),
    task_annotations={
        "app.workers.tasks.index_document_task": {
            "time_limit": _settings.document_indexer_task_timeout_seconds,
            "soft_time_limit": max(1, _settings.document_indexer_task_timeout_seconds - 5),
        }
    },
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "reconcile-document-parser-jobs": {
            "task": "app.workers.tasks.reconcile_document_tasks",
            "schedule": _settings.document_parser_reconciliation_interval_seconds,
            "options": {"queue": "document-parser"},
        }
    },
)
