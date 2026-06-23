"""Create one safe, local-only Phase 34 portfolio-demo scenario."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
API_SOURCE = ROOT / "apps" / "api" / "src"
if str(API_SOURCE) not in sys.path:
    sys.path.insert(0, str(API_SOURCE))

from app.core.config import AppSettings, get_settings  # noqa: E402
from app.db.base import EMBEDDING_DIMENSIONS  # noqa: E402
from app.db.models import (  # noqa: E402
    AgentMessage,
    Approval,
    AuditEvent,
    Case,
    Document,
    DocumentChunk,
    DocumentText,
    ExtractedField,
    ModelUsageRecord,
    RetrievedSource,
    RiskAssessment,
    User,
    WorkflowNodeRun,
    WorkflowRun,
    WorkflowToolCall,
)
from app.db.models.organization import Organization  # noqa: E402
from app.db.seed import DEMO_ORGANIZATION_SLUG, seed_local  # noqa: E402
from app.db.session import dispose_database_engines, get_sessionmaker  # noqa: E402
from app.services.auth.principal import Principal, RoleName  # noqa: E402
from app.services.evaluation.service import EvaluationService  # noqa: E402
from sqlalchemy import select  # noqa: E402

ADMIN_EMAIL = "per.eksempel+admin@demo.invalid"
CASE_WORKER_EMAIL = "kari.eksempel+caseworker@demo.invalid"
REVIEWER_EMAIL = "ole.eksempel+reviewer@demo.invalid"
_WORKFLOW_VERSION = "phase34-demo-v1"
_DOCUMENT_CONTENT = (
    "Dette er en utelukkende syntetisk rutine for Eksempelkommune. Saksbehandler skal "
    "dokumentere samtykke og vurdere godkjente kilder før et svar kan brukes. Saken skal "
    "sendes til menneskelig godkjenning når den gjelder personopplysninger eller et "
    "offentlig vedtak. Den ansvarlige medarbeideren skal registrere kontrollene i saken."
)
_DRAFT_TEXT = (
    "Det syntetiske saksutkastet skal ikke brukes før en Compliance Reviewer har kontrollert "
    "kildegrunnlaget og godkjent utfallet. [S1]"
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed one safe local Phase 34 portfolio-demo scenario."
    )
    parser.add_argument(
        "--password-env",
        metavar="VARIABLE",
        required=True,
        help="Environment variable containing the local-only synthetic login password.",
    )
    return parser.parse_args()


async def seed_phase34_demo(settings: AppSettings, *, local_password: str) -> dict[str, object]:
    """Persist a fresh, self-contained demo bundle without deleting prior fixtures."""

    await seed_local(settings, local_password=local_password)
    sessionmaker = get_sessionmaker(settings)
    async with sessionmaker() as session:
        organization = await session.scalar(
            select(Organization).where(Organization.slug == DEMO_ORGANIZATION_SLUG)
        )
        case_worker = await session.scalar(select(User).where(User.email == CASE_WORKER_EMAIL))
        admin = await session.scalar(select(User).where(User.email == ADMIN_EMAIL))
        if organization is None or case_worker is None or admin is None:
            raise ValueError("Synthetic Phase 34 identities are unavailable.")

        now = datetime.now(UTC)
        fixture_suffix = uuid4().hex[:10].upper()
        case = Case(
            organization_id=organization.id,
            case_number=f"DEMO-34-{fixture_suffix}",
            title="Syntetisk søknad om tilrettelegging",
            description=(
                "Dette er en fiktiv, sikker demo-sak fra Eksempelkommune. Den inneholder "
                "kun oppdiktede opplysninger og viser hvorfor menneskelig godkjenning kreves."
            ),
            language="nb",
            domain="public_sector",
            case_type="case_support",
            priority="high",
            status="waiting_for_human_review",
            risk_level="high",
            assigned_user_id=case_worker.id,
            submitted_by_user_id=case_worker.id,
            external_reference=f"phase34-demo-{fixture_suffix.lower()}",
        )
        session.add(case)
        await session.flush()

        document = Document(
            organization_id=organization.id,
            case_id=case.id,
            uploaded_by_user_id=case_worker.id,
            title="Syntetisk rutine for saksbehandling",
            original_filename="syntetisk-rutine-for-saksbehandling.txt",
            file_type="txt",
            mime_type="text/plain",
            file_size_bytes=len(_DOCUMENT_CONTENT.encode("utf-8")),
            checksum_sha256=hashlib.sha256(_DOCUMENT_CONTENT.encode("utf-8")).hexdigest(),
            object_storage_key=f"synthetic/phase34/{fixture_suffix.lower()}.txt",
            language="nb",
            source_status="approved",
            confidentiality_level="internal",
            page_count=1,
            parsing_status="parsed",
            parsing_error=None,
            indexing_status="indexed",
            indexing_error=None,
            indexed_at=now,
        )
        session.add(document)
        await session.flush()
        chunk = DocumentChunk(
            organization_id=organization.id,
            document_id=document.id,
            chunk_index=0,
            page_number=1,
            section_title="Godkjenning og kontroll",
            content=_DOCUMENT_CONTENT,
            token_count=48,
            chunk_metadata={"synthetic": True, "fixture": "phase34-demo"},
            embedding=[0.01] * EMBEDDING_DIMENSIONS,
        )
        session.add_all(
            (
                DocumentText(
                    document_id=document.id,
                    extracted_text=_DOCUMENT_CONTENT,
                    extraction_metadata={"synthetic": True, "parser": "phase34-demo"},
                ),
                chunk,
            )
        )
        await session.flush()

        intake_run = _completed_run(
            organization_id=organization.id,
            case_id=case.id,
            user_id=case_worker.id,
            now=now,
            workflow_name="intake",
            state_snapshot={
                "workflow_name": "intake",
                "workflow_version": _WORKFLOW_VERSION,
                "state_schema_version": "v1",
                "status": "completed",
                "declared_language": "nb",
                "detected_language": "nb",
                "detected_language_confident": True,
                "classification_case_type": "case_support",
                "recommended_domain": "public_sector",
                "pii_detected": True,
                "preliminary_risk_level": "high",
                "suggested_workflow": "evidence",
            },
        )
        evidence_run = _completed_run(
            organization_id=organization.id,
            case_id=case.id,
            user_id=case_worker.id,
            now=now + timedelta(seconds=1),
            workflow_name="evidence",
            state_snapshot={
                "workflow_name": "evidence",
                "workflow_version": _WORKFLOW_VERSION,
                "state_schema_version": "v1",
                "status": "completed",
                "evidence_outcome": "sufficient",
                "evidence_sufficient": True,
                "contradiction_detected": False,
                "evidence_source_count": 1,
                "approved_source_count": 1,
                "node_count": 3,
            },
        )
        extraction_run = _completed_run(
            organization_id=organization.id,
            case_id=case.id,
            user_id=case_worker.id,
            now=now + timedelta(seconds=2),
            workflow_name="extraction",
            state_snapshot={
                "workflow_name": "extraction",
                "workflow_version": _WORKFLOW_VERSION,
                "state_schema_version": "v1",
                "status": "completed",
                "extraction_schema": "v1",
                "extracted_field_count": 1,
                "low_confidence_field_count": 0,
            },
        )
        drafting_run = _completed_run(
            organization_id=organization.id,
            case_id=case.id,
            user_id=case_worker.id,
            now=now + timedelta(seconds=3),
            workflow_name="drafting",
            state_snapshot={
                "workflow_name": "drafting",
                "workflow_version": _WORKFLOW_VERSION,
                "state_schema_version": "v1",
                "status": "completed",
                "target_language": "nb",
                "draft_available": True,
                "citation_count": 1,
            },
        )
        risk_run = _completed_run(
            organization_id=organization.id,
            case_id=case.id,
            user_id=case_worker.id,
            now=now + timedelta(seconds=4),
            workflow_name="risk_compliance",
            state_snapshot={
                "workflow_name": "risk_compliance",
                "workflow_version": _WORKFLOW_VERSION,
                "state_schema_version": "v1",
                "status": "completed",
                "final_risk_level": "high",
                "requires_approval": True,
                "safe_next_state": "waiting_for_human_review",
            },
        )
        approval_run = WorkflowRun(
            organization_id=organization.id,
            case_id=case.id,
            started_by_user_id=case_worker.id,
            workflow_name="human_approval",
            workflow_version="phase22-v1",
            status="waiting_for_human_review",
            started_at=now + timedelta(seconds=5),
            state_snapshot={
                "workflow_name": "human_approval",
                "workflow_version": "phase22-v1",
                "state_schema_version": "v1",
                "status": "waiting_for_human_review",
                "approval_lifecycle": "pending",
                "approval_required": True,
            },
        )
        session.add_all(
            (intake_run, evidence_run, extraction_run, drafting_run, risk_run, approval_run)
        )
        await session.flush()

        trace_nodes = _trace_nodes(evidence_run.id, now)
        session.add_all(trace_nodes)
        await session.flush()
        session.add_all(
            (
                WorkflowToolCall(
                    workflow_run_id=evidence_run.id,
                    workflow_node_run_id=trace_nodes[1].id,
                    tool_name="hybrid_retrieval",
                    status="completed",
                    started_at=now + timedelta(seconds=1, milliseconds=30),
                    finished_at=now + timedelta(seconds=1, milliseconds=90),
                    duration_ms=60,
                    retry_count=0,
                    input_summary={"source_status": "approved"},
                    output_summary={"result_count": 1},
                    error_summary=None,
                ),
                ModelUsageRecord(
                    organization_id=organization.id,
                    case_id=case.id,
                    workflow_run_id=evidence_run.id,
                    provider="deterministic",
                    model_name="deterministic-local-workflow",
                    operation="evidence_rerank",
                    token_input=None,
                    token_output=None,
                    cost_estimate=None,
                    latency_ms=0,
                    success=True,
                    error_summary=None,
                ),
                RetrievedSource(
                    organization_id=organization.id,
                    case_id=case.id,
                    workflow_run_id=evidence_run.id,
                    document_id=document.id,
                    chunk_id=chunk.id,
                    rank=1,
                    score=Decimal("0.02000000"),
                    retrieval_method="hybrid",
                    excerpt=_DOCUMENT_CONTENT,
                    citation_label="S1",
                ),
                ExtractedField(
                    organization_id=organization.id,
                    case_id=case.id,
                    workflow_run_id=extraction_run.id,
                    field_name="next_action",
                    field_value={"value": "Innhent menneskelig godkjenning før bruk."},
                    confidence=Decimal("0.95000000"),
                    source_chunk_id=chunk.id,
                    human_edited=False,
                ),
                AgentMessage(
                    organization_id=organization.id,
                    case_id=case.id,
                    workflow_run_id=drafting_run.id,
                    message_type="draft",
                    role="assistant",
                    content=_DRAFT_TEXT,
                    structured_output={"language": "nb", "citation_labels": ["S1"]},
                    model_provider="deterministic",
                    model_name="deterministic-local-workflow",
                    prompt_version_id=None,
                    token_input=None,
                    token_output=None,
                    cost_estimate=None,
                    latency_ms=0,
                ),
            )
        )
        risk = RiskAssessment(
            organization_id=organization.id,
            case_id=case.id,
            workflow_run_id=risk_run.id,
            risk_level="high",
            risk_reasons={"codes": ["pii_detected", "sensitive_domain"]},
            pii_detected=True,
            prompt_injection_detected=False,
            weak_evidence=False,
            high_impact_action=False,
            requires_approval=True,
        )
        session.add(risk)
        await session.flush()
        approval = Approval(
            organization_id=organization.id,
            case_id=case.id,
            workflow_run_id=approval_run.id,
            drafting_workflow_run_id=drafting_run.id,
            risk_assessment_id=risk.id,
            status="pending",
            ai_draft=_DRAFT_TEXT,
            interrupted_at=now + timedelta(seconds=5),
        )
        session.add(approval)
        await session.flush()
        approval_run.state_snapshot = {
            **approval_run.state_snapshot,
            "approval_id": str(approval.id),
        }
        session.add(
            AuditEvent(
                organization_id=organization.id,
                actor_user_id=case_worker.id,
                event_type="demo.scenario_seeded",
                resource_type="case",
                resource_id=case.id,
                case_id=case.id,
                event_data={"fixture": "phase34", "synthetic": True},
            )
        )
        await session.commit()

        admin_principal = Principal(
            user_id=admin.id,
            organization_id=organization.id,
            display_name=admin.display_name,
            preferred_language="nb",
            roles=frozenset({RoleName.ADMIN}),
        )
        evaluations = EvaluationService(session)
        datasets = await evaluations.list_canonical_datasets(admin_principal)
        if not datasets:
            raise ValueError("Canonical evaluation dataset is unavailable.")
        evaluation = await evaluations.start(
            admin_principal, dataset_key=datasets[0].dataset.dataset_key
        )
        if await evaluations.execute(evaluation.evaluation_run_id) != "completed":
            raise ValueError("Synthetic evaluation run did not complete.")

        return {
            "approval_id": str(approval.id),
            "approval_url": f"/nb/approvals/{approval.id}",
            "case_id": str(case.id),
            "case_url": f"/nb/cases/{case.id}",
            "case_worker_email": CASE_WORKER_EMAIL,
            "document_id": str(document.id),
            "evaluation_run_id": str(evaluation.evaluation_run_id),
            "evaluation_url": f"/nb/evaluations/runs/{evaluation.evaluation_run_id}",
            "rag_answer_request": {
                "answer_language": "nb",
                "case_id": str(case.id),
                "question": "Hva må dokumenteres før et svar kan brukes?",
            },
            "reviewer_email": REVIEWER_EMAIL,
            "title": case.title,
            "trace_workflow_run_id": str(evidence_run.id),
            "trace_url": f"/nb/workflows/{evidence_run.id}/trace",
        }


def _completed_run(
    *,
    organization_id: UUID,
    case_id: UUID,
    user_id: UUID,
    now: datetime,
    workflow_name: str,
    state_snapshot: dict[str, object],
) -> WorkflowRun:
    return WorkflowRun(
        organization_id=organization_id,
        case_id=case_id,
        started_by_user_id=user_id,
        workflow_name=workflow_name,
        workflow_version=_WORKFLOW_VERSION,
        status="completed",
        started_at=now,
        finished_at=now + timedelta(milliseconds=100),
        duration_ms=100,
        total_cost_estimate=None,
        total_tokens=None,
        error_summary=None,
        state_snapshot=state_snapshot,
    )


def _trace_nodes(workflow_run_id: UUID, now: datetime) -> tuple[WorkflowNodeRun, ...]:
    return (
        WorkflowNodeRun(
            workflow_run_id=workflow_run_id,
            node_name="source_policy",
            status="completed",
            started_at=now + timedelta(seconds=1),
            finished_at=now + timedelta(seconds=1, milliseconds=20),
            duration_ms=20,
            input_summary={"source_status": "approved"},
            output_summary={"permitted_source_count": 1},
            error_summary=None,
            retry_count=0,
        ),
        WorkflowNodeRun(
            workflow_run_id=workflow_run_id,
            node_name="hybrid_retrieval",
            status="completed",
            started_at=now + timedelta(seconds=1, milliseconds=20),
            finished_at=now + timedelta(seconds=1, milliseconds=90),
            duration_ms=70,
            input_summary={"candidate_limit": 1},
            output_summary={"merged_candidate_count": 1},
            error_summary=None,
            retry_count=0,
        ),
        WorkflowNodeRun(
            workflow_run_id=workflow_run_id,
            node_name="evidence_sufficiency",
            status="completed",
            started_at=now + timedelta(seconds=1, milliseconds=90),
            finished_at=now + timedelta(seconds=1, milliseconds=100),
            duration_ms=10,
            input_summary={"evidence_source_count": 1},
            output_summary={"evidence_sufficient": True},
            error_summary=None,
            retry_count=0,
        ),
    )


async def main() -> int:
    arguments = _arguments()
    settings = get_settings()
    password = os.getenv(arguments.password_env)
    if password is None:
        print("Phase 34 demo seed configuration is unavailable.", file=sys.stderr)
        return 1
    if settings.environment not in {"local", "test"}:
        print("Phase 34 demo seeding is limited to local and test environments.", file=sys.stderr)
        return 1
    try:
        fixture = await seed_phase34_demo(settings, local_password=password)
    except Exception as error:
        print(f"Phase 34 demo seed failed ({type(error).__name__}).", file=sys.stderr)
        return 1
    finally:
        await dispose_database_engines()
    print(json.dumps(fixture, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
