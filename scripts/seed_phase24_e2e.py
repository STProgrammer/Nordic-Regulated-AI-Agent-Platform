"""Seed one synthetic eligible-Evidence case for the focused controlled-memory browser flow."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
API_SOURCE = ROOT / "apps" / "api" / "src"
if str(API_SOURCE) not in sys.path:
    sys.path.insert(0, str(API_SOURCE))

from app.core.config import get_settings  # noqa: E402
from app.db.models.case import Case  # noqa: E402
from app.db.models.document import Document, DocumentChunk  # noqa: E402
from app.db.models.identity import User  # noqa: E402
from app.db.models.organization import Organization  # noqa: E402
from app.db.models.workflow import RetrievedSource, WorkflowRun  # noqa: E402
from app.db.seed import DEMO_ORGANIZATION_SLUG, seed_local  # noqa: E402
from app.db.session import dispose_database_engines, get_sessionmaker  # noqa: E402
from sqlalchemy import select  # noqa: E402

CASE_WORKER_EMAIL = "kari.eksempel+caseworker@demo.invalid"


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed one Phase 24 browser-test fixture.")
    parser.add_argument("--password-env", metavar="VARIABLE", required=True)
    parser.add_argument("--title-env", metavar="VARIABLE", default="NORDIC_E2E_MEMORY_CASE_TITLE")
    return parser.parse_args()


async def main() -> int:
    arguments = _arguments()
    settings = get_settings()
    password = os.getenv(arguments.password_env)
    title = os.getenv(arguments.title_env, "").strip()
    if password is None or not title or len(title) > 255:
        print("Phase 24 E2E seed configuration is unavailable.", file=sys.stderr)
        return 1
    if settings.environment not in {"local", "test"}:
        print("Phase 24 E2E seeding is limited to local and test environments.", file=sys.stderr)
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
                raise ValueError("Synthetic controlled-memory identities are unavailable.")
            now = datetime.now(UTC)
            case = Case(
                organization_id=organization.id,
                case_number=f"E2E-P24-{uuid4().hex[:12].upper()}",
                title=title,
                description="Synthetic controlled-memory drafting fixture.",
                language="nb",
                domain="internal_policy",
                priority="normal",
                status="processing",
                submitted_by_user_id=worker.id,
                external_reference="phase24-e2e-fixture",
            )
            session.add(case)
            await session.flush()
            document = Document(
                organization_id=organization.id,
                case_id=case.id,
                uploaded_by_user_id=worker.id,
                title="Synthetic approved source",
                original_filename="synthetic-phase24.txt",
                file_type="txt",
                mime_type="text/plain",
                file_size_bytes=64,
                checksum_sha256="4" * 64,
                object_storage_key="local/phase24/synthetic.txt",
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
                content="Det syntetiske kildegrunnlaget er godkjent.",
                token_count=8,
                chunk_metadata={},
                embedding=[0.0] * 1536,
            )
            session.add(chunk)
            await session.flush()
            evidence = WorkflowRun(
                organization_id=organization.id,
                case_id=case.id,
                started_by_user_id=worker.id,
                workflow_name="evidence",
                workflow_version="phase24-e2e-v1",
                status="completed",
                started_at=now,
                finished_at=now,
                state_snapshot={
                    "workflow_name": "evidence",
                    "workflow_version": "phase24-e2e-v1",
                    "status": "completed",
                    "evidence_outcome": "completed",
                    "evidence_sufficient": True,
                    "contradiction_detected": False,
                },
            )
            session.add(evidence)
            await session.flush()
            session.add(
                RetrievedSource(
                    organization_id=organization.id,
                    case_id=case.id,
                    workflow_run_id=evidence.id,
                    document_id=document.id,
                    chunk_id=chunk.id,
                    rank=1,
                    score=1,
                    retrieval_method="keyword",
                    excerpt=chunk.content,
                    citation_label="S1",
                )
            )
            fixture = {"case_id": str(case.id), "title": case.title}
    except Exception as error:
        print(f"Phase 24 E2E fixture seed failed ({type(error).__name__}).", file=sys.stderr)
        return 1
    finally:
        await dispose_database_engines()
    if fixture is None:
        print("Phase 24 E2E fixture seed produced no fixture.", file=sys.stderr)
        return 1
    print(json.dumps(fixture, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
