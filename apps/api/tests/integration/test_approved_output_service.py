"""PostgreSQL coverage for approved-output exports and simulated handoffs."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from agent_orchestrator.graphs.approval_types import ReviewerDecision
from app.core.config import AppSettings
from app.db.models.audit import AuditEvent
from app.db.models.case import Case
from app.db.models.document import Document, DocumentChunk
from app.db.models.identity import User
from app.db.models.organization import Organization
from app.db.models.workflow import (
    Approval,
    ExtractedField,
    RetrievedSource,
    WorkflowRun,
    WorkflowToolCall,
)
from app.db.session import dispose_database_engines, get_sessionmaker
from app.services.approvals.approved_output import (
    ApprovedOutputFormat,
    ApprovedOutputService,
    MockHandoffTarget,
)
from app.services.auth.principal import Principal, RoleName
from app.services.errors import ConflictError, NotFoundError
from sqlalchemy import select


def test_export_and_mock_handoff_are_tenant_safe_and_content_free(
    database_settings: AppSettings,
) -> None:
    asyncio.run(_exercise_approved_output_service(database_settings))


async def _exercise_approved_output_service(settings: AppSettings) -> None:
    fixture = await _seed(settings)
    sessionmaker = get_sessionmaker(settings)
    try:
        async with sessionmaker() as session:
            service = ApprovedOutputService(session)
            principal = Principal(
                user_id=fixture.user_id,
                organization_id=fixture.organization_id,
                display_name="Synthetic reviewer",
                preferred_language="nb",
                roles=frozenset({RoleName.COMPLIANCE_REVIEWER}),
            )

            for export_format, filename, media_type in (
                (ApprovedOutputFormat.JSON, "approved-output.json", "application/json"),
                (ApprovedOutputFormat.CSV, "approved-output.csv", "text/csv; charset=utf-8"),
                (
                    ApprovedOutputFormat.MARKDOWN,
                    "approved-output.md",
                    "text/markdown; charset=utf-8",
                ),
                (ApprovedOutputFormat.PDF, "approved-output.pdf", "application/pdf"),
            ):
                exported = await service.export(
                    principal, fixture.approval_id, export_format=export_format
                )
                assert exported.filename == filename
                assert exported.media_type == media_type
                if export_format in {ApprovedOutputFormat.JSON, ApprovedOutputFormat.MARKDOWN}:
                    assert b"Synthetic approved final output" in exported.content
                if export_format is ApprovedOutputFormat.CSV:
                    assert b"Synthetic approved final output" not in exported.content
                if export_format is ApprovedOutputFormat.PDF:
                    assert exported.content.startswith(b"%PDF")

            handoff = await service.record_mock_handoff(
                principal, fixture.approval_id, target=MockHandoffTarget.TEAMS
            )
            assert handoff.target is MockHandoffTarget.TEAMS
            assert handoff.status == "recorded"
            assert handoff.mode == "mock"

            events = tuple(
                (
                    await session.scalars(
                        select(AuditEvent)
                        .where(AuditEvent.resource_id == fixture.approval_id)
                        .order_by(AuditEvent.inserted_at.asc(), AuditEvent.id.asc())
                    )
                ).all()
            )
            assert [event.event_type for event in events] == [
                "approved_output.exported",
                "approved_output.exported",
                "approved_output.exported",
                "approved_output.exported",
                "approved_output.mock_handoff_recorded",
            ]
            assert {event.event_data["format"] for event in events[:4]} == {
                "json",
                "csv",
                "markdown",
                "pdf",
            }
            assert all("content" not in event.event_data for event in events)
            assert all("final_text" not in event.event_data for event in events)

            tool_call = await session.scalar(
                select(WorkflowToolCall).where(
                    WorkflowToolCall.workflow_run_id == fixture.approval_workflow_run_id
                )
            )
            assert tool_call is not None
            assert tool_call.tool_name == "mock_teams_handoff"
            assert tool_call.input_summary == {"target": "teams", "mode": "mock", "source_count": 1}
            assert tool_call.output_summary == {"status": "recorded", "delivery": "simulated"}
            assert "Synthetic approved final output" not in repr(tool_call.input_summary)
            assert "Synthetic approved final output" not in repr(tool_call.output_summary)

            foreign_principal = Principal(
                user_id=uuid4(),
                organization_id=uuid4(),
                display_name="Other tenant",
                preferred_language="nb",
                roles=frozenset({RoleName.ADMIN}),
            )
            with pytest.raises(NotFoundError):
                await service.export(
                    foreign_principal,
                    fixture.approval_id,
                    export_format=ApprovedOutputFormat.JSON,
                )
    finally:
        await dispose_database_engines()


def test_non_terminal_approval_cannot_be_exported(database_settings: AppSettings) -> None:
    asyncio.run(_non_terminal_export_is_rejected(database_settings))


async def _non_terminal_export_is_rejected(settings: AppSettings) -> None:
    fixture = await _seed(settings, terminal=False)
    sessionmaker = get_sessionmaker(settings)
    try:
        async with sessionmaker() as session:
            principal = Principal(
                user_id=fixture.user_id,
                organization_id=fixture.organization_id,
                display_name="Synthetic reviewer",
                preferred_language="nb",
                roles=frozenset({RoleName.ADMIN}),
            )
            with pytest.raises(ConflictError):
                await ApprovedOutputService(session).export(
                    principal,
                    fixture.approval_id,
                    export_format=ApprovedOutputFormat.JSON,
                )
    finally:
        await dispose_database_engines()


class _Fixture:
    def __init__(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        approval_id: UUID,
        approval_workflow_run_id: UUID,
    ) -> None:
        self.organization_id = organization_id
        self.user_id = user_id
        self.approval_id = approval_id
        self.approval_workflow_run_id = approval_workflow_run_id


async def _seed(settings: AppSettings, *, terminal: bool = True) -> _Fixture:
    sessionmaker = get_sessionmaker(settings)
    async with sessionmaker() as session, session.begin():
        organization = Organization(
            name="Approved output organization",
            slug=f"approved-output-{uuid4().hex[:12]}",
            default_language="nb",
            retention_policy={},
            settings={},
        )
        session.add(organization)
        await session.flush()
        user = User(
            organization_id=organization.id,
            email=f"reviewer-{uuid4().hex[:10]}@demo.invalid",
            display_name="Synthetic reviewer",
            preferred_language="nb",
            is_active=True,
        )
        session.add(user)
        await session.flush()
        case = Case(
            organization_id=organization.id,
            case_number=f"CASE-{uuid4().hex[:8].upper()}",
            title="Synthetic approved output case",
            description="Synthetic fixture only.",
            language="nb",
            domain="internal_policy",
            priority="normal",
            status="approved" if terminal else "waiting_for_human_review",
            submitted_by_user_id=user.id,
        )
        session.add(case)
        await session.flush()
        now = datetime.now(UTC)
        drafting = WorkflowRun(
            organization_id=organization.id,
            case_id=case.id,
            started_by_user_id=user.id,
            workflow_name="drafting",
            workflow_version="test",
            status="completed",
            started_at=now,
            finished_at=now,
            state_snapshot={},
        )
        extraction = WorkflowRun(
            organization_id=organization.id,
            case_id=case.id,
            started_by_user_id=user.id,
            workflow_name="extraction",
            workflow_version="test",
            status="completed",
            started_at=now,
            finished_at=now,
            state_snapshot={},
        )
        approval_run = WorkflowRun(
            organization_id=organization.id,
            case_id=case.id,
            started_by_user_id=user.id,
            workflow_name="human_approval",
            workflow_version="test",
            status="completed" if terminal else "waiting_for_human_review",
            started_at=now,
            finished_at=now if terminal else None,
            state_snapshot={},
        )
        session.add_all((drafting, extraction, approval_run))
        await session.flush()
        document = Document(
            organization_id=organization.id,
            case_id=case.id,
            uploaded_by_user_id=user.id,
            title="Synthetic approved guidance",
            original_filename="guidance.txt",
            file_type="txt",
            mime_type="text/plain",
            file_size_bytes=1,
            checksum_sha256="a" * 64,
            object_storage_key="synthetic/guidance.txt",
            source_status="approved",
            confidentiality_level="internal",
            parsing_status="parsed",
            indexing_status="indexed",
        )
        session.add(document)
        await session.flush()
        chunk = DocumentChunk(
            organization_id=organization.id,
            document_id=document.id,
            chunk_index=0,
            page_number=2,
            section_title="Synthetic section",
            content="Synthetic source text must not leave the report.",
            token_count=8,
            chunk_metadata={},
            embedding=[0.0] * 1536,
        )
        session.add(chunk)
        await session.flush()
        session.add_all(
            (
                RetrievedSource(
                    organization_id=organization.id,
                    case_id=case.id,
                    workflow_run_id=drafting.id,
                    document_id=document.id,
                    chunk_id=chunk.id,
                    rank=1,
                    score=1,
                    retrieval_method="synthetic",
                    excerpt="Synthetic source text must not leave the report.",
                    citation_label="S1",
                ),
                ExtractedField(
                    organization_id=organization.id,
                    case_id=case.id,
                    workflow_run_id=extraction.id,
                    field_name="deadline",
                    field_value={"date": "2030-01-01"},
                    confidence=1,
                    source_chunk_id=chunk.id,
                    human_edited=True,
                ),
            )
        )
        approval = Approval(
            organization_id=organization.id,
            case_id=case.id,
            workflow_run_id=approval_run.id,
            drafting_workflow_run_id=drafting.id,
            reviewer_user_id=user.id,
            assigned_user_id=user.id,
            status="approved" if terminal else "pending",
            decision=ReviewerDecision.EDIT_AND_APPROVE.value,
            ai_draft="Synthetic unapproved draft",
            final_text="Synthetic approved final output" if terminal else None,
            decision_at=now,
        )
        session.add(approval)
        await session.flush()
        return _Fixture(
            organization_id=organization.id,
            user_id=user.id,
            approval_id=approval.id,
            approval_workflow_run_id=approval_run.id,
        )
