"""Persistence-only staging for direct RAG answer records."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.prompt import ModelUsageRecord
from app.db.models.workflow import AgentMessage, RetrievedSource, WorkflowRun


class RagAnswerRepository:
    """Stage trusted RAG records in the caller-owned transaction without policy logic."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_run(self, run: WorkflowRun) -> WorkflowRun:
        self.session.add(run)
        return run

    async def add_source(self, source: RetrievedSource) -> RetrievedSource:
        self.session.add(source)
        return source

    async def add_message(self, message: AgentMessage) -> AgentMessage:
        self.session.add(message)
        return message

    async def add_usage(self, usage: ModelUsageRecord) -> ModelUsageRecord:
        self.session.add(usage)
        return usage
