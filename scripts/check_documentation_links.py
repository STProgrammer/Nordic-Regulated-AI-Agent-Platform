"""Validate repository-relative Markdown links in reviewer-facing documentation."""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
LINK_PATTERN = re.compile(r"!?\[[^\]\n]*\]\(([^)\n]+)\)")
HEADING_PATTERN = re.compile(r"^#{1,6}[ \t]+(.+?)[ \t]*#*[ \t]*$", re.MULTILINE)
EXTERNAL_SCHEMES = frozenset({"data", "http", "https", "mailto", "tel"})


def documentation_files() -> list[Path]:
    """Return the public Markdown documents whose local links form the review surface."""

    fixed_files = (
        ROOT / "README.md",
        ROOT / "SECURITY.md",
        ROOT / "apps/web/README.md",
        ROOT / "infra/README.md",
        ROOT / "sample-data/README.md",
    )
    return [*fixed_files, *sorted((ROOT / "docs").rglob("*.md"))]


def github_slug(heading: str) -> str:
    """Return the GitHub-compatible anchor slug for a Markdown heading."""

    without_html = re.sub(r"<[^>]+>", "", heading)
    without_punctuation = re.sub(r"[^\w\s-]", "", without_html.casefold(), flags=re.UNICODE)
    return re.sub(r"\s", "-", without_punctuation.strip())


def anchors_in(document: Path) -> set[str]:
    """Collect explicit GitHub heading anchors, including duplicate-heading suffixes."""

    counts: dict[str, int] = {}
    anchors: set[str] = set()
    for match in HEADING_PATTERN.finditer(document.read_text(encoding="utf-8")):
        slug = github_slug(match.group(1))
        if not slug:
            continue
        occurrence = counts.get(slug, 0)
        counts[slug] = occurrence + 1
        anchors.add(slug if occurrence == 0 else f"{slug}-{occurrence}")
    return anchors


def local_markdown_targets(document: Path) -> Iterable[str]:
    """Yield inline Markdown link destinations from one document."""

    for match in LINK_PATTERN.finditer(document.read_text(encoding="utf-8")):
        destination = match.group(1).strip()
        if destination.startswith("<") and destination.endswith(">"):
            destination = destination[1:-1]
        yield destination.split(maxsplit=1)[0]


def validate_document(document: Path, anchor_cache: dict[Path, set[str]]) -> list[str]:
    """Return human-readable validation errors for local links in ``document``."""

    errors: list[str] = []
    for destination in local_markdown_targets(document):
        parsed = urlsplit(destination)
        if parsed.scheme.casefold() in EXTERNAL_SCHEMES or destination.startswith("//"):
            continue

        target_path = unquote(parsed.path)
        target = (document.parent / target_path).resolve() if target_path else document.resolve()
        relative_document = document.relative_to(ROOT)
        if not target.is_relative_to(ROOT):
            errors.append(f"{relative_document}: link escapes repository: {destination}")
            continue
        if not target.exists():
            errors.append(f"{relative_document}: missing target: {destination}")
            continue
        if not parsed.fragment:
            continue
        if target.suffix.casefold() != ".md":
            errors.append(f"{relative_document}: fragment target is not Markdown: {destination}")
            continue

        anchors = anchor_cache.setdefault(target, anchors_in(target))
        fragment = unquote(parsed.fragment)
        if fragment not in anchors:
            errors.append(f"{relative_document}: missing heading fragment: {destination}")
    return errors


def main() -> int:
    """Validate every reviewer-facing document and return a conventional shell status."""

    documents = documentation_files()
    anchor_cache: dict[Path, set[str]] = {}
    errors = [
        error for document in documents for error in validate_document(document, anchor_cache)
    ]
    if errors:
        print("Documentation link validation failed:", file=sys.stderr)
        print(*errors, sep="\n", file=sys.stderr)
        return 1

    print(f"Documentation link validation passed ({len(documents)} files checked).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
