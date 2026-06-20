"""Internal identity persistence service; authorization policy is intentionally absent."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.identity import Role, User, UserRole
from app.db.repositories.identity import RoleRepository, UserRepository, UserRoleRepository
from app.services.common.pagination import Page, Pagination
from app.services.common.persistence import stage_write
from app.services.common.querying import SortSpec
from app.services.errors import ConflictError, InvalidCommandError, NotFoundError


@dataclass(frozen=True)
class UserCreate:
    """Typed user persistence input without identifiers, timestamps, or credentials."""

    organization_id: UUID
    email: str
    display_name: str
    preferred_language: str
    identity_provider: str | None = None
    identity_subject: str | None = None
    is_active: bool = True
    password_hash: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class UserUpdate:
    """Explicit mutable user fields; password hashes never appear in repr output."""

    display_name: str | None = None
    preferred_language: str | None = None
    is_active: bool | None = None
    password_hash: str | None = field(default=None, repr=False)


class IdentityService:
    """Compose tenant user and global-role persistence calls with safe failures."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.roles = RoleRepository(session)
        self.assignments = UserRoleRepository(session)

    async def create_user(self, command: UserCreate) -> User:
        user = User(
            organization_id=command.organization_id,
            email=command.email,
            display_name=command.display_name,
            preferred_language=command.preferred_language,
            identity_provider=command.identity_provider,
            identity_subject=command.identity_subject,
            is_active=command.is_active,
            password_hash=command.password_hash,
        )
        return await stage_write(self.session, lambda: self.users.create(user), resource="User")

    async def get_user_required(self, organization_id: UUID, user_id: UUID) -> User:
        user = await self.users.get(organization_id, user_id)
        if user is None:
            raise NotFoundError("User")
        return user

    async def get_user_required_or_none(self, organization_id: UUID, user_id: UUID) -> User | None:
        """Return a scoped user for session validation without raising on stale state."""

        return await self.users.get(organization_id, user_id)

    async def get_user_by_normalized_email(self, normalized_email: str) -> User | None:
        """Locate a user for login; its persisted organization remains authoritative."""

        return await self.users.get_by_normalized_email(normalized_email)

    async def list_users(
        self,
        organization_id: UUID,
        *,
        pagination: Pagination,
        sort: SortSpec | None = None,
    ) -> Page[User]:
        return await self.users.list(organization_id, pagination=pagination, sort=sort)

    async def get_role_required(self, role_id: UUID) -> Role:
        role = await self.roles.get(role_id)
        if role is None:
            raise NotFoundError("Role")
        return role

    async def list_roles(self) -> tuple[Role, ...]:
        """List the global role catalogue in deterministic order."""

        return await self.roles.list()

    async def list_role_names_for_user(
        self, organization_id: UUID, user_id: UUID
    ) -> tuple[str, ...]:
        """Return current organization-bound role names for a visible user."""

        await self.get_user_required(organization_id, user_id)
        return await self.assignments.list_role_names_for_user(organization_id, user_id)

    async def update_user(self, organization_id: UUID, user_id: UUID, command: UserUpdate) -> User:
        """Apply a deliberate set of mutable identity fields in tenant scope."""

        user = await self.get_user_required(organization_id, user_id)
        return await self.users.update(
            user,
            display_name=command.display_name,
            preferred_language=command.preferred_language,
            is_active=command.is_active,
            password_hash=command.password_hash,
        )

    async def assign_role(self, organization_id: UUID, user_id: UUID, role_id: UUID) -> UserRole:
        await self.get_user_required(organization_id, user_id)
        await self.get_role_required(role_id)
        if await self.assignments.get(organization_id, user_id, role_id) is not None:
            raise ConflictError("User role assignment")
        assignment = UserRole(
            organization_id=organization_id,
            user_id=user_id,
            role_id=role_id,
        )
        return await stage_write(
            self.session,
            lambda: self.assignments.assign(assignment),
            resource="User role assignment",
        )

    async def replace_roles(
        self,
        organization_id: UUID,
        user_id: UUID,
        role_names: tuple[str, ...],
    ) -> tuple[UserRole, ...]:
        """Replace a user's tenant role set using only known global role names."""

        await self.get_user_required(organization_id, user_id)
        if len(set(role_names)) != len(role_names):
            raise InvalidCommandError("Role assignments must not contain duplicates.")

        selected_roles: list[Role] = []
        for role_name in role_names:
            role = await self.roles.get_by_name(role_name)
            if role is None:
                raise InvalidCommandError("The requested role is not supported.")
            selected_roles.append(role)
        selected_role_ids = {role.id for role in selected_roles}
        existing = await self.assignments.list_for_user(organization_id, user_id)
        existing_role_ids = {assignment.role_id for assignment in existing}

        async def _replace() -> tuple[UserRole, ...]:
            for assignment in existing:
                if assignment.role_id not in selected_role_ids:
                    await self.session.delete(assignment)
            created: list[UserRole] = []
            for role in selected_roles:
                if role.id not in existing_role_ids:
                    assignment = UserRole(
                        organization_id=organization_id,
                        user_id=user_id,
                        role_id=role.id,
                    )
                    self.session.add(assignment)
                    created.append(assignment)
            return tuple(created)

        await stage_write(self.session, _replace, resource="User role assignment")
        return await self.assignments.list_for_user(organization_id, user_id)

    async def count_active_users_with_role(self, organization_id: UUID, role_name: str) -> int:
        """Support the administrator-continuity policy without unscoped access."""

        return await self.assignments.count_active_users_with_role(organization_id, role_name)
