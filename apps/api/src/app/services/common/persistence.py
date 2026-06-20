"""Transaction helpers for expected, safely translated persistence conflicts."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.errors import ConflictError


async def stage_write[T](
    session: AsyncSession,
    write: Callable[[], Awaitable[T]],
    *,
    resource: str,
) -> T:
    """Flush a deliberate write in a savepoint and safely map expected conflicts.

    The callback must not stage rows before this helper starts its savepoint.  A
    failed constraint check then rolls back only the savepoint, leaving the
    caller-owned outer session usable for subsequent repository operations.
    """

    try:
        async with session.begin_nested():
            result = await write()
            await session.flush()
    except IntegrityError as error:
        raise ConflictError(resource) from error
    return result
