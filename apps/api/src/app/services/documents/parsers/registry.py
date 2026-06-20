"""Format-specific text extraction keyed only by the trusted stored file type."""

from __future__ import annotations

import csv
import re
from collections.abc import Callable, Iterable
from email import policy
from email.message import Message
from email.parser import BytesParser
from html.parser import HTMLParser
from io import BytesIO, StringIO

from docx import Document as DocxDocument
from openpyxl import load_workbook  # type: ignore[import-untyped]
from pypdf import PdfReader

from app.services.documents.parsers.types import (
    LocationSpan,
    ParsedDocument,
    ParseFailure,
    SafeParseErrorCode,
)

type _Parser = Callable[[bytes], ParsedDocument]
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


class _HtmlToText(HTMLParser):
    """A small, dependency-free HTML fallback for EML bodies only."""

    _BLOCK_TAGS = frozenset({"br", "div", "p", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag.casefold() in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


class DocumentParserRegistry:
    """Parse trusted bytes with bounded normalized results and locator metadata."""

    def __init__(self, *, maximum_characters: int, maximum_sections: int) -> None:
        self.maximum_characters = maximum_characters
        self.maximum_sections = maximum_sections
        self._parsers: dict[str, _Parser] = {
            "pdf": self._parse_pdf,
            "docx": self._parse_docx,
            "txt": self._parse_txt,
            "markdown": self._parse_markdown,
            "csv": self._parse_csv,
            "xlsx": self._parse_xlsx,
            "eml": self._parse_eml,
        }

    def parse(self, *, file_type: str, payload: bytes) -> ParsedDocument:
        """Select exactly one parser from trusted database metadata."""

        parser = self._parsers.get(file_type)
        if parser is None:
            raise ParseFailure(SafeParseErrorCode.UNSUPPORTED_TYPE)
        try:
            parsed = parser(payload)
        except ParseFailure:
            raise
        except Exception as error:
            # Library/provider exceptions can carry raw document details; do not preserve them.
            del error
            raise ParseFailure(SafeParseErrorCode.MALFORMED_DOCUMENT) from None
        return self._bounded(parsed)

    def _parse_pdf(self, payload: bytes) -> ParsedDocument:
        reader = PdfReader(BytesIO(payload), strict=False)
        sections = [
            (f"Page {index}", page.extract_text() or "", index)
            for index, page in enumerate(reader.pages, 1)
        ]
        return _from_sections(
            sections,
            kind="page",
            parser_name="pypdf",
            page_count=len(reader.pages),
        )

    def _parse_docx(self, payload: bytes) -> ParsedDocument:
        document = DocxDocument(BytesIO(payload))
        sections: list[tuple[str | None, str, int | None]] = []
        current_heading: str | None = None
        current_lines: list[str] = []
        for paragraph in document.paragraphs:
            text = paragraph.text
            if not text.strip():
                continue
            style_name = paragraph.style.name if paragraph.style is not None else ""
            if style_name.casefold().startswith("heading"):
                if current_lines:
                    sections.append((current_heading, "\n".join(current_lines), None))
                    current_lines = []
                current_heading = text
            else:
                current_lines.append(text)
        if current_lines:
            sections.append((current_heading, "\n".join(current_lines), None))
        return _from_sections(sections, kind="section", parser_name="python-docx")

    def _parse_txt(self, payload: bytes) -> ParsedDocument:
        return _from_sections(
            [(None, _decode_utf8(payload), None)], kind="section", parser_name="utf-8"
        )

    def _parse_markdown(self, payload: bytes) -> ParsedDocument:
        text = _decode_utf8(payload)
        sections: list[tuple[str | None, str, int | None]] = []
        heading: str | None = None
        lines: list[str] = []
        for line in text.splitlines():
            match = _HEADING.match(line)
            if match:
                if lines:
                    sections.append((heading, "\n".join(lines), None))
                    lines = []
                heading = match.group(2)
            else:
                lines.append(line)
        if lines or heading is not None:
            sections.append((heading, "\n".join(lines), None))
        return _from_sections(sections, kind="section", parser_name="markdown")

    def _parse_csv(self, payload: bytes) -> ParsedDocument:
        rows = list(csv.reader(StringIO(_decode_utf8(payload), newline="")))
        if not rows:
            raise ParseFailure(SafeParseErrorCode.EMPTY_TEXT)
        header = rows[0]
        sections: list[tuple[str | None, str, int | None]] = [("Header", " | ".join(header), None)]
        for index, row in enumerate(rows[1:], 1):
            values = [
                f"{header[column] if column < len(header) else f'Column {column + 1}'}: {value}"
                for column, value in enumerate(row)
            ]
            sections.append((f"Row {index}", " | ".join(values), None))
        return _from_sections(sections, kind="row", parser_name="csv")

    def _parse_xlsx(self, payload: bytes) -> ParsedDocument:
        workbook = load_workbook(BytesIO(payload), read_only=True, data_only=False)
        sections: list[tuple[str | None, str, int | None]] = []
        try:
            for worksheet in workbook.worksheets:
                rows: list[str] = []
                for row in worksheet.iter_rows(values_only=True):
                    values = ["" if value is None else str(value) for value in row]
                    if any(values):
                        rows.append(" | ".join(values))
                if rows:
                    sections.append((worksheet.title, "\n".join(rows), None))
        finally:
            workbook.close()
        return _from_sections(sections, kind="worksheet", parser_name="openpyxl")

    def _parse_eml(self, payload: bytes) -> ParsedDocument:
        message = BytesParser(policy=policy.default).parsebytes(payload)
        if not message.keys():
            raise ParseFailure(SafeParseErrorCode.MALFORMED_DOCUMENT)
        header_names = {"from", "to", "cc", "subject", "date"}
        headers = [
            f"{name}: {value}" for name, value in message.items() if name.casefold() in header_names
        ]
        plain: list[str] = []
        html_bodies: list[str] = []
        parts: Iterable[Message] = message.walk() if message.is_multipart() else (message,)
        for part in parts:
            # ``walk`` returns Message instances; attribute access is intentionally narrow.
            if part.get_content_disposition() == "attachment":
                continue
            content_type = part.get_content_type()
            if content_type not in {"text/plain", "text/html"}:
                continue
            raw_body = part.get_payload(decode=True)
            if not isinstance(raw_body, bytes):
                continue
            try:
                body = raw_body.decode(part.get_content_charset() or "utf-8", errors="replace")
            except LookupError:
                continue
            if content_type == "text/plain":
                plain.append(body)
            else:
                extractor = _HtmlToText()
                extractor.feed(body)
                html_bodies.append(extractor.text())
        body = "\n\n".join(plain) if plain else "\n\n".join(html_bodies)
        sections = [("Headers", "\n".join(headers), None), ("Body", body, None)]
        return _from_sections(sections, kind="section", parser_name="email")

    def _bounded(self, parsed: ParsedDocument) -> ParsedDocument:
        if len(parsed.extracted_text) > self.maximum_characters:
            raise ParseFailure(SafeParseErrorCode.TEXT_LIMIT_EXCEEDED)
        if len(parsed.spans) > self.maximum_sections:
            raise ParseFailure(SafeParseErrorCode.SECTION_LIMIT_EXCEEDED)
        if not parsed.extracted_text.strip() or not parsed.spans:
            raise ParseFailure(SafeParseErrorCode.EMPTY_TEXT)
        previous_end = 0
        for span in parsed.spans:
            if (
                span.start < previous_end
                or span.end <= span.start
                or span.end > len(parsed.extracted_text)
            ):
                raise ParseFailure(SafeParseErrorCode.MALFORMED_DOCUMENT)
            previous_end = span.end
        return parsed


def _decode_utf8(payload: bytes) -> str:
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError:
        raise ParseFailure(SafeParseErrorCode.MALFORMED_DOCUMENT) from None


def _normalized(text: str) -> str:
    """Normalize only line endings/trailing horizontal whitespace deterministically."""

    normalized_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip() for line in normalized_lines).strip()


def _from_sections(
    sections: Iterable[tuple[str | None, str, int | None]],
    *,
    kind: str,
    parser_name: str,
    page_count: int | None = None,
) -> ParsedDocument:
    parts: list[str] = []
    spans: list[LocationSpan] = []
    text_length = 0
    for label, raw_text, page_number in sections:
        text = _normalized(raw_text)
        if not text:
            continue
        if parts:
            parts.append("\n\n")
            text_length += 2
        start = text_length
        parts.append(text)
        end = start + len(text)
        text_length = end
        spans.append(
            LocationSpan(
                start=start,
                end=end,
                kind=kind,
                label=label,
                page_number=page_number,
            )
        )
    return ParsedDocument(
        extracted_text="".join(parts),
        spans=tuple(spans),
        page_count=page_count,
        parser_name=parser_name,
        parser_version="1",
    )
