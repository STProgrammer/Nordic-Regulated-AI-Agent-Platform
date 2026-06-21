"""Approved-output exports and deliberately non-network enterprise handoffs."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from io import BytesIO, StringIO
from typing import cast
from uuid import UUID
from xml.sax.saxutils import escape

from agent_orchestrator.graphs.approval_types import ApprovalLifecycle, ReviewerDecision
from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore[import-untyped]
from reportlab.lib.units import mm  # type: ignore[import-untyped]
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer  # type: ignore[import-untyped]
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.case import Case
from app.db.models.document import Document, DocumentChunk
from app.db.models.workflow import (
    Approval,
    ExtractedField,
    RetrievedSource,
    WorkflowRun,
    WorkflowToolCall,
)
from app.db.repositories.workflow import ApprovalRepository, WorkflowToolCallRepository
from app.services.audit.service import AuditEventCreate, AuditService
from app.services.auth.policy import ensure_roles
from app.services.auth.principal import Principal, RoleName
from app.services.errors import ConflictError, NotFoundError


class ApprovedOutputFormat(StrEnum):
    """The fixed, server-owned formats available for one approved output."""

    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"
    PDF = "pdf"


class MockHandoffTarget(StrEnum):
    """The closed set of simulated enterprise destinations."""

    TICKET = "ticket"
    EMAIL = "email"
    TEAMS = "teams"
    ARCHIVE = "archive"


@dataclass(frozen=True)
class ApprovedOutputSource:
    citation_label: str
    document_title: str | None
    document_file_type: str | None
    page_number: int | None
    section_title: str | None


@dataclass(frozen=True)
class ApprovedOutputField:
    field_name: str
    field_value: dict[str, object]
    human_edited: bool
    document_title: str | None
    page_number: int | None
    section_title: str | None


@dataclass(frozen=True)
class ApprovedOutputProjection:
    approval_id: UUID
    approval_workflow_run_id: UUID
    case_id: UUID
    case_number: str
    case_title: str
    case_language: str
    decision: ReviewerDecision
    approved_at: datetime
    content: str
    sources: tuple[ApprovedOutputSource, ...]
    extracted_fields: tuple[ApprovedOutputField, ...]


@dataclass(frozen=True)
class RenderedApprovedOutput:
    content: bytes
    filename: str
    media_type: str


@dataclass(frozen=True)
class MockHandoffRecord:
    approval_id: UUID
    target: MockHandoffTarget
    status: str
    mode: str


class ApprovedOutputService:
    """Own safe exports and metadata-only simulated handoff records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._approvals = ApprovalRepository(session)
        self._audit = AuditService(session)
        self._tool_calls = WorkflowToolCallRepository(session)

    async def export(
        self,
        principal: Principal,
        approval_id: UUID,
        *,
        export_format: ApprovedOutputFormat,
    ) -> RenderedApprovedOutput:
        """Render one complete, approved output before recording its successful export."""

        projection = await self._projection(principal, approval_id)
        rendered = render_approved_output(projection, export_format)
        await self._audit.record_event(
            AuditEventCreate(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="approved_output.exported",
                resource_type="approval",
                resource_id=projection.approval_id,
                case_id=projection.case_id,
                event_data={
                    "format": export_format.value,
                    "source_count": len(projection.sources),
                },
            )
        )
        await self._session.commit()
        return rendered

    async def record_mock_handoff(
        self,
        principal: Principal,
        approval_id: UUID,
        *,
        target: MockHandoffTarget,
    ) -> MockHandoffRecord:
        """Record a mock-only handoff without transport, state changes, or output retention."""

        projection = await self._projection(principal, approval_id)
        recorded_at = datetime.now(UTC)
        await self._tool_calls.create(
            WorkflowToolCall(
                workflow_run_id=projection.approval_workflow_run_id,
                workflow_node_run_id=None,
                tool_name=f"mock_{target.value}_handoff",
                status="completed",
                started_at=recorded_at,
                finished_at=recorded_at,
                duration_ms=0,
                retry_count=0,
                input_summary={
                    "target": target.value,
                    "mode": "mock",
                    "source_count": len(projection.sources),
                },
                output_summary={"status": "recorded", "delivery": "simulated"},
                error_summary=None,
            )
        )
        await self._audit.record_event(
            AuditEventCreate(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="approved_output.mock_handoff_recorded",
                resource_type="approval",
                resource_id=projection.approval_id,
                case_id=projection.case_id,
                event_data={
                    "target": target.value,
                    "mode": "mock",
                    "source_count": len(projection.sources),
                },
            )
        )
        await self._session.commit()
        return MockHandoffRecord(
            approval_id=projection.approval_id,
            target=target,
            status="recorded",
            mode="mock",
        )

    async def _projection(
        self, principal: Principal, approval_id: UUID
    ) -> ApprovedOutputProjection:
        ensure_roles(principal, RoleName.ADMIN, RoleName.COMPLIANCE_REVIEWER)
        approval = await self._approvals.get(principal.organization_id, approval_id)
        if approval is None:
            raise NotFoundError("Approval")
        case = cast(
            Case | None,
            await self._session.scalar(
                select(Case).where(
                    Case.organization_id == principal.organization_id,
                    Case.id == approval.case_id,
                    Case.archived_at.is_(None),
                )
            ),
        )
        run = cast(
            WorkflowRun | None,
            await self._session.scalar(
                select(WorkflowRun).where(
                    WorkflowRun.organization_id == principal.organization_id,
                    WorkflowRun.id == approval.workflow_run_id,
                )
            ),
        )
        if case is None or run is None:
            raise NotFoundError("Approval")
        decision = _approved_decision(approval)
        if (
            decision is None
            or approval.status != ApprovalLifecycle.APPROVED.value
            or case.status != "approved"
            or run.status != "completed"
            or approval.decision_at is None
        ):
            raise ConflictError("Approved output")
        content = _approved_content(approval, decision)
        if content is None:
            raise ConflictError("Approved output")
        sources = await self._sources(principal.organization_id, approval)
        fields = await self._fields(principal.organization_id, case.id)
        return ApprovedOutputProjection(
            approval_id=approval.id,
            approval_workflow_run_id=approval.workflow_run_id,
            case_id=case.id,
            case_number=case.case_number,
            case_title=case.title,
            case_language=case.language,
            decision=decision,
            approved_at=approval.decision_at,
            content=content,
            sources=sources,
            extracted_fields=fields,
        )

    async def _sources(
        self, organization_id: UUID, approval: Approval
    ) -> tuple[ApprovedOutputSource, ...]:
        if approval.drafting_workflow_run_id is None:
            return ()
        document_join = and_(
            Document.id == RetrievedSource.document_id,
            Document.organization_id == RetrievedSource.organization_id,
            Document.source_status == "approved",
            Document.archived_at.is_(None),
        )
        chunk_join = and_(
            DocumentChunk.id == RetrievedSource.chunk_id,
            DocumentChunk.organization_id == RetrievedSource.organization_id,
            Document.id.is_not(None),
        )
        rows = (
            await self._session.execute(
                select(
                    RetrievedSource.citation_label,
                    Document.title,
                    Document.file_type,
                    DocumentChunk.page_number,
                    DocumentChunk.section_title,
                )
                .outerjoin(Document, document_join)
                .outerjoin(DocumentChunk, chunk_join)
                .where(
                    RetrievedSource.organization_id == organization_id,
                    RetrievedSource.case_id == approval.case_id,
                    RetrievedSource.workflow_run_id == approval.drafting_workflow_run_id,
                )
                .order_by(RetrievedSource.rank.asc(), RetrievedSource.id.asc())
            )
        ).all()
        seen: set[str] = set()
        sources: list[ApprovedOutputSource] = []
        for row in rows:
            if row.citation_label in seen:
                continue
            seen.add(row.citation_label)
            sources.append(
                ApprovedOutputSource(
                    citation_label=row.citation_label,
                    document_title=row.title,
                    document_file_type=row.file_type,
                    page_number=row.page_number,
                    section_title=row.section_title,
                )
            )
        return tuple(sources)

    async def _fields(
        self, organization_id: UUID, case_id: UUID
    ) -> tuple[ApprovedOutputField, ...]:
        extraction_run = cast(
            WorkflowRun | None,
            await self._session.scalar(
                select(WorkflowRun)
                .where(
                    WorkflowRun.organization_id == organization_id,
                    WorkflowRun.case_id == case_id,
                    WorkflowRun.workflow_name == "extraction",
                    WorkflowRun.status == "completed",
                )
                .order_by(desc(WorkflowRun.finished_at), desc(WorkflowRun.id))
            ),
        )
        if extraction_run is None:
            return ()
        document_join = and_(
            Document.id == DocumentChunk.document_id,
            Document.organization_id == DocumentChunk.organization_id,
            Document.source_status == "approved",
            Document.archived_at.is_(None),
        )
        rows = (
            await self._session.execute(
                select(
                    ExtractedField.field_name,
                    ExtractedField.field_value,
                    ExtractedField.human_edited,
                    Document.title,
                    DocumentChunk.page_number,
                    DocumentChunk.section_title,
                )
                .outerjoin(
                    DocumentChunk,
                    and_(
                        DocumentChunk.id == ExtractedField.source_chunk_id,
                        DocumentChunk.organization_id == ExtractedField.organization_id,
                    ),
                )
                .outerjoin(Document, document_join)
                .where(
                    ExtractedField.organization_id == organization_id,
                    ExtractedField.case_id == case_id,
                    ExtractedField.workflow_run_id == extraction_run.id,
                )
                .order_by(ExtractedField.inserted_at.asc(), ExtractedField.id.asc())
            )
        ).all()
        return tuple(
            ApprovedOutputField(
                field_name=row.field_name,
                field_value=row.field_value,
                human_edited=bool(row.human_edited),
                document_title=row.title,
                page_number=row.page_number,
                section_title=row.section_title,
            )
            for row in rows
        )


