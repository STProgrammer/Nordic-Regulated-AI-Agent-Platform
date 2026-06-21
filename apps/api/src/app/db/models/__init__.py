"""Intentional model-registration import point for Alembic and tests."""

from app.db.models.audit import AuditEvent
from app.db.models.case import Case
from app.db.models.document import Document, DocumentChunk, DocumentText
from app.db.models.evaluation import EvalCase, EvalDataset, EvalResult, EvalRun
from app.db.models.identity import Role, User, UserRole
from app.db.models.memory import MemoryEntry, MemoryUsageRecord
from app.db.models.organization import Organization
from app.db.models.prompt import ModelUsageRecord, PromptVersion
from app.db.models.workflow import (
    AgentMessage,
    Approval,
    ExtractedField,
    RetrievedSource,
    RiskAssessment,
    WorkflowNodeRun,
    WorkflowRun,
    WorkflowToolCall,
)

__all__ = [
    "AgentMessage",
    "Approval",
    "AuditEvent",
    "Case",
    "Document",
    "DocumentChunk",
    "DocumentText",
    "EvalCase",
    "EvalDataset",
    "EvalResult",
    "EvalRun",
    "ExtractedField",
    "MemoryEntry",
    "MemoryUsageRecord",
    "ModelUsageRecord",
    "Organization",
    "PromptVersion",
    "RetrievedSource",
    "RiskAssessment",
    "Role",
    "User",
    "UserRole",
    "WorkflowNodeRun",
    "WorkflowRun",
    "WorkflowToolCall",
]
