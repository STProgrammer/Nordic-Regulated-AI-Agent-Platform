"""Unit coverage for safe sorting without raw SQL fragments."""

from typing import cast

import pytest
from app.services.common.querying import SortDirection, SortSpec, resolve_sort
from app.services.errors import InvalidQueryError
from sqlalchemy import column


def test_resolve_sort_uses_allowlisted_column_and_uuid_tie_breaker() -> None:
    orders = resolve_sort(
        SortSpec("name", SortDirection.ASC),
        allowed={"name": column("name")},
        default=SortSpec("name"),
        tie_breaker=column("id"),
    )

    assert len(orders) == 2
    assert "name ASC" in str(orders[0])
    assert "id ASC" in str(orders[1])


def test_resolve_sort_rejects_unknown_sort_key() -> None:
    with pytest.raises(InvalidQueryError) as error:
        resolve_sort(
            SortSpec("name; DROP TABLE cases"),
            allowed={"name": column("name")},
            default=SortSpec("name"),
            tie_breaker=column("id"),
        )

    assert error.value.message == "The requested sort key is not supported."


def test_resolve_sort_rejects_non_enum_direction() -> None:
    with pytest.raises(InvalidQueryError):
        resolve_sort(
            SortSpec("name", cast(SortDirection, "descending")),
            allowed={"name": column("name")},
            default=SortSpec("name"),
            tie_breaker=column("id"),
        )
