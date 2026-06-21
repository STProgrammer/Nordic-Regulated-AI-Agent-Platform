"""Integration-facing contract checks for workflow trace persistence additions."""

from app.db.models.workflow import WorkflowToolCall


def test_workflow_tool_call_model_is_metadata_only() -> None:
    """The ORM model deliberately has summaries but no payload/body/content columns."""

    columns = set(WorkflowToolCall.__table__.columns.keys())
    assert {"tool_name", "status", "input_summary", "output_summary", "error_summary"} <= columns
    assert not {"payload", "result", "headers", "url", "request_body", "response_body"} & columns
