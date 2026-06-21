"""Focused format tests for server-generated approved-output attachments."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from io import BytesIO, StringIO
from uuid import UUID

from agent_orchestrator.graphs.approval_types import ReviewerDecision
from app.services.approvals.approved_output import (
    ApprovedOutputField,
    ApprovedOutputFormat,
    ApprovedOutputProjection,
    ApprovedOutputSource,
    render_approved_output,
)
from pypdf import PdfReader


def _projection() -> ApprovedOutputProjection:
    return ApprovedOutputProjection(
        approval_id=UUID("11111111-1111-4111-8111-111111111111"),
        approval_workflow_run_id=UUID("22222222-2222-4222-8222-222222222222"),
        case_id=UUID("33333333-3333-4333-8333-333333333333"),
        case_number="CASE-28",
        case_title="Syntetisk norsk sak",
        case_language="nb",
        decision=ReviewerDecision.EDIT_AND_APPROVE,
        approved_at=datetime(2030, 1, 2, 3, 4, tzinfo=UTC),
        content="Godkjent slutttekst med kilde [S1].",
        sources=(
            ApprovedOutputSource(
                citation_label="S1",
                document_title="Godkjent veiledning",
                document_file_type="pdf",
                page_number=4,
                section_title="Vilkår",
            ),
        ),
        extracted_fields=(
            ApprovedOutputField(
                field_name="deadline",
                field_value={"date": "2030-02-01"},
                human_edited=True,
                document_title="Godkjent veiledning",
                page_number=4,
                section_title="Vilkår",
            ),
        ),
    )


def test_json_export_is_server_owned_and_contains_only_approved_projection() -> None:
    rendered = render_approved_output(_projection(), ApprovedOutputFormat.JSON)

    assert rendered.filename == "approved-output.json"
    assert rendered.media_type == "application/json"
    payload = json.loads(rendered.content)
    assert payload["approved_output"]["content"] == "Godkjent slutttekst med kilde [S1]."
    assert payload["sources"] == [
        {
            "citation_label": "S1",
            "document_file_type": "pdf",
            "document_title": "Godkjent veiledning",
            "page_number": 4,
            "section_title": "Vilkår",
        }
    ]
    serialized = rendered.content.decode()
    assert "approval_id" not in serialized
    assert "workflow_run" not in serialized
    assert "reviewer_comment" not in serialized


def test_csv_export_contains_only_structured_fields_and_safe_source_locator() -> None:
    rendered = render_approved_output(_projection(), ApprovedOutputFormat.CSV)

    assert rendered.filename == "approved-output.csv"
    assert rendered.media_type == "text/csv; charset=utf-8"
    rows = list(csv.DictReader(StringIO(rendered.content.decode())))
    assert rows == [
        {
            "case_number": "CASE-28",
            "field_name": "deadline",
            "field_value_json": '{"date": "2030-02-01"}',
            "human_edited": "true",
            "source_document_title": "Godkjent veiledning",
            "source_page_number": "4",
            "source_section_title": "Vilkår",
        }
    ]
    assert "Godkjent slutttekst" not in rendered.content.decode()


def test_markdown_and_pdf_exports_include_approved_output_and_source_reference() -> None:
    projection = _projection()
    markdown = render_approved_output(projection, ApprovedOutputFormat.MARKDOWN)
    pdf = render_approved_output(projection, ApprovedOutputFormat.PDF)

    assert markdown.filename == "approved-output.md"
    assert markdown.media_type == "text/markdown; charset=utf-8"
    assert "Godkjent slutttekst med kilde [S1]." in markdown.content.decode()
    assert "S1 — Godkjent veiledning — page 4 — Vilkår" in markdown.content.decode()

    assert pdf.filename == "approved-output.pdf"
    assert pdf.media_type == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    pdf_text = "\n".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(pdf.content)).pages
    )
    assert "Godkjent slutttekst med kilde [S1]." in pdf_text
    assert "S1" in pdf_text
    assert "Godkjent veiledning" in pdf_text
