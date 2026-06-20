"""Tenant-scoped identity persistence and global role access."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.db.models.identity import Role, User, UserRole
from app.db.repositories.base import TenantScopedRepository
from app.services.common.pagination import Page, Pagination
from app.services.common.querying import SortSpec, resolve_sort


class UserRepository(TenantScopedRepository[User]):
    """Database access for users, always constrained by organization id."""

    _sort_columns = {
        "inserted_at": cast(ColumnElement[object], User.inserted_at),
        "email": cast(ColumnElement[object], User.email),
        "display_name": cast(ColumnElement[object], User.display_name),
    }

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(
            session,
            User,
            id_column=cast(ColumnElement[UUID], User.id),
            organization_column=cast(ColumnElement[UUID], User.organization_id),
            archived_at_column=None,
        )

    async def create(self, user: User) -> User:
        """Stage a user in the caller-owned transaction."""

        self.session.add(user)
        return user

    async def get_by_normalized_email(self, normalized_email: str) -> User | None:
        """Find an account for authentication without accepting a tenant claim.

        Email is globally unique in the Phase 4 schema. The resulting tenant is
        always taken from this persisted row, never from a request value.
        """

        statement = select(User).where(func.lower(User.email) == normalized_email)
        return cast(User | None, await self.session.scalar(statement))

    async def list(
        self,
        organization_id: UUID,
        *,
        pagination: Pagination,
        sort: SortSpec | None = None,
    ) -> Page[User]:
        """List users with an allowlisted, stable sort."""

        order = resolve_sort(
            sort,
            allowed=self._sort_columns,
            default=SortSpec("inserted_at"),
            tie_breaker=cast(ColumnElement[object], User.id),
        )
        return await self.list_page(organization_id, pagination=pagination, order_by=order)

    async def update(
        self,
        user: User,
        *,
        display_name: str | None = None,
        preferred_language: str | None = None,
        is_active: bool | None = None,
        password_hash: str | None = None,
    ) -> User:
        """Update explicit identity persistence attributes only."""

        if display_name is not None:
            user.display_name = display_name
        if preferred_language is not None:
            user.preferred_language = preferred_language
        if is_active is not None:
            user.is_active = is_active
        if password_hash is not None:
            user.password_hash = password_hash
        return user


class RoleRepository:
    """Global role definitions; this repository does not make RBAC decisions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, role_id: UUID) -> Role | None:
        return cast(Role | None, await self.session.scalar(select(Role).where(Role.id == role_id)))

    async def get_by_name(self, name: str) -> Role | None:
        return cast(Role | None, await self.session.scalar(select(Role).where(Role.name == name)))

    async def list(self) -> tuple[Role, ...]:
        statement = select(Role).order_by(Role.name.asc(), Role.id.asc())
        return tuple((await self.session.scalars(statement)).all())


class UserRoleRepository:
    """Organization-bound assignment access for global roles."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, organization_id: UUID, user_id: UUID, role_id: UUID) -> UserRole | None:
        statement = select(UserRole).where(
            UserRole.organization_id == organization_id,
            UserRole.user_id == user_id,
            UserRole.role_id == role_id,
        )
        return cast(UserRole | None, await self.session.scalar(statement))

    async def list_for_user(self, organization_id: UUID, user_id: UUID) -> tuple[UserRole, ...]:
        statement = (
            select(UserRole)
            .where(
                UserRole.organization_id == organization_id,
                UserRole.user_id == user_id,
            )
            .order_by(UserRole.inserted_at.asc(), UserRole.role_id.asc())
        )
        return tuple((await self.session.scalars(statement)).all())

    async def list_role_names_for_user(
        self, organization_id: UUID, user_id: UUID
    ) -> tuple[str, ...]:
        """Load current global role names through the tenant membership table."""

        statement = (
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.organization_id == organization_id,
                UserRole.user_id == user_id,
            )
            .order_by(Role.name.asc(), Role.id.asc())
        )
        return tuple((await self.session.scalars(statement)).all())

    async def assign(self, assignment: UserRole) -> UserRole:
        """Stage a tenant-bound user-role membership."""

        self.session.add(assignment)
        return assignment

    async def count_active_users_with_role(self, organization_id: UUID, role_name: str) -> int:
        """Count active tenant users assigned one exact global role."""

        statement = (
            select(func.count(User.id))
            .select_from(User)
            .join(
                UserRole,
                (UserRole.user_id == User.id) & (UserRole.organization_id == User.organization_id),
            )
            .join(Role, Role.id == UserRole.role_id)
            .where(
                User.organization_id == organization_id,
                User.is_active.is_(True),
                Role.name == role_name,
            )
        )
        result = await self.session.scalar(statement)
        return result if result is not None else 0
