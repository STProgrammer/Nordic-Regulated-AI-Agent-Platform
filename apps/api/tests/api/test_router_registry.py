from app.api.router import ROUTE_GROUPS, build_api_router, openapi_tags
from fastapi import APIRouter, FastAPI

EXPECTED_PREFIXES: dict[str, str] = {
    "auth": "/auth",
    "users": "/users",
    "cases": "/cases",
    "documents": "/documents",
    "workflows": "/workflows",
    "approvals": "/approvals",
    "retrieval": "/retrieval",
    "evaluations": "/evaluations",
    "audit": "/audit",
    "admin": "/admin",
}


def test_registry_contains_every_expected_group() -> None:
    names = [group.name for group in ROUTE_GROUPS]
    assert names == list(EXPECTED_PREFIXES)


def test_registry_prefixes_match_architecture() -> None:
    actual = {group.name: group.prefix for group in ROUTE_GROUPS}
    assert actual == EXPECTED_PREFIXES


def test_registry_prefixes_and_tags_are_unique() -> None:
    prefixes = [group.prefix for group in ROUTE_GROUPS]
    tags = [group.tag for group in ROUTE_GROUPS]
    assert len(prefixes) == len(set(prefixes))
    assert len(tags) == len(set(tags))


def test_prefixes_are_rooted_paths() -> None:
    for group in ROUTE_GROUPS:
        assert group.prefix.startswith("/")
        assert not group.prefix.endswith("/")


def test_only_implemented_route_modules_define_operations() -> None:
    for group in ROUTE_GROUPS:
        assert isinstance(group.router, APIRouter)
        if group.name in {
            "auth",
            "users",
            "cases",
            "documents",
            "retrieval",
            "workflows",
            "approvals",
            "evaluations",
            "audit",
            "admin",
        }:
            assert group.router.routes
        else:
            assert group.router.routes == []


def test_aggregate_router_mounts_the_phase_twenty_eight_business_operations() -> None:
    api_router = build_api_router("/api")
    assert isinstance(api_router, APIRouter)

    app = FastAPI()
    app.include_router(api_router)
    paths = app.openapi().get("paths", {})
    assert {path for path in paths if path.startswith("/api/")} == {
        "/api/auth/login",
        "/api/auth/logout",
        "/api/auth/me",
        "/api/auth/me/preferred-language",
        "/api/users",
        "/api/users/{user_id}",
        "/api/users/{user_id}/roles",
        "/api/roles",
        "/api/cases",
        "/api/cases/assignees",
        "/api/cases/{case_id}",
        "/api/cases/{case_id}/archive",
        "/api/cases/{case_id}/workflows/run",
        "/api/cases/{case_id}/extraction/fields",
        "/api/cases/{case_id}/extraction/fields/{field_id}",
        "/api/cases/{case_id}/draft",
        "/api/cases/{case_id}/risk-assessment",
        "/api/cases/{case_id}/audit",
        "/api/documents",
        "/api/documents/upload",
        "/api/documents/{document_id}",
        "/api/documents/{document_id}/context",
        "/api/documents/{document_id}/reprocess",
        "/api/documents/{document_id}/reindex",
        "/api/documents/{document_id}/source-status",
        "/api/retrieval/search",
        "/api/retrieval/answer",
        "/api/evaluations/datasets",
        "/api/evaluations/datasets/{dataset_key}/runs",
        "/api/evaluations/runs",
        "/api/evaluations/runs/{evaluation_run_id}",
        "/api/evaluations/runs/{evaluation_run_id}/results/{evaluation_result_id}",
        "/api/evaluations/runs/{evaluation_run_id}/report",
        "/api/workflows/{workflow_run_id}",
        "/api/workflows/{workflow_run_id}/intake/correction",
        "/api/workflows/{workflow_run_id}/trace",
        "/api/audit/events",
        "/api/approvals",
        "/api/approvals/{approval_id}",
        "/api/approvals/{approval_id}/approve",
        "/api/approvals/{approval_id}/edit-and-approve",
        "/api/approvals/{approval_id}/reject",
        "/api/approvals/{approval_id}/request-more-evidence",
        "/api/approvals/{approval_id}/reassign",
        "/api/approvals/{approval_id}/exports/{export_format}",
        "/api/approvals/{approval_id}/mock-handoffs",
        "/api/admin/memory/settings",
        "/api/admin/memory/entries",
        "/api/admin/memory/entries/{memory_entry_id}",
        "/api/admin/memory/entries/{memory_entry_id}/archive",
    }


def test_openapi_tags_describe_each_boundary() -> None:
    tags = openapi_tags()
    assert [tag["name"] for tag in tags] == [group.tag for group in ROUTE_GROUPS]
    for tag in tags:
        assert tag["description"].strip()