def render_approved_output(
    projection: ApprovedOutputProjection, export_format: ApprovedOutputFormat
) -> RenderedApprovedOutput:
    """Render one fixed-format attachment without writing any artifact to storage."""

    if export_format is ApprovedOutputFormat.JSON:
        return RenderedApprovedOutput(
            content=(
                json.dumps(_json_data(projection), ensure_ascii=False, indent=2, sort_keys=True)
                + "\n"
            ).encode(),
            filename="approved-output.json",
            media_type="application/json",
        )
    if export_format is ApprovedOutputFormat.CSV:
        return RenderedApprovedOutput(
            content=_render_csv(projection).encode(),
            filename="approved-output.csv",
            media_type="text/csv; charset=utf-8",
        )
    if export_format is ApprovedOutputFormat.MARKDOWN:
        return RenderedApprovedOutput(
            content=_render_markdown(projection).encode(),
            filename="approved-output.md",
            media_type="text/markdown; charset=utf-8",
        )
    return RenderedApprovedOutput(
        content=_render_pdf(projection),
        filename="approved-output.pdf",
        media_type="application/pdf",
    )


def _approved_decision(approval: Approval) -> ReviewerDecision | None:
    try:
        decision = ReviewerDecision(approval.decision) if approval.decision is not None else None
    except ValueError:
        return None
    return (
        decision
        if decision in {ReviewerDecision.APPROVE, ReviewerDecision.EDIT_AND_APPROVE}
        else None
    )


