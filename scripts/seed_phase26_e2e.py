"""Seed safe persisted evaluation metadata for the focused Phase 26 browser flow."""

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
from app.db.models.evaluation import EvalCase, EvalResult, EvalRun  # noqa: E402
from app.db.models.identity import User  # noqa: E402
from app.db.models.organization import Organization  # noqa: E402
from app.db.seed import DEMO_ORGANIZATION_SLUG, seed_local  # noqa: E402
from app.db.session import dispose_database_engines, get_sessionmaker  # noqa: E402
from app.services.auth.principal import Principal, RoleName  # noqa: E402
from app.services.evaluation.service import EvaluationService  # noqa: E402
from sqlalchemy import select  # noqa: E402

ADMIN_EMAIL = "per.eksempel+admin@demo.invalid"


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed one Phase 26 browser-test fixture.")
    parser.add_argument("--password-env", metavar="VARIABLE", required=True)
    return parser.parse_args()


async def main() -> int:
    arguments = _arguments()
    settings = get_settings()
    password = os.getenv(arguments.password_env)
    if password is None:
        print("Phase 26 E2E seed configuration is unavailable.", file=sys.stderr)
        return 1
    if settings.environment not in {"local", "test"}:
        print("Phase 26 E2E seeding is limited to local and test environments.", file=sys.stderr)
        return 1

    fixture: dict[str, str] | None = None
    try:
        await seed_local(settings, local_password=password)
        sessionmaker = get_sessionmaker(settings)
        async with sessionmaker() as session, session.begin():
            organization = await session.scalar(
                select(Organization).where(Organization.slug == DEMO_ORGANIZATION_SLUG)
            )
            admin = await session.scalar(select(User).where(User.email == ADMIN_EMAIL))
            if organization is None or admin is None:
                raise ValueError("Synthetic evaluation identities are unavailable.")
            principal = Principal(
                user_id=admin.id,
                organization_id=organization.id,
                display_name=admin.display_name,
                preferred_language="nb",
                roles=frozenset({RoleName.ADMIN}),
            )
            service = EvaluationService(session)
            datasets = await service.list_canonical_datasets(principal)
            if len(datasets) != 1:
                raise ValueError("The canonical evaluation dataset is unavailable.")
            dataset = datasets[0].dataset
            cases = tuple(
                (
                    await session.scalars(
                        select(EvalCase)
                        .where(EvalCase.eval_dataset_id == dataset.id)
                        .order_by(EvalCase.case_key)
                    )
                ).all()
            )
            if len(cases) < 2:
                raise ValueError("The canonical evaluation cases are unavailable.")
            now = datetime.now(UTC)
            run = EvalRun(
                organization_id=organization.id,
                eval_dataset_id=dataset.id,
                dataset_version=dataset.dataset_version,
                dataset_content_hash=dataset.content_hash,
                run_name=f"phase26-e2e-{uuid4().hex[:12]}",
                status="completed",
                started_at=now,
                finished_at=now,
                summary_metrics={},
                pass_fail="fail",
            )
            session.add(run)
            await session.flush()
            failed = EvalResult(
                eval_run_id=run.id,
                eval_case_id=cases[0].id,
                retrieval_score=Decimal("1"),
                citation_score=Decimal("0"),
                faithfulness_score=Decimal("1"),
                refusal_score=Decimal("1"),
                risk_score=Decimal("1"),
                routing_score=Decimal("1"),
                latency_ms=12,
                cost_estimate=Decimal("0.001000"),
                passed=False,
                failure_reasons={"codes": ["citation_mismatch"]},
            )
            session.add(failed)
            session.add(
                EvalResult(
                    eval_run_id=run.id,
                    eval_case_id=cases[1].id,
                    retrieval_score=Decimal("1"),
                    citation_score=Decimal("1"),
                    faithfulness_score=Decimal("1"),
                    refusal_score=Decimal("1"),
                    risk_score=Decimal("1"),
                    routing_score=Decimal("1"),
                    passed=True,
                    failure_reasons={"codes": []},
                )
            )
            await session.flush()
            fixture = {
                "case_key": cases[0].case_key,
                "evaluation_result_id": str(failed.id),
                "evaluation_run_id": str(run.id),
            }
    except Exception as error:
        print(f"Phase 26 E2E fixture seed failed ({type(error).__name__}).", file=sys.stderr)
        return 1
    finally:
        await dispose_database_engines()
    if fixture is None:
        print("Phase 26 E2E fixture seed produced no fixture.", file=sys.stderr)
        return 1
    print(json.dumps(fixture, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
