"""Unit coverage for Phase 10 structural validation and opaque storage keys."""

from __future__ import annotations

import asyncio
from io import BytesIO
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest
from app.services.documents.keys import document_storage_key
from app.services.documents.validator import (
    validate_document_bytes,
    validate_email_text,
    validate_upload_file,
)
from app.services.errors import (
    InvalidCommandError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)


def _ooxml(*, directory: str, member: str) -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr(f"{directory}/{member}", "<document />")
    return stream.getvalue()


@pytest.mark.parametrize(
    ("filename", "payload", "file_type", "mime_type"),
    [
        ("sample.pdf", b"%PDF-1.7\nsynthetic", "pdf", "application/pdf"),
        (
            "sample.docx",
            _ooxml(directory="word", member="document.xml"),
            "docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        ("sample.txt", b"safe synthetic text\n", "txt", "text/plain"),
        ("sample.md", b"# Synthetic\n", "markdown", "text/markdown"),
        ("sample.csv", b"column\nvalue\n", "csv", "text/csv"),
        (
            "sample.xlsx",
            _ooxml(directory="xl", member="workbook.xml"),
            "xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        ("sample.eml", b"From: sender@example.invalid\n\nSynthetic body", "eml", "message/rfc822"),
    ],
)
def test_validator_accepts_every_supported_structural_format(
    filename: str, payload: bytes, file_type: str, mime_type: str
) -> None:
    document = validate_document_bytes(
        payload,
        filename=filename,
        declared_content_type="application/octet-stream",
        maximum_bytes=1024 * 1024,
    )

    assert document.file_type == file_type
    assert document.mime_type == mime_type
    assert document.byte_size == len(payload)
    assert len(document.checksum_sha256) == 64


def test_pasted_email_and_filename_normalization_are_safe() -> None:
    document = validate_email_text("From: sender@example.invalid\n\nSafe body", maximum_bytes=1024)
    normalized = validate_document_bytes(
        b"safe text",
        filename="C:\\unsafe-path\\safe.txt\x00",
        declared_content_type="text/plain",
        maximum_bytes=1024,
    )

    assert document.original_filename == "pasted-email.eml"
    assert normalized.original_filename == "safe.txt"


@pytest.mark.parametrize(
    ("filename", "payload", "declared_type", "error"),
    [
        ("archive.zip", b"PK\x03\x04", "application/zip", UnsupportedMediaTypeError),
        ("notes.txt", b"%PDF-1.7", "application/pdf", UnsupportedMediaTypeError),
        ("notes.txt", b"\x00binary", "text/plain", UnsupportedMediaTypeError),
        ("notes.txt", b"", "text/plain", InvalidCommandError),
    ],
)
def test_validator_rejects_unsafe_or_mismatched_inputs(
    filename: str, payload: bytes, declared_type: str, error: type[Exception]
) -> None:
    with pytest.raises(error):
        validate_document_bytes(
            payload,
            filename=filename,
            declared_content_type=declared_type,
            maximum_bytes=1024,
        )


class _StreamingUpload:
    filename: str | None = "synthetic.txt"
    content_type: str | None = "text/plain"
    size: int | None = None

    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = iter(chunks)

    async def read(self, size: int = -1) -> bytes:
        return next(self._chunks, b"")


def test_streaming_limit_is_enforced_without_trusting_content_length() -> None:
    with pytest.raises(PayloadTooLargeError):
        asyncio.run(
            validate_upload_file(_StreamingUpload([b"a" * 10, b"b" * 10]), maximum_bytes=15)
        )


def test_storage_keys_are_server_owned_and_exclude_filename_data() -> None:
    organization_id = uuid4()
    case_id = uuid4()
    first = document_storage_key(
        organization_id=organization_id,
        case_id=case_id,
        document_id=uuid4(),
    )
    second = document_storage_key(
        organization_id=organization_id,
        case_id=case_id,
        document_id=uuid4(),
    )

    assert first != second
    assert "unsafe-report.pdf" not in first
    assert first.startswith("v1/organizations/")


@pytest.mark.parametrize("attack", ["duplicate", "symlink", "compression_bomb"])
def test_validator_rejects_hostile_ooxml_archives(attack: str) -> None:
    stream = BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        if attack == "duplicate":
            archive.writestr("word/document.xml", "<document />")
            archive.writestr("word/document.xml", "<document />")
        elif attack == "symlink":
            member = ZipInfo("word/document.xml")
            member.external_attr = 0o120777 << 16
            archive.writestr(member, "<document />")
        else:
            archive.writestr("word/document.xml", b"x" * (256 * 1024))

    with pytest.raises(UnsupportedMediaTypeError):
        validate_document_bytes(
            stream.getvalue(),
            filename="hostile.docx",
            declared_content_type=(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
            maximum_bytes=1024 * 1024,
        )
