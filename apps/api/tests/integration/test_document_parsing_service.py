"""Database-backed parsing lifecycle invariants with private-storage fakes."""

from __future__ import annotations

import asyncio
from hashlib import sha256
from typing import Protocol
from uuid import UUID

from app.core.config import AppSettings
from app.db.models import Case, Document, DocumentText
from app.db.repositories.document import DocumentRepository
from app.db.session import dispose_database_engines, get_sessionmaker
from app.services.documents.parsers.registry import DocumentParserRegistry
from app.services.documents.parsing import DocumentParseCoordinator, ParseProcessOutcome
from app.services.documents.storage import ObjectNotFoundError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class TenantSeed(Protocol):
    """Fields from the shared seed fixture required by this focused lifecycle suite."""

    primary_organization_id: UUID
    primary_case_id: UUID
    primary_document_id: UUID


class _PrivateStorageFake:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects
        self.requests: list[tuple[str, int]] = []

    async def put_bytes(self, *, key: str, payload: bytes, content_type: str) -> None:
        del content_type
        self.objects[key] = payload

    async def delete(self, *, key: str) -> None:
        self.objects.pop(key, None)

    async def get_bytes(self, *, key: str, maximum_bytes: int) -> bytes:
        self.requests.append((key, maximum_bytes))
        if key not in self.objects:
            raise ObjectNotFoundError()
        payload = self.objects[key]
        return payload


def test_successful_parse_persists_one_canonical_text_record(
    database_settings: AppSettings, tenant_seed: TenantSeed
) -> None:
    asyncio.run(_successful_parse(database_settings, tenant_seed))


async def _successful_parse(settings: AppSettings, seed: TenantSeed) -> None:
    payload = (
        b"This is a sufficiently long English synthetic document for parser lifecycle testing."
    )
    try:
        async with get_sessionmaker(settings)() as session:
            document = await _prepare_document(session, seed.primary_document_id, payload)
            storage = _PrivateStorageFake({document.object_storage_key: payload})
            outcome = await _coordinator(session, storage).process(document.id)

            await session.refresh(document)
            text_record = await session.scalar(
                select(DocumentText).where(DocumentText.document_id == document.id)
            )
            assert outcome == ParseProcessOutcome.PARSED
            assert document.parsing_status == "parsed"
            assert document.parsing_error is None
            assert document.indexing_status == "pending"
            assert document.indexing_error is None
            assert document.language == "en"
            assert text_record is not None
            assert text_record.extracted_text == payload.decode()
            assert text_record.extraction_metadata["text_length"] == len(payload)
            assert storage.requests == [(document.object_storage_key, 1024)]
    finally:
        await dispose_database_engines()


def test_failed_reparse_preserves_last_good_text_and_case_state(
    database_settings: AppSettings, tenant_seed: TenantSeed
) -> None:
    asyncio.run(_failed_reparse_preserves_text(database_settings, tenant_seed))


async def _failed_reparse_preserves_text(settings: AppSettings, seed: TenantSeed) -> None:
    original = "Last good extracted text."
    payload = b"different raw bytes"
    try:
        async with get_sessionmaker(settings)() as session:
            document = await _prepare_document(session, seed.primary_document_id, payload)
            document.parsing_status = "parsed"
            document.language = "en"
            session.add(
                DocumentText(
                    document_id=document.id,
                    extracted_text=original,
                    extraction_metadata={"parser": {"name": "synthetic", "version": "1"}},
                )
            )
            await session.commit()
            case = await session.get(Case, seed.primary_case_id)
            assert case is not None
            original_case_status = case.status

            requested = await DocumentRepository(session).request_reprocess(
                seed.primary_organization_id, document.id
            )
            assert requested is not None
            await session.commit()

            # The stored metadata expects the original payload; this fake returns
            # tampered bytes and must fail before the parser sees them.
            storage = _PrivateStorageFake({document.object_storage_key: b"tampered"})
            outcome = await _coordinator(session, storage).process(document.id)

            await session.refresh(document)
            await session.refresh(case)
            text_record = await session.scalar(
                select(DocumentText).where(DocumentText.document_id == document.id)
            )
            assert outcome == ParseProcessOutcome.PERMANENT_FAILURE
            assert document.parsing_status == "failed"
            assert (
                document.parsing_error == "The stored document did not pass integrity verification."
            )
            assert text_record is not None
            assert text_record.extracted_text == original
            assert case.status == original_case_status
    finally:
        await dispose_database_engines()


async def _prepare_document(session: AsyncSession, document_id: UUID, payload: bytes) -> Document:
    """Set existing synthetic metadata to one valid private text-object boundary."""

    # Keep this helper intentionally small so test setup cannot bypass the same
    # document row used by the coordinator under test.
    document = await session.get(Document, document_id)
    assert document is not None
    document.file_type = "txt"
    document.file_size_bytes = len(payload)
    document.checksum_sha256 = sha256(payload).hexdigest()
    document.parsing_status = "pending"
    document.parsing_error = None
    document.language = None
    document.page_count = None
    await session.commit()
    return document


def _coordinator(session: AsyncSession, storage: _PrivateStorageFake) -> DocumentParseCoordinator:
    return DocumentParseCoordinator(
        session,
        storage=storage,
        registry=DocumentParserRegistry(maximum_characters=10_000, maximum_sections=100),
        maximum_input_bytes=1024,
        language_minimum_characters=20,
        language_confidence_threshold=0.8,
    )
