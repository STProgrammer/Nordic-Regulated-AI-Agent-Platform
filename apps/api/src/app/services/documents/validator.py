"""Bounded structural validation for supported raw document payloads."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import PurePosixPath
from typing import Protocol
from zipfile import BadZipFile, ZipFile

from app.services.errors import (
    InvalidCommandError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)

_READ_CHUNK_BYTES = 64 * 1024
_MAX_ARCHIVE_ENTRIES = 10_000
_MAX_ARCHIVE_UNCOMPRESSED_BYTES = 256 * 1024 * 1024


@dataclass(frozen=True)
class _FormatSpec:
    file_type: str
    mime_type: str
    kind: str


_FORMATS: dict[str, _FormatSpec] = {
    "pdf": _FormatSpec("pdf", "application/pdf", "pdf"),
    "docx": _FormatSpec(
        "docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"
    ),
    "txt": _FormatSpec("txt", "text/plain", "text"),
    "md": _FormatSpec("markdown", "text/markdown", "text"),
    "csv": _FormatSpec("csv", "text/csv", "text"),
    "xlsx": _FormatSpec(
        "xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
    ),
    "eml": _FormatSpec("eml", "message/rfc822", "text"),
}


class UploadFileLike(Protocol):
    """The small FastAPI upload surface needed by the domain validator."""

    filename: str | None
    content_type: str | None
    size: int | None

    async def read(self, size: int = -1) -> bytes:
        """Read the next bounded chunk from the incoming multipart part."""


@dataclass(frozen=True)
class ValidatedDocument:
    """Trusted metadata plus the exact bounded payload that will be stored."""

    payload: bytes
    file_type: str
    mime_type: str
    original_filename: str
    byte_size: int
    checksum_sha256: str


async def validate_upload_file(upload: UploadFileLike, *, maximum_bytes: int) -> ValidatedDocument:
    """Read an upload once with a hard byte cap before structural validation."""

    if upload.size is not None and upload.size > maximum_bytes:
        raise PayloadTooLargeError()

    payload = bytearray()
    while True:
        chunk = await upload.read(_READ_CHUNK_BYTES)
        if not chunk:
            break
        if not isinstance(chunk, bytes):
            raise InvalidCommandError("The document payload is invalid.")
        if len(payload) + len(chunk) > maximum_bytes:
            raise PayloadTooLargeError()
        payload.extend(chunk)

    return validate_document_bytes(
        bytes(payload),
        filename=upload.filename,
        declared_content_type=upload.content_type,
        maximum_bytes=maximum_bytes,
    )


def validate_email_text(email_text: str, *, maximum_bytes: int) -> ValidatedDocument:
    """Validate pasted email text using the same storage and integrity boundary."""

    try:
        payload = email_text.encode("utf-8")
    except UnicodeError as error:
        raise InvalidCommandError("The document payload is invalid.") from error
    return validate_document_bytes(
        payload,
        filename="pasted-email.eml",
        declared_content_type="message/rfc822",
        maximum_bytes=maximum_bytes,
    )


def validate_document_bytes(
    payload: bytes,
    *,
    filename: str | None,
    declared_content_type: str | None,
    maximum_bytes: int,
) -> ValidatedDocument:
    """Return trusted metadata only after content, extension, and MIME checks."""

    if not payload:
        raise InvalidCommandError("The document payload must not be empty.")
    if len(payload) > maximum_bytes:
        raise PayloadTooLargeError()

    original_filename, extension = _normalized_filename(filename)
    specification = _FORMATS.get(extension)
    if specification is None:
        raise UnsupportedMediaTypeError()
    if not _declared_type_is_compatible(specification, declared_content_type):
        raise UnsupportedMediaTypeError()
    _validate_content(specification, payload)

    return ValidatedDocument(
        payload=payload,
        file_type=specification.file_type,
        mime_type=specification.mime_type,
        original_filename=original_filename,
        byte_size=len(payload),
        checksum_sha256=sha256(payload).hexdigest(),
    )


def _normalized_filename(filename: str | None) -> tuple[str, str]:
    if filename is None:
        raise InvalidCommandError("A document filename is required.")
    basename = filename.replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    normalized = "".join(character for character in basename if character.isprintable()).strip()
    if not normalized or normalized in {".", ".."} or len(normalized) > 255:
        raise InvalidCommandError("The document filename is invalid.")
    if "." not in normalized or normalized.endswith("."):
        raise UnsupportedMediaTypeError()
    extension = normalized.rsplit(".", maxsplit=1)[1].casefold()
    return normalized, extension


def _declared_type_is_compatible(
    specification: _FormatSpec, declared_content_type: str | None
) -> bool:
    if declared_content_type is None:
        return True
    declared = declared_content_type.split(";", maxsplit=1)[0].strip().casefold()
    if not declared or declared == "application/octet-stream":
        return True
    if declared == specification.mime_type:
        return True
    return specification.kind == "text" and declared.startswith("text/")


def _validate_content(specification: _FormatSpec, payload: bytes) -> None:
    if specification.kind == "pdf":
        if not payload.startswith(b"%PDF-"):
            raise UnsupportedMediaTypeError()
        return
    if specification.kind in {"docx", "xlsx"}:
        _validate_ooxml(
            payload, expected_directory="word" if specification.kind == "docx" else "xl"
        )
        return
    _validate_utf8_text(payload)


def _validate_ooxml(payload: bytes, *, expected_directory: str) -> None:
    if not payload.startswith(b"PK"):
        raise UnsupportedMediaTypeError()
    try:
        with ZipFile(BytesIO(payload)) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > _MAX_ARCHIVE_ENTRIES:
                raise UnsupportedMediaTypeError()
            if sum(entry.file_size for entry in entries) > _MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                raise UnsupportedMediaTypeError()
            names: set[str] = set()
            for entry in entries:
                name = entry.filename.replace("\\", "/")
                path = PurePosixPath(name)
                if "\x00" in name or path.is_absolute() or ".." in path.parts:
                    raise UnsupportedMediaTypeError()
                names.add(name)
    except (BadZipFile, OSError, ValueError) as error:
        raise UnsupportedMediaTypeError() from error

    expected_member = f"{expected_directory}/document.xml"
    if expected_directory == "xl":
        expected_member = "xl/workbook.xml"
    if "[Content_Types].xml" not in names or expected_member not in names:
        raise UnsupportedMediaTypeError()


def _validate_utf8_text(payload: bytes) -> None:
    if b"\x00" in payload:
        raise UnsupportedMediaTypeError()
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise UnsupportedMediaTypeError() from error
    if any(ord(character) < 32 and character not in {"\t", "\n", "\r"} for character in text):
        raise UnsupportedMediaTypeError()
