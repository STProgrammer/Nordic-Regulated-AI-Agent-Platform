"""UUID-only task and dedicated queue coverage for deterministic evaluations."""

from __future__ import annotations

from uuid import uuid4

import pytest
from app.core.config import AppSettings
from app.workers import tasks
from app.workers.celery_app import celery_app


def test_evaluation_task_rejects_non_uuid_payload_without_runtime_access() -> None:
    assert tasks.run_evaluation_task.run("not-a-uuid") == "noop"


def test_evaluation_task_passes_only_the_run_uuid_to_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[str] = []

    async def process(run_id: object, _settings: AppSettings) -> str:
        observed.append(str(run_id))
        return "completed"

    monkeypatch.setattr(tasks, "_process_evaluation", process)
    monkeypatch.setattr(tasks, "get_settings", lambda: AppSettings(environment="test"))
    run_id = uuid4()

    assert tasks.run_evaluation_task.run(str(run_id)) == "completed"
    assert observed == [str(run_id)]


def test_evaluation_task_uses_the_dedicated_queue() -> None:
    queues = {queue.name for queue in celery_app.conf.task_queues}

    assert "evaluation" in queues
    assert celery_app.conf.task_routes["app.workers.tasks.run_evaluation_task"] == {
        "queue": "evaluation"
    }