def _approved_content(approval: Approval, decision: ReviewerDecision) -> str | None:
    candidate = (
        approval.final_text if decision is ReviewerDecision.EDIT_AND_APPROVE else approval.ai_draft
    )
    if candidate is None:
        return None
    normalized = candidate.strip()
    return normalized or None


def _json_data(projection: ApprovedOutputProjection) -> dict[str, object]:
    return {
        "format_version": "approved-output-v1",
        "case": {
            "number": projection.case_number,
            "title": projection.case_title,
            "language": projection.case_language,
        },
        "approved_output": {
            "decision": projection.decision.value,
            "approved_at": projection.approved_at.isoformat(),
            "content": projection.content,
        },
        "sources": [_source_data(source) for source in projection.sources],
        "extracted_fields": [_field_data(field) for field in projection.extracted_fields],
    }


def _source_data(source: ApprovedOutputSource) -> dict[str, object]:
    return {
        "citation_label": source.citation_label,
        "document_title": source.document_title,
        "document_file_type": source.document_file_type,
        "page_number": source.page_number,
        "section_title": source.section_title,
    }


def _field_data(field: ApprovedOutputField) -> dict[str, object]:
    return {
        "field_name": field.field_name,
        "field_value": field.field_value,
        "human_edited": field.human_edited,
        "source_document_title": field.document_title,
        "source_page_number": field.page_number,
        "source_section_title": field.section_title,
    }


