"""Phase 34 local-demo fixture contracts against PostgreSQL/pgvector."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from uuid import UUID

from agent_orchestrator.types import WorkflowContext
from app.core.config import AppSettings
from app.db.models import (
    Approval,
    Case,
    Document,
    EvalRun,
    RetrievedSource,
    WorkflowNodeRun,
    WorkflowRun,
)
from app.db.session import dispose_database_engines, get_sessionmaker
from app.services.approvals.service import ApprovalWorkflowService
from app.services.auth.principal import Principal, RoleName
from app.services.workflows.drafting import DraftingWorkflowService
from app.services.workflows.extraction import ExtractionWorkflowService, load_eligible_evidence
from app.services.workflows.risk import RiskWorkflowService, load_risk_prerequisites
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[4]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.seed_phase34_demo import seed_phase34_demo  # noqa: E402


def test_phase34_demo_seed_creates_a_safe_runnable_bundle(database_settings: AppSettings) -> None:
    asyncio.run(_assert_demo_bundle(database_settings))


async def _assert_demo_bundle(settings: AppSettings) -> None:
    try:
        fixture = await seed_phase34_demo(settings, local_password="Synthetic demo password 42")

        assert fixture["case_worker_email"] == "kari.eksempel+caseworker@demo.invalid"
        assert fixture["reviewer_email"] == "ole.eksempel+reviewer@demo.invalid"
        assert fixture["case_url"] == f"/en/cases/{fixture['case_id']}"
        assert fixture["approval_url"] == f"/en/approvals/{fixture['approval_id']}"
        assert fixture["trace_url"] == f"/en/workflows/{fixture['trace_workflow_run_id']}/trace"
        assert fixture["evaluation_url"] == (f"/en/evaluations/runs/{fixture['evaluation_run_id']}")
        assert "password" not in str(fixture).lower()

        case_id = UUID(str(fixture["case_id"]))
        approval_id = UUID(str(fixture["approval_id"]))
        trace_id = UUID(str(fixture["trace_workflow_run_id"]))
        evaluation_id = UUID(str(fixture["evaluation_run_id"]))
        document_id = UUID(str(fixture["document_id"]))
        request = fixture["rag_answer_request"]
        assert isinstance(request, dict)
        assert request["case_id"] == str(case_id)
        assert request["answer_language"] == "en"
        assert request["question"] == "What must be documented before an answer can be used?"

        async with get_sessionmaker(settings)() as session:
            case = await session.get(Case, case_id)
            document = await session.get(Document, document_id)
            approval = await session.get(Approval, approval_id)
            trace = await session.get(WorkflowRun, trace_id)
            evaluation = await session.get(EvalRun, evaluation_id)

            assert case is not None
            assert case.domain == "public_sector"
            assert case.language == "en"
            assert case.title == "Synthetic accommodation request"
            assert case.status == "waiting_for_human_review"
            assert case.risk_level == "high"
            assert document is not None
            assert document.language == "en"
            assert document.title == "Synthetic case-handling procedure"
            assert document.parsing_status == "parsed"
            assert document.indexing_status == "indexed"
            assert document.source_status == "approved"
            assert approval is not None
            assert approval.status == "pending"
            assert trace is not None
            assert trace.workflow_name == "evidence"
            assert trace.status == "completed"
            assert evaluation is not None
            assert evaluation.status == "completed"
            assert evaluation.pass_fail == "pass"

            seeded_risk_run = await session.scalar(
                select(WorkflowRun).where(
                    WorkflowRun.case_id == case_id,
                    WorkflowRun.workflow_name == "risk_compliance",
                    WorkflowRun.status == "completed",
                )
            )
            assert seeded_risk_run is not None
            assert (
                await ApprovalWorkflowService(session).create_required_run(
                    WorkflowContext(
                        workflow_run_id=seeded_risk_run.id,
                        organization_id=case.organization_id,
                        case_id=case_id,
                        initiated_by_user_id=case.submitted_by_user_id,
                        workflow_name=seeded_risk_run.workflow_name,
                        workflow_version=seeded_risk_run.workflow_version,
                    )
                )
                is None
            )

            principal = Principal(
                user_id=case.submitted_by_user_id,
                organization_id=case.organization_id,
                display_name="Synthetic case worker",
                preferred_language="en",
                roles=frozenset({RoleName.CASE_WORKER}),
            )
            eligible_evidence = await load_eligible_evidence(
                session, principal.organization_id, case_id
            )
            assert eligible_evidence is not None
            assert eligible_evidence.workflow_run.id == trace_id
            assert (
                await load_risk_prerequisites(session, principal.organization_id, case_id)
                is not None
            )

            extraction = await ExtractionWorkflowService(session, confidence_threshold=0.8).start(
                principal, case_id
            )
            drafting = await DraftingWorkflowService(session).start(principal, case_id)
            risk = await RiskWorkflowService(session).start(principal, case_id)
            assert extraction.status == "queued"
            assert drafting.status == "queued"
            assert risk.status == "queued"

            source = await session.scalar(
                select(RetrievedSource).where(RetrievedSource.workflow_run_id == trace_id)
            )
            assert source is not None
            assert source.document_id == document_id
            assert source.citation_label == "S1"
            nodes = list(
                (
                    await session.scalars(
                        select(WorkflowNodeRun).where(WorkflowNodeRun.workflow_run_id == trace_id)
                    )
                ).all()
            )
            assert {node.node_name for node in nodes} == {
                "source_policy",
                "hybrid_retrieval",
                "evidence_sufficiency",
            }
            # The historical Phase 22 downgrade restores ``decision_at`` to a
            # non-nullable legacy column. Remove this deliberately pending
            # fixture row before the shared database fixture downgrades.
            await session.delete(approval)
            await session.commit()
    finally:
        await dispose_database_engines()
