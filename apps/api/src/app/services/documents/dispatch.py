"""Identifier-only dispatch boundary between request services and Celery."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class DocumentTaskDispatcher(Protocol):
    """Submit one durable document id without raw bytes or storage metadata."""

    def dispatch_parse(self, document_id: UUID) -> None:
        """Queue a document parser task."""

    def dispatch_index(self, document_id: UUID) -> None:
        """Queue a document indexing task."""


class CeleryDocumentTaskDispatcher:
    """Production dispatcher with a deliberately fixed single-argument payload."""

    def dispatch_parse(self, document_id: UUID) -> None:
        from app.workers.tasks import parse_document_task

        parse_document_task.apply_async(args=[str(document_id)])

    def dispatch_index(self, document_id: UUID) -> None:
        from app.workers.tasks import index_document_task

        index_document_task.apply_async(args=[str(document_id)])
