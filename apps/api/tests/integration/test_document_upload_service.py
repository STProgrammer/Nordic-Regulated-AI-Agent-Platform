"""Database-backed document ingestion and audit/compensation coverage."""

from __future__ import annotations

import asyncio
from typing import Protocol
from uuid import UUID

import pytest
from app.core.config import AppSettings
from app.db.models import AuditEvent, Document
from app.db.session import dispose_database_engines, get_sessionmaker
from app.services.audit.service import AuditEventInput, AuditService
from app.services.auth.principal import Principal, RoleName
from app.services.documents.service import DocumentService, DocumentUpload
from app.services.errors import InvalidCommandError
from sqlalchemy import func, select


class TenantSeed(Protocol):
    primary_organization_id: UUID
    primary_user_id: UUID
    primary_case_id: UUID


class _StorageFake:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []

    async def put_bytes(self, *, key: str, payload: bytes, content_type: str) -> None:
        self.objects[key] = payload

    async def delete(self, *, key: str) -> None:
        self.objects.pop(key, None)
        self.deleted.append(key)

    async def get_bytes(self, *, key: str, maximum_bytes: int) -> bytes:
        del maximum_bytes
        return self.objects[key]


class _FailingAuditService(AuditService):
    async def record_event(self, command: AuditEventInput) -> AuditEvent:
        del command
        raise InvalidCommandError("Synthetic audit failure.")


def _principal(seed: TenantSeed) -> Principal:
    return Principal(
        user_id=seed.primary_user_id,
        organization_id=seed.primary_organization_id,
        display_name="Primary Example",
        preferred_language="nb",
        roles=frozenset({RoleName.CASE_WORKER}),
    )


def test_document_upload_persists_safe_metadata_and_one_audit_event(
    database_settings: AppSettings, tenant_seed: TenantSeed
) -> None:
    asyncio.run(_successful_upload(database_settings, tenant_seed))


async def _successful_upload(settings: AppSettings, seed: TenantSeed) -> None:
    storage = _StorageFake()
    try:
        async with get_sessionmaker(settings)() as session:
            service = DocumentService(session, storage=storage, maximum_upload_bytes=1024)
            document = await service.upload(
                _principal(seed),
                DocumentUpload(
                    case_id=seed.primary_case_id,
                    email_text="From: sender@example.invalid\n\nSynthetic body",
                ),
            )
            await session.commit()

            persisted = await session.get(Document, document.id)
            event = await session.scalar(
                select(AuditEvent).where(
                    AuditEvent.event_type == "document.uploaded",
                    AuditEvent.resource_id == document.id,
                )
            )
            assert persisted is not None
            assert persisted.case_id == seed.primary_case_id
            assert persisted.uploaded_by_user_id == seed.primary_user_id
            assert persisted.source_status == "draft"
            assert persisted.confidentiality_level == "internal"
            assert persisted.parsing_status == "pending"
            assert persisted.file_size_bytes == len(next(iter(storage.objects.values())))
            assert len(persisted.checksum_sha256) == 64
            assert event is not None
            assert event.case_id == seed.primary_case_id
            assert event.actor_user_id == seed.primary_user_id
            assert event.event_data == {
                "file_type": "eml",
                "file_size_bytes": persisted.file_size_bytes,
                "source_status": "draft",
                "confidentiality_level": "internal",
                "parsing_status": "pending",
            }
    finally:
        await dispose_database_engines()


def test_document_upload_compensates_private_object_when_audit_write_fails(
    database_settings: AppSettings, tenant_seed: TenantSeed
) -> None:
    asyncio.run(_failed_audit_upload(database_settings, tenant_seed))


async def _failed_audit_upload(settings: AppSettings, seed: TenantSeed) -> None:
    storage = _StorageFake()
    try:
        async with get_sessionmaker(settings)() as session:
            service = DocumentService(session, storage=storage, maximum_upload_bytes=1024)

            service.audit = _FailingAuditService(session)
            with pytest.raises(InvalidCommandError):
                await service.upload(
                    _principal(seed),
                    DocumentUpload(
                        case_id=seed.primary_case_id,
                        email_text="From: sender@example.invalid\n\nSynthetic body",
                    ),
                )
            await session.rollback()
            assert storage.objects == {}
            assert len(storage.deleted) == 1
            assert await session.scalar(select(func.count()).select_from(Document)) == 2
            assert await session.scalar(select(func.count()).select_from(AuditEvent)) == 0
    finally:
        await dispose_database_engines()
