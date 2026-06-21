"""Cookie/RBAC and strict safe-contract coverage for evaluation operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.api.dependencies import get_authentication_service, get_evaluation_service
from app.core.config import AppSettings
from app.db.models.evaluation import EvalDataset, EvalResult, EvalRun
from app.main import create_api_app
from app.services.auth.policy import EvaluationAction, authorize_evaluation_action
from app.services.auth.principal import Principal, RoleName
from app.services.common.pagination import Page, Pagination
from app.services.errors import NotFoundError
from app.services.evaluation.reporting import (
    EvaluationResultProjection,
    EvaluationRunProjection,
    project_result,
    project_run,
    render_markdown_report,
)
from app.services.evaluation.service import CanonicalDatasetRecord
from fastapi.testclient import TestClient

_SESSION_ID = "synthetic_evaluation_session_012345678901234567890123456"
_HASH = "a" * 64


class _AuthenticationFake:
    def __init__(self, principal: Principal) -> None:
        self.principal = principal

    async def resolve_principal(self, session_id: str) -> Principal | None:
        return self.principal if session_id == _SESSION_ID else None


@dataclass
class _EvaluationServiceFake:
    principal: Principal

    def __post_init__(self) -> None:
        now = datetime(2030, 1, 1, tzinfo=UTC)
        self.dataset = EvalDataset(
            id=uuid4(),
            organization_id=None,
            name="nordic-regulated-core-v1",
            description="Synthetic deterministic evaluation corpus.",
            dataset_key="nordic-regulated-core-v1",
            dataset_version="v1",
            content_hash=_HASH,
            domain="canonical",
            inserted_at=now,
            updated_at=now,
        )
        self.run = EvalRun(
            id=uuid4(),
            organization_id=self.principal.organization_id,
            eval_dataset_id=self.dataset.id,
            dataset_version="v1",
            dataset_content_hash=_HASH,
            run_name="nordic-regulated-core-v1-v1",
            status="completed",
            started_at=now,
            finished_at=now,
            summary_metrics={"total_cases": 1, "passed": True},
            pass_fail="pass",
            inserted_at=now,
        )
        self.result = EvalResult(
            id=uuid4(),
            eval_run_id=self.run.id,
            eval_case_id=uuid4(),
            retrieval_score=Decimal("1"),
            citation_score=Decimal("1"),
            faithfulness_score=Decimal("1"),
            refusal_score=Decimal("1"),
            risk_score=Decimal("1"),
            routing_score=Decimal("1"),
            latency_ms=0,
            cost_estimate=Decimal("0"),
            passed=True,
            failure_reasons={"codes": []},
            inserted_at=now,
        )

    async def list_canonical_datasets(
        self, principal: Principal
    ) -> tuple[CanonicalDatasetRecord, ...]:
        authorize_evaluation_action(principal, EvaluationAction.READ)
        return (CanonicalDatasetRecord(self.dataset),)

    def _run_projection(self) -> EvaluationRunProjection:
        return project_run(
            self.run,
            dataset_key=self.dataset.dataset_key,
            results=(project_result(self.result, case_key="synthetic_case"),),
        )

    async def start(self, principal: Principal, *, dataset_key: str) -> EvaluationRunProjection:
        authorize_evaluation_action(principal, EvaluationAction.START)
        if dataset_key != self.dataset.dataset_key:
            raise NotFoundError("Evaluation dataset")
        self.run.status = "queued"
        self.run.finished_at = None
        self.run.pass_fail = "pending"
        return project_run(self.run, dataset_key=self.dataset.dataset_key, results=())

    async def list_runs(
        self, principal: Principal, *, pagination: Pagination, status: str | None = None
    ) -> Page[EvaluationRunProjection]:
        authorize_evaluation_action(principal, EvaluationAction.READ)
        items = (self._run_projection(),) if status is None or status == self.run.status else ()
        return Page(items=items, limit=pagination.limit, offset=pagination.offset, total=len(items))

    async def get_run(self, principal: Principal, run_id: UUID) -> EvaluationRunProjection:
        authorize_evaluation_action(principal, EvaluationAction.READ)
        if run_id != self.run.id or principal.organization_id != self.principal.organization_id:
            raise NotFoundError("Evaluation run")
        return self._run_projection()

    async def get_result(
        self, principal: Principal, run_id: UUID, result_id: UUID
    ) -> EvaluationResultProjection:
        authorize_evaluation_action(principal, EvaluationAction.READ)
        if (
            run_id != self.run.id
            or result_id != self.result.id
            or principal.organization_id != self.principal.organization_id
        ):
            raise NotFoundError("Evaluation result")
        return project_result(self.result, case_key="synthetic_case")

    async def export_report(self, principal: Principal, run_id: UUID, *, locale: str) -> str:
        authorize_evaluation_action(principal, EvaluationAction.EXPORT)
        if run_id != self.run.id or principal.organization_id != self.principal.organization_id:
            raise NotFoundError("Evaluation run")
        return render_markdown_report(self._run_projection(), locale=locale)


def _client(*roles: RoleName) -> tuple[TestClient, _EvaluationServiceFake]:
    principal = Principal(
        user_id=uuid4(),
        organization_id=uuid4(),
        display_name="Synthetic evaluation user",
        preferred_language="nb",
        roles=frozenset(roles),
    )
    service = _EvaluationServiceFake(principal)
    app = create_api_app(AppSettings(environment="test"))
    app.dependency_overrides[get_authentication_service] = lambda: _AuthenticationFake(principal)
    app.dependency_overrides[get_evaluation_service] = lambda: service
    client = TestClient(app)
    client.cookies.set("nordic_session", _SESSION_ID)
    return client, service


def test_evaluation_routes_require_admin_and_expose_safe_data_only() -> None:
    denied, _service = _client(RoleName.CASE_WORKER)
    with denied:
        assert denied.get("/api/evaluations/datasets").status_code == 403
        assert denied.get(f"/api/evaluations/runs/{uuid4()}/results/{uuid4()}").status_code == 403
        assert denied.post(f"/api/evaluations/runs/{uuid4()}/report", json={}).status_code == 403

    client, service = _client(RoleName.ADMIN)
    with client:
        datasets = client.get("/api/evaluations/datasets")
        started = client.post("/api/evaluations/datasets/nordic-regulated-core-v1/runs", json={})
        extra = client.post(
            "/api/evaluations/datasets/nordic-regulated-core-v1/runs",
            json={"provider": "external", "organization_id": str(uuid4())},
        )
        runs = client.get("/api/evaluations/runs?status=queued")
        detail = client.get(f"/api/evaluations/runs/{service.run.id}")
        result = client.get(f"/api/evaluations/runs/{service.run.id}/results/{service.result.id}")
        mismatch = client.get(f"/api/evaluations/runs/{service.run.id}/results/{uuid4()}")
        report = client.post(
            f"/api/evaluations/runs/{service.run.id}/report",
            headers={"Accept-Language": "en"},
            json={},
        )
        report_extra = client.post(
            f"/api/evaluations/runs/{service.run.id}/report", json={"format": "pdf"}
        )
        foreign = client.get(f"/api/evaluations/runs/{uuid4()}")

    assert datasets.status_code == 200
    assert datasets.json()["data"]["items"][0]["dataset_key"] == "nordic-regulated-core-v1"
    assert started.status_code == 201
    assert started.json()["data"]["pass_fail"] == "pending"
    assert extra.status_code == 422
    assert runs.status_code == 200
    assert runs.json()["data"]["total"] == 1
    assert detail.status_code == 200
    assert detail.json()["data"]["results"][0]["case_key"] == "synthetic_case"
    assert detail.json()["data"]["results"][0]["risk_score"] == 1.0
    assert detail.json()["data"]["run"]["metrics"]["average_latency_ms"] == 0
    assert detail.json()["data"]["run"]["metrics"]["total_cost_estimate"] == 0
    assert "summary" not in detail.json()["data"]["run"]
    assert "evaluation_case_id" not in detail.json()["data"]["results"][0]
    assert result.status_code == 200
    assert result.json()["data"]["cost_estimate"] == 0
    assert mismatch.status_code == 404
    assert report.status_code == 200
    assert report.headers["content-type"].startswith("text/markdown")
    assert report.headers["content-disposition"] == 'attachment; filename="evaluation-report.md"'
    assert report.text.startswith("# Evaluation report")
    assert report_extra.status_code == 422
    assert "query" not in detail.text
    assert "provider" not in detail.text
    assert foreign.status_code == 404
