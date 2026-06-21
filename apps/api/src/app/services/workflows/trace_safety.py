"""Response-side safety projection for workflow traces and audit metadata."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence

_MAX_DEPTH = 4
_MAX_KEYS = 32
_MAX_ITEMS = 32
_MAX_STRING_LENGTH = 160
_CODE = re.compile(r"^[a-z][a-z0-9_]{0,99}$")

# Normalize keys before matching so ``Authorization-Header``, ``AUTH_token``,
# and nested spelling variants receive the same default-deny treatment.
_FORBIDDEN_KEY_PARTS = frozenset(
    {
        "secret",
        "authorization",
        "cookie",
        "credential",
        "password",
        "token",
        "prompt",
        "request",
        "response",
        "body",
        "query",
        "excerpt",
        "embedding",
        "vector",
        "storage",
        "objectkey",
        "checksum",
        "sql",
        "exception",
        "traceback",
        "stacktrace",
        "ipaddress",
        "useragent",
        "content",
        "rawtext",
        "documenttext",
        "message",
    }
)


def sanitize_metadata(value: object) -> dict[str, object]:
    """Return a bounded JSON-safe metadata projection with no sensitive-key paths.

    Trace and audit rows remain untrusted after they are read from PostgreSQL.
    Unsafe fields are omitted instead of copied or rendered; unknown objects are
    reduced recursively and malformed values become a neutral ``None`` marker.
    """

    sanitized = _sanitize(value, depth=0)
    return sanitized if isinstance(sanitized, dict) else {}


def controlled_code(value: object) -> str | None:
    """Expose a persisted failure only when it is a closed machine-readable code."""

    return value if isinstance(value, str) and _CODE.fullmatch(value) is not None else None


def _sanitize(value: object, *, depth: int) -> object:
    if depth > _MAX_DEPTH:
        return None
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        return value[:_MAX_STRING_LENGTH]
    if isinstance(value, Mapping):
        safe: dict[str, object] = {}
        for key, item in list(value.items())[:_MAX_KEYS]:
            if not isinstance(key, str) or _forbidden_key(key):
                continue
            safe[key[:100]] = _sanitize(item, depth=depth + 1)
        return safe
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [_sanitize(item, depth=depth + 1) for item in value[:_MAX_ITEMS]]
    return None


def _forbidden_key(key: str) -> bool:
    normalized = "".join(character for character in key.casefold() if character.isalnum())
    return any(part in normalized for part in _FORBIDDEN_KEY_PARTS)
