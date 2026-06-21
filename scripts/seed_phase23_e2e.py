"""Seed one synthetic trace/audit fixture for the focused Phase 23 browser check."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
API_SOURCE = ROOT / "apps" / "api" / "src"
if str(API_SOURCE) not in sys.path:
    sys.path.insert(0, str(API_SOURCE))

from app.core.config import get_settings  # noqa: E402
from app.db.models.audit import AuditEvent  # noqa: E402
from app.db.models.case import Case  # noqa: E402
from app.db.models.document import Document, DocumentChunk  # noqa: E402
from app.db.models.identity import User  # noqa: E402
from app.db.models.organization import Organization  # noqa: E402
from app.db.models.prompt import ModelUsageRecord  # noqa: E402
from app.db.models.workflow import (  # noqa: E402
    ExtractedField,
    RetrievedSource,
    WorkflowNodeRun,
    WorkflowRun,
    WorkflowToolCall,
)
from app.db.seed import DEMO_ORGANIZATION_SLUG, seed_local  # noqa: E402
from app.db.session import dispose_database_engines, get_sessionmaker  # noqa: E402
from sqlalchemy import select  # noqa: E402

CASE_WORKER_EMAIL = "kari.eksempel+caseworker@demo.invalid"


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed one Phase 23 browser-test fixture.")
    parser.add_argument("--password-env", metavar="VARIABLE", required=True)
    parser.add_argument("--title-env", metavar="VARIABLE", default="NORDIC_E2E_TRACE_CASE_TITLE")
    return parser.parse_args()


async def main() -> int:
    arguments = _arguments()
    settings = get_settings()
    password = os.getenv(arguments.password_env)
    title = os.getenv(arguments.title_env, "").strip()
    if password is None or not title or len(title) > 255:
        print("Phase 23 E2E seed configuration is unavailable.", file=sys.stderr)
        return 1
    if settings.environment not in {"local", "test"}:
        print("Phase 23 E2E seeding is limited to local and test environments.", file=sys.stderr)
        return 1

    fixture: dict[str, str] | None = None
    try:
        await seed_local(settings, local_password=password)
        sessionmaker = get_sessionmaker(settings)
        async with sessionmaker() as session, session.begin():
            organization = await session.scalar(
                select(Organization).where(Organization.slug == DEMO_ORGANIZATION_SLUG)
            )
            worker = await session.scalar(select(User).where(User.email == CASE_WORKER_EMAIL))
            if organization is None or worker is None:
                raise ValueError("Synthetic trace identities are unavailable.")
            now = datetime.now(UTC)
            case = Case(
                organization_id=organization.id,
                case_number=f"E2E-P23-{uuid4().hex[:12].upper()}",
                title=title,
                description="Synthetic trace fixture without protected content.",
                language="nb",
                domain="internal_policy",
                priority="normal",
                status="processing",
                submitted_by_user_id=worker.id,
                external_reference="phase23-e2e-fixture",
            )
            session.add(case)
            await session.flush()
            document = Document(
                organization_id=organization.id,
                case_id=case.id,
                uploaded_by_user_id=worker.id,
                title="Synthetic governed source",
                original_filename="synthetic-phase23.txt",
                file_type="txt",
                mime_type="text/plain",
                file_size_bytes=64,
                checksum_sha256="0" * 64,
                object_storage_key="local/phase23/synthetic.txt",
                language="nb",
                source_status="approved",
                confidentiality_level="internal",
                page_count=1,
                parsing_status="parsed",
                indexing_status="indexed",
                indexed_at=now,
            )
            session.add(document)
            await session.flush()
            chunk = DocumentChunk(
                organization_id=organization.id,
                document_id=document.id,
                chunk_index=0,
                page_number=1,
                section_title="Synthetic section",
                content="Synthetic bounded context for the Phase 23 browser fixture.",
                token_count=12,
                chunk_metadata={},
                embedding=[0.0] * 1536,
            )
            session.add(chunk)
            run = WorkflowRun(
                organization_id=organization.id,
                case_id=case.id,
                started_by_user_id=worker.id,
                workflow_name="extraction",
                workflow_version="phase23-e2e-v1",
                status="completed",
                started_at=now,
                finished_at=now,
                duration_ms=12,
                total_tokens=30,
                total_cost_estimate=Decimal("0.012000"),
                state_snapshot={
                    "workflow_name": "extraction",
                    "workflow_version": "phase23-e2e-v1",
                    "status": "completed",
                    "evidence_available": True,
                    "extracted_field_count": 1,
                    "hidden_content": "phase23-hidden-sentinel",
                },
            )
            session.add(run)
            await session.flush()
            node = WorkflowNodeRun(
                workflow_run_id=run.id,
                node_name="extract_fields",
                status="completed",
                started_at=now,
                finished_at=now,
                duration_ms=3,
                input_summary={"field_names": ["evidence_available"]},
                output_summary={"counters": {"extracted_field_count": 1}},
                retry_count=0,
            )
            session.add(node)
            await session.flush()
            session.add(
                WorkflowToolCall(
                    workflow_run_id=run.id,
                    workflow_node_run_id=node.id,
                    tool_name="synthetic_tool",
                    status="succeeded",
                    started_at=now,
                    finished_at=now,
                    duration_ms=1,
                    retry_count=0,
                    input_summary={"field_names": ["case_id"]},
                    output_summary={"field_names": ["source_count"]},
                )
            )
            session.add(
                ModelUsageRecord(
                    organization_id=organization.id,
                    case_id=case.id,
                    workflow_run_id=run.id,
                    provider="deterministic",
                    model_name="phase23-fixture",
                    operation="extract_fields",
                    token_input=12,
                    token_output=18,
                    cost_estimate=Decimal("0.012000"),
                    latency_ms=2,
                    success=True,
                )
            )
            session.add(
                RetrievedSource(
                    organization_id=organization.id,
                    case_id=case.id,
                    workflow_run_id=run.id,
                    document_id=document.id,
                    chunk_id=chunk.id,
                    rank=1,
                    score=Decimal("0.90000000"),
                    retrieval_method="semantic",
                    excerpt="phase23-hidden-sentinel",
                    citation_label="S1",
                )
            )
            session.add(
                ExtractedField(
                    organization_id=organization.id,
                    case_id=case.id,
                    workflow_run_id=run.id,
                    field_name="people",
                    field_value={"items": ["Synthetic person"]},
                    confidence=Decimal("0.95000000"),
                    source_chunk_id=chunk.id,
                    human_edited=False,
                )
            )
            session.add(
                AuditEvent(
                    organization_id=organization.id,
                    actor_user_id=worker.id,
                    case_id=case.id,
                    resource_id=run.id,
                    event_type="workflow.extraction_completed",
                    resource_type="workflow_run",
                    event_data={"workflow": "extraction", "status": "completed"},
                )
            )
            fixture = {
                "case_id": str(case.id),
                "event_type": "workflow.extraction_completed",
                "title": case.title,
                "workflow_run_id": str(run.id),
            }
    except Exception as error:
        diagnostic = getattr(getattr(error, "orig", None), "diag", None)
        constraint = getattr(diagnostic, "constraint_name", None)
        detail = f" constraint={constraint}" if isinstance(constraint, str) else ""
        print(
            f"Phase 23 E2E fixture seed failed ({type(error).__name__}{detail}).",
            file=sys.stderr,
        )
        return 1
    finally:
        await dispose_database_engines()
    if fixture is None:
        print("Phase 23 E2E fixture seed produced no fixture.", file=sys.stderr)
        return 1
    print(json.dumps(fixture, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
