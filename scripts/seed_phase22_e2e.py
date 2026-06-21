"""Seed one synthetic, already-paused Phase 22 approval for focused browser validation."""

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
from app.db.models.identity import User  # noqa: E402
from app.db.models.organization import Organization  # noqa: E402
from app.db.models.workflow import AgentMessage, Approval, RiskAssessment, WorkflowRun  # noqa: E402
from app.db.seed import DEMO_ORGANIZATION_SLUG, seed_local  # noqa: E402
from app.db.session import dispose_database_engines, get_sessionmaker  # noqa: E402
from sqlalchemy import select  # noqa: E402

CASE_WORKER_EMAIL = "kari.eksempel+caseworker@demo.invalid"


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed one focused Phase 22 browser-test fixture.")
    parser.add_argument(
        "--password-env",
        metavar="VARIABLE",
        required=True,
        help="Environment variable containing the local-only synthetic login password.",
    )
    parser.add_argument(
        "--title-env",
        metavar="VARIABLE",
        default="NORDIC_E2E_APPROVAL_CASE_TITLE",
        help="Environment variable containing the synthetic case title.",
    )
    return parser.parse_args()


async def main() -> int:
    """Create a pending review without exercising prerequisite workflows in the browser."""

    arguments = _arguments()
    settings = get_settings()
    password = os.getenv(arguments.password_env)
    title = os.getenv(arguments.title_env, "").strip()
    if password is None or not title or len(title) > 255:
        print("Phase 22 E2E seed configuration is unavailable.", file=sys.stderr)
        return 1
    if settings.environment not in {"local", "test"}:
        print("Phase 22 E2E seeding is limited to local and test environments.", file=sys.stderr)
        return 1

    fixture: dict[str, str] | None = None
    try:
        await seed_local(settings, local_password=password)
        sessionmaker = get_sessionmaker(settings)
        async with sessionmaker() as session, session.begin():
            organization = await session.scalar(
                select(Organization).where(Organization.slug == DEMO_ORGANIZATION_SLUG)
            )
            case_worker = await session.scalar(select(User).where(User.email == CASE_WORKER_EMAIL))
            if organization is None or case_worker is None:
                raise ValueError("Synthetic approval identities are unavailable.")

            now = datetime.now(UTC)
            case = Case(
                organization_id=organization.id,
                case_number=f"E2E-P22-{uuid4().hex[:12].upper()}",
                title=title,
                description="Synthetic pre-seeded human-approval fixture.",
                language="nb",
                domain="internal_policy",
                priority="normal",
                status="waiting_for_human_review",
                risk_level="high",
                submitted_by_user_id=case_worker.id,
                external_reference="phase22-e2e-fixture",
            )
            session.add(case)
            await session.flush()

            drafting_run = WorkflowRun(
                organization_id=organization.id,
                case_id=case.id,
                started_by_user_id=case_worker.id,
                workflow_name="drafting",
                workflow_version="phase20-v1",
                status="completed",
                started_at=now,
                finished_at=now,
                state_snapshot={
                    "workflow_name": "drafting",
                    "workflow_version": "phase20-v1",
                    "state_schema_version": "v1",
                    "status": "completed",
                    "draft_available": True,
                    "citation_labels": [],
                },
            )
            risk_run = WorkflowRun(
                organization_id=organization.id,
                case_id=case.id,
                started_by_user_id=case_worker.id,
                workflow_name="risk_compliance",
                workflow_version="phase21-v1",
                status="completed",
                started_at=now,
                finished_at=now,
                state_snapshot={
                    "workflow_name": "risk_compliance",
                    "workflow_version": "phase21-v1",
                    "state_schema_version": "v1",
                    "status": "completed",
                    "final_risk_level": "high",
                    "approval_required": True,
                },
            )
            approval_run = WorkflowRun(
                organization_id=organization.id,
                case_id=case.id,
                started_by_user_id=case_worker.id,
                workflow_name="human_approval",
                workflow_version="phase22-v1",
                status="waiting_for_human_review",
                started_at=now,
                state_snapshot={
                    "workflow_name": "human_approval",
                    "workflow_version": "phase22-v1",
                    "state_schema_version": "v1",
                    "status": "waiting_for_human_review",
                    "approval_lifecycle": "pending",
                },
            )
            session.add_all((drafting_run, risk_run, approval_run))
            await session.flush()

            session.add(
                AgentMessage(
                    organization_id=organization.id,
                    case_id=case.id,
                    workflow_run_id=drafting_run.id,
                    message_type="draft",
                    role="assistant",
                    content="Syntetisk uforanderlig KI-utkast for lokal Phase 22-validering.",
                    model_provider="deterministic",
                    model_name="phase22-e2e-fixture",
                )
            )
            risk = RiskAssessment(
                organization_id=organization.id,
                case_id=case.id,
                workflow_run_id=risk_run.id,
                risk_level="high",
                risk_reasons={"codes": ["pii_detected"]},
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
                ai_draft="Syntetisk uforanderlig KI-utkast for lokal Phase 22-validering.",
                interrupted_at=now,
            )
            session.add(approval)
            await session.flush()
            approval_run.state_snapshot = {
                **approval_run.state_snapshot,
                "approval_id": str(approval.id),
            }
            fixture = {
                "approval_id": str(approval.id),
                "case_id": str(case.id),
                "title": case.title,
            }
    except Exception:
        print("Phase 22 E2E fixture seed failed.", file=sys.stderr)
        return 1
    finally:
        await dispose_database_engines()

    if fixture is None:
        print("Phase 22 E2E fixture seed produced no fixture.", file=sys.stderr)
        return 1
    print(json.dumps(fixture, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
