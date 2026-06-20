"""Safe sort primitives; repository callers must supply explicit allowlists."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy.sql.elements import ColumnElement

from app.services.errors import InvalidQueryError


class SortDirection(StrEnum):
    """The only supported SQL sort directions."""

    ASC = "asc"
    DESC = "desc"


@dataclass(frozen=True)
class SortSpec:
    """A public-name sort request interpreted only through a model allowlist."""

    key: str
    direction: SortDirection = SortDirection.DESC


def resolve_sort(
    sort: SortSpec | None,
    *,
    allowed: dict[str, ColumnElement[object]],
    default: SortSpec,
    tie_breaker: ColumnElement[object],
) -> tuple[ColumnElement[object], ColumnElement[object]]:
    """Build deterministic SQLAlchemy order expressions without raw SQL input."""

    selected = sort if sort is not None else default
    if not isinstance(selected.direction, SortDirection):
        raise InvalidQueryError("The requested sort direction is not supported.")
    column = allowed.get(selected.key)
    if column is None:
        raise InvalidQueryError("The requested sort key is not supported.")
    primary = column.asc() if selected.direction is SortDirection.ASC else column.desc()
    return primary, tie_breaker.asc()