def _render_csv(projection: ApprovedOutputProjection) -> str:
    output = StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=(
            "case_number",
            "field_name",
            "field_value_json",
            "human_edited",
            "source_document_title",
            "source_page_number",
            "source_section_title",
        ),
        lineterminator="\n",
    )
    writer.writeheader()
    for field in projection.extracted_fields:
        writer.writerow(
            {
                "case_number": projection.case_number,
                "field_name": field.field_name,
                "field_value_json": json.dumps(
                    field.field_value, ensure_ascii=False, sort_keys=True
                ),
                "human_edited": str(field.human_edited).lower(),
                "source_document_title": field.document_title or "",
                "source_page_number": field.page_number if field.page_number is not None else "",
                "source_section_title": field.section_title or "",
            }
        )
    return output.getvalue()


def _render_markdown(projection: ApprovedOutputProjection) -> str:
    lines = [
        "# Approved output report",
        "",
        f"- Case: {_markdown(projection.case_number)} — {_markdown(projection.case_title)}",
        f"- Language: {_markdown(projection.case_language)}",
        f"- Decision: `{projection.decision.value}`",
        f"- Approved at: `{projection.approved_at.isoformat()}`",
        "",
        "## Approved output",
        "",
        projection.content,
        "",
        "## Source references",
        "",
    ]
    if projection.sources:
        lines.extend(f"- {_source_label(source)}" for source in projection.sources)
    else:
        lines.append("- No source references are available.")
    lines.extend(("", "## Extracted fields", ""))
    if projection.extracted_fields:
        lines.extend(
            f"- **{_markdown(field.field_name)}**: `{_markdown(_field_value_json(field))}`"
            for field in projection.extracted_fields
        )
    else:
        lines.append("- No extracted fields are available.")
    return "\n".join(lines) + "\n"


def _render_pdf(projection: ApprovedOutputProjection) -> bytes:
    output = BytesIO()
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "ApprovedOutputBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        spaceAfter=3 * mm,
    )
    title = ParagraphStyle("ApprovedOutputTitle", parent=styles["Title"], fontName="Helvetica-Bold")
    heading = ParagraphStyle(
        "ApprovedOutputHeading", parent=styles["Heading2"], fontName="Helvetica-Bold"
    )
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Approved output report",
    )
    story = [
        Paragraph("Approved output report", title),
        Paragraph(
            _pdf_text(
                f"Case: {projection.case_number} — {projection.case_title}<br/>"
                f"Language: {projection.case_language}<br/>"
                f"Decision: {projection.decision.value}<br/>"
                f"Approved at: {projection.approved_at.isoformat()}"
            ),
            body,
        ),
        Spacer(1, 2 * mm),
        Paragraph("Approved output", heading),
        Paragraph(_pdf_text(projection.content), body),
        Paragraph("Source references", heading),
    ]
    if projection.sources:
        story.extend(
            Paragraph(_pdf_text(_source_label(source)), body) for source in projection.sources
        )
    else:
        story.append(Paragraph("No source references are available.", body))
    story.append(Paragraph("Extracted fields", heading))
    if projection.extracted_fields:
        story.extend(
            Paragraph(
                _pdf_text(f"{field.field_name}: {_field_value_json(field)}"),
                body,
            )
            for field in projection.extracted_fields
        )
    else:
        story.append(Paragraph("No extracted fields are available.", body))
    document.build(story)
    return output.getvalue()


def _source_label(source: ApprovedOutputSource) -> str:
    parts = [source.citation_label]
    if source.document_title is not None:
        parts.append(source.document_title)
    if source.page_number is not None:
        parts.append(f"page {source.page_number}")
    if source.section_title is not None:
        parts.append(source.section_title)
    return " — ".join(parts)


def _field_value_json(field: ApprovedOutputField) -> str:
    return json.dumps(field.field_value, ensure_ascii=False, sort_keys=True)


def _markdown(value: str) -> str:
    return value.replace("`", "\\`").replace("\n", " ")


def _pdf_text(value: str) -> str:
    return escape(value).replace("\n", "<br/>")
