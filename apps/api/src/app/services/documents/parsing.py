"""Worker-only document parsing lifecycle coordination."""

from __future__ import annotations

from enum import StrEnum
from hashlib import sha256
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.observability import get_telemetry
from app.db.models.document import Document
from app.db.repositories.document import DocumentRepository
from app.services.audit.service import AuditEventInput, AuditService, JSONValue
from app.services.documents.parsers.language import detect_language
from app.services.documents.parsers.registry import DocumentParserRegistry
from app.services.documents.parsers.types import ParseFailure, SafeParseErrorCode
from app.services.documents.storage import (
    ObjectNotFoundError,
    ObjectStorage,
    ObjectStorageError,
    ObjectTooLargeError,
)

_logger = get_logger("documents.parsing")
_TRANSIENT_SUMMARY = "Document parsing is temporarily unavailable."


class ParseProcessOutcome(StrEnum):
    """Task-facing state that never needs to include source/provider detail."""

    NOOP = "noop"
    PARSED = "parsed"
    PERMANENT_FAILURE = "permanent_failure"
    TRANSIENT_FAILURE = "transient_failure"


class DocumentParseCoordinator:
    """Claim, integrity-check, parse, and persist one document in safe transactions."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        storage: ObjectStorage,
        registry: DocumentParserRegistry,
        maximum_input_bytes: int,
        language_minimum_characters: int,
        language_confidence_threshold: float,
    ) -> None:
        self.session = session
        self.repository = DocumentRepository(session)
        self.audit = AuditService(session)
        self.storage = storage
        self.registry = registry
        self.maximum_input_bytes = maximum_input_bytes
        self.language_minimum_characters = language_minimum_characters
        self.language_confidence_threshold = language_confidence_threshold

    async def process(self, document_id: UUID) -> ParseProcessOutcome:
        """Run one idempotent parser attempt; transient callers requeue through Celery."""

        try:
            async with self.session.begin():
                document = await self.repository.claim_pending(document_id)
            if document is None:
                return ParseProcessOutcome.NOOP
        except SQLAlchemyError as error:
            _logger.warning("document.claim_unavailable", error_type=type(error).__name__)
            return ParseProcessOutcome.TRANSIENT_FAILURE

        try:
            with get_telemetry().span("document.parse", {"document.operation": "parse"}):
                payload = await self._verified_payload(document)
                parsed = self.registry.parse(file_type=document.file_type, payload=payload)
                language = detect_language(
                    parsed.extracted_text,
                    minimum_characters=self.language_minimum_characters,
                    confidence_threshold=self.language_confidence_threshold,
                )
        except ParseFailure as error:
            await self._record_permanent_failure(document_id, error)
            return ParseProcessOutcome.PERMANENT_FAILURE
        except ObjectNotFoundError:
            await self._record_permanent_failure(
                document_id, ParseFailure(SafeParseErrorCode.OBJECT_MISSING)
            )
            return ParseProcessOutcome.PERMANENT_FAILURE
        except ObjectTooLargeError:
            await self._record_permanent_failure(
                document_id, ParseFailure(SafeParseErrorCode.INPUT_TOO_LARGE)
            )
            return ParseProcessOutcome.PERMANENT_FAILURE
        except ObjectStorageError as error:
            _logger.warning("document.private_read_unavailable", error_type=type(error).__name__)
            await self._return_to_pending(document_id)
            return ParseProcessOutcome.TRANSIENT_FAILURE
        except Exception as error:
            _logger.warning("document.parser_unavailable", error_type=type(error).__name__)
            await self._return_to_pending(document_id)
            return ParseProcessOutcome.TRANSIENT_FAILURE

        metadata: dict[str, object] = {
            "parser": {"name": parsed.parser_name, "version": parsed.parser_version},
            "language": {"value": language.language, "confidence": language.confidence},
            "text_length": len(parsed.extracted_text),
            "page_count": parsed.page_count,
            "locations": [span.as_metadata() for span in parsed.spans],
        }
        try:
            async with self.session.begin():
                completed = await self.repository.complete_parse(
                    document_id,
                    extracted_text=parsed.extracted_text,
                    extraction_metadata=metadata,
                    language=language.language,
                    page_count=parsed.page_count,
                )
                if completed is None:
                    return ParseProcessOutcome.NOOP
                await self._record_terminal_event(
                    completed,
                    event_type="document.parsed",
                    event_data={
                        "file_type": completed.file_type,
                        "transition": "parsed",
                        "language": language.language,
                        "page_count": parsed.page_count,
                        "text_length": len(parsed.extracted_text),
                    },
                )
            return ParseProcessOutcome.PARSED
        except SQLAlchemyError as error:
            _logger.warning("document.parse_persist_unavailable", error_type=type(error).__name__)
            await self._return_to_pending(document_id)
            return ParseProcessOutcome.TRANSIENT_FAILURE

    async def mark_exhausted_retry(self, document_id: UUID) -> None:
        """Turn an unrecoverable pending infrastructure retry into a safe terminal state."""

        try:
            async with self.session.begin():
                failed = await self.repository.fail_pending(
                    document_id, parsing_error=_TRANSIENT_SUMMARY
                )
                if failed is not None:
                    await self._record_terminal_event(
                        failed,
                        event_type="document.parse_failed",
                        event_data={
                            "file_type": failed.file_type,
                            "transition": "failed",
                            "failure_code": "infrastructure_unavailable",
                        },
                    )
                    get_telemetry().parsing_failure(outcome="infrastructure_unavailable")
        except SQLAlchemyError as error:
            _logger.warning(
                "document.retry_exhaustion_persist_unavailable",
                error_type=type(error).__name__,
            )

    async def _verified_payload(self, document: Document) -> bytes:
        if document.file_size_bytes > self.maximum_input_bytes:
            raise ParseFailure(SafeParseErrorCode.INPUT_TOO_LARGE)
        payload = await self.storage.get_bytes(
            key=document.object_storage_key, maximum_bytes=self.maximum_input_bytes
        )
        if (
            len(payload) != document.file_size_bytes
            or sha256(payload).hexdigest() != document.checksum_sha256
        ):
            raise ParseFailure(SafeParseErrorCode.INTEGRITY_MISMATCH)
        return payload

    async def _record_permanent_failure(self, document_id: UUID, failure: ParseFailure) -> None:
        try:
            async with self.session.begin():
                failed = await self.repository.fail_parse(
                    document_id, parsing_error=failure.summary
                )
                if failed is not None:
                    await self._record_terminal_event(
                        failed,
                        event_type="document.parse_failed",
                        event_data={
                            "file_type": failed.file_type,
                            "transition": "failed",
                            "failure_code": failure.code.value,
                        },
                    )
                    get_telemetry().parsing_failure(outcome=failure.code.value)
        except SQLAlchemyError as error:
            _logger.warning(
                "document.parse_failure_persist_unavailable",
                error_type=type(error).__name__,
            )

    async def _return_to_pending(self, document_id: UUID) -> None:
        try:
            async with self.session.begin():
                await self.repository.return_to_pending(document_id)
        except SQLAlchemyError as error:
            _logger.warning("document.retry_release_unavailable", error_type=type(error).__name__)

    async def _record_terminal_event(
        self,
        document: Document,
        *,
        event_type: str,
        event_data: dict[str, JSONValue],
    ) -> None:
        await self.audit.record_event(
            AuditEventInput(
                organization_id=document.organization_id,
                event_type=event_type,
                resource_type="document",
                resource_id=document.id,
                case_id=document.case_id,
                event_data=event_data,
                include_archived_case=True,
            )
        )
