"""Unit coverage for bounded internal pagination primitives."""

import pytest
from app.services.common.pagination import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT, Page, Pagination
from app.services.errors import InvalidQueryError


def test_pagination_uses_conservative_defaults() -> None:
    pagination = Pagination()

    assert pagination.limit == DEFAULT_PAGE_LIMIT
    assert pagination.offset == 0


@pytest.mark.parametrize(
    ("limit", "offset"),
    [
        (0, 0),
        (MAX_PAGE_LIMIT + 1, 0),
        (1, -1),
    ],
)
def test_pagination_rejects_invalid_bounds(limit: int, offset: int) -> None:
    with pytest.raises(InvalidQueryError) as error:
        Pagination(limit=limit, offset=offset)

    assert error.value.code == "invalid_query"
    assert "postgres" not in error.value.message.casefold()


def test_page_metadata_is_stable() -> None:
    page = Page(items=("one", "two"), limit=2, offset=2, total=5)

    assert page.has_more is True
    assert Page(items=("one",), limit=2, offset=4, total=5).has_more is False
