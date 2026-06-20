"""Bounded, immutable pagination types for internal repository list operations."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.errors import InvalidQueryError

DEFAULT_PAGE_LIMIT = 25
MAX_PAGE_LIMIT = 100


@dataclass(frozen=True)
class Pagination:
    """Offset pagination with conservative defaults and an intentional maximum."""

    limit: int = DEFAULT_PAGE_LIMIT
    offset: int = 0

    def __post_init__(self) -> None:
        if self.limit < 1 or self.limit > MAX_PAGE_LIMIT:
            raise InvalidQueryError(f"The page limit must be between 1 and {MAX_PAGE_LIMIT}.")
        if self.offset < 0:
            raise InvalidQueryError("The page offset must not be negative.")


@dataclass(frozen=True)
class Page[T]:
    """A stable page including the total for the same scoped filter set."""

    items: tuple[T, ...]
    limit: int
    offset: int
    total: int

    @property
    def has_more(self) -> bool:
        """Whether another result exists after this page."""

        return self.offset + len(self.items) < self.total
