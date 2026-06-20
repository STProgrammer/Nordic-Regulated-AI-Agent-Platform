"""Application services for local authentication and administrator identity work."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import PasswordInputError, PasswordSecurity
from app.core.session_store import SessionStore
from app.db.models.identity import Role, User, UserRole
from app.services.audit.service import AuditEventCreate, AuditService, JSONValue
from app.services.auth.principal import Principal, RoleName, canonical_roles
from app.services.common.pagination import Page, Pagination
from app.services.common.querying import SortSpec
from app.services.errors import ConflictError, InvalidCommandError
from app.services.identity.service import IdentityService, UserCreate, UserUpdate


def normalize_email(email: str) -> str:
    """Apply the intentionally limited email lookup/write normalization policy."""

    return email.strip().casefold()


@dataclass(frozen=True)
class LoginCommand:
    """Credential input kept out of diagnostic representations."""

    email: str
    password: str = field(repr=False)


@dataclass(frozen=True)
class LoginSucceeded:
    """A successful login result; the opaque handle is never serialized directly."""

    principal: Principal
    session_id: str = field(repr=False)


@dataclass(frozen=True)
class LoginRejected:
    """A deliberately uninformative local-login failure."""


LoginResult = LoginSucceeded | LoginRejected


@dataclass(frozen=True)
class UserAdminCreateCommand:
    email: str
    display_name: str
    preferred_language: str
    password: str | None = field(default=None, repr=False)
    role_names: tuple[RoleName, ...] = ()


@dataclass(frozen=True)
class UserAdminUpdateCommand:
    display_name: str | None = None
    preferred_language: str | None = None
    is_active: bool | None = None
    password: str | None = field(default=None, repr=False)


class AuthenticationService:
    """Compose identity persistence, audit writes, passwords, and sessions."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        password_security: PasswordSecurity,
        session_store: SessionStore,
        session_ttl_seconds: int,
    ) -> None:
        self._session = session
        self._password_security = password_security
        self._session_store = session_store
        self._session_ttl_seconds = session_ttl_seconds
        self._identity = IdentityService(session)
        self._audit = AuditService(session)

    async def login(self, command: LoginCommand) -> LoginResult:
        """Authenticate without leaking account state to callers."""

        user = await self._identity.get_user_by_normalized_email(normalize_email(command.email))
        if user is None:
            self._password_security.verify_dummy(command.password)
            return LoginRejected()

        if not user.is_active or user.password_hash is None:
            self._password_security.verify_dummy(command.password)
            await self._record_login_failure(user)
            return LoginRejected()

        verification = self._password_security.verify(command.password, user.password_hash)
        if not verification.verified:
            await self._record_login_failure(user)
            return LoginRejected()

        if verification.needs_rehash:
            user.password_hash = self._password_security.hash(command.password)
        user.last_login_at = datetime.now(UTC)
        role_names = await self._identity.list_role_names_for_user(user.organization_id, user.id)
        principal = _principal_from_user(user, role_names)
        await self._audit.record_event(
            AuditEventCreate(
                organization_id=user.organization_id,
                actor_user_id=user.id,
                event_type="auth.login_succeeded",
                resource_type="user",
                resource_id=user.id,
            )
        )
        # Flush prior writes before issuing an external session. The request-owned
        # transaction still owns the final commit/rollback decision.
        await self._session.flush()
        session_id = await self._session_store.create(
            user.id,
            user.organization_id,
            ttl_seconds=self._session_ttl_seconds,
        )
        return LoginSucceeded(principal=principal, session_id=session_id)

    async def resolve_principal(self, session_id: str) -> Principal | None:
        """Resolve one opaque session against current persisted identity state."""

        record = await self._session_store.get(session_id)
        if record is None:
            return None
        user = await self._identity.get_user_required_or_none(
            record.organization_id, record.user_id
        )
        if user is None or not user.is_active:
            await self._session_store.delete_all_for_user(record.user_id)
            return None
        role_names = await self._identity.list_role_names_for_user(
            record.organization_id, record.user_id
        )
        return _principal_from_user(user, role_names)

    async def logout(self, principal: Principal, session_id: str) -> None:
        """Invalidate the presented opaque session and append a minimal audit event."""

        await self._session_store.delete(session_id)
        await self._audit.record_event(
            AuditEventCreate(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="auth.logout",
                resource_type="user",
                resource_id=principal.user_id,
            )
        )

    async def _record_login_failure(self, user: User) -> None:
        await self._audit.record_event(
            AuditEventCreate(
                organization_id=user.organization_id,
                actor_user_id=user.id,
                event_type="auth.login_failed",
                resource_type="user",
                resource_id=user.id,
            )
        )


class UserAdministrationService:
    """Admin-only application operations; the API dependency enforces Admin."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        password_security: PasswordSecurity,
        session_store: SessionStore,
    ) -> None:
        self._identity = IdentityService(session)
        self._audit = AuditService(session)
        self._password_security = password_security
        self._session_store = session_store

    async def list_users(
        self, principal: Principal, *, pagination: Pagination, sort: SortSpec | None
    ) -> Page[User]:
        return await self._identity.list_users(
            principal.organization_id, pagination=pagination, sort=sort
        )

    async def get_user(self, principal: Principal, user_id: UUID) -> User:
        return await self._identity.get_user_required(principal.organization_id, user_id)

    async def role_names_for_user(self, principal: Principal, user_id: UUID) -> tuple[str, ...]:
        return await self._identity.list_role_names_for_user(principal.organization_id, user_id)

    async def list_roles(self) -> tuple[Role, ...]:
        return await self._identity.list_roles()

    async def create_user(self, principal: Principal, command: UserAdminCreateCommand) -> User:
        password_hash = self._hash_optional_password(command.password)
        user = await self._identity.create_user(
            UserCreate(
                organization_id=principal.organization_id,
                email=normalize_email(command.email),
                display_name=command.display_name.strip(),
                preferred_language=command.preferred_language.strip(),
                password_hash=password_hash,
            )
        )
        await self._identity.replace_roles(
            principal.organization_id,
            user.id,
            tuple(role.value for role in command.role_names),
        )
        await self._audit.record_event(
            AuditEventCreate(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="identity.user_created",
                resource_type="user",
                resource_id=user.id,
            )
        )
        return user

    async def update_user(
        self, principal: Principal, user_id: UUID, command: UserAdminUpdateCommand
    ) -> User:
        target = await self._identity.get_user_required(principal.organization_id, user_id)
        target_roles = await self._identity.list_role_names_for_user(
            principal.organization_id, target.id
        )
        if command.is_active is False and target.is_active and RoleName.ADMIN.value in target_roles:
            await self._ensure_not_only_active_admin(principal.organization_id)

        password_hash = self._hash_optional_password(command.password)
        user = await self._identity.update_user(
            principal.organization_id,
            user_id,
            UserUpdate(
                display_name=command.display_name.strip()
                if command.display_name is not None
                else None,
                preferred_language=(
                    command.preferred_language.strip()
                    if command.preferred_language is not None
                    else None
                ),
                is_active=command.is_active,
                password_hash=password_hash,
            ),
        )
        if command.is_active is False or password_hash is not None:
            await self._session_store.delete_all_for_user(user.id)
        changed_fields = _changed_identity_fields(command)
        await self._audit.record_event(
            AuditEventCreate(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type=(
                    "identity.user_deactivated"
                    if command.is_active is False
                    else "identity.user_updated"
                ),
                resource_type="user",
                resource_id=user.id,
                event_data={"changed_fields": changed_fields},
            )
        )
        return user

    async def replace_roles(
        self, principal: Principal, user_id: UUID, role_names: tuple[RoleName, ...]
    ) -> tuple[UserRole, ...]:
        target = await self._identity.get_user_required(principal.organization_id, user_id)
        existing = await self._identity.list_role_names_for_user(principal.organization_id, user_id)
        requested_names = tuple(role.value for role in role_names)
        if (
            target.is_active
            and RoleName.ADMIN.value in existing
            and RoleName.ADMIN.value not in requested_names
        ):
            await self._ensure_not_only_active_admin(principal.organization_id)
        assignments = await self._identity.replace_roles(
            principal.organization_id, user_id, requested_names
        )
        await self._audit.record_event(
            AuditEventCreate(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="identity.roles_replaced",
                resource_type="user",
                resource_id=user_id,
            )
        )
        return assignments

    def _hash_optional_password(self, password: str | None) -> str | None:
        if password is None:
            return None
        try:
            return self._password_security.hash(password)
        except PasswordInputError as error:
            raise InvalidCommandError(
                "The supplied password does not meet the password policy."
            ) from error

    async def _ensure_not_only_active_admin(self, organization_id: UUID) -> None:
        if (
            await self._identity.count_active_users_with_role(organization_id, RoleName.ADMIN.value)
        ) <= 1:
            raise ConflictError("Administrator continuity")


def _principal_from_user(user: User, role_names: tuple[str, ...]) -> Principal:
    return Principal(
        user_id=user.id,
        organization_id=user.organization_id,
        display_name=user.display_name,
        preferred_language=user.preferred_language,
        roles=canonical_roles(role_names),
    )


def _changed_identity_fields(command: UserAdminUpdateCommand) -> list[JSONValue]:
    changed: list[JSONValue] = []
    if command.display_name is not None:
        changed.append("display_name")
    if command.preferred_language is not None:
        changed.append("preferred_language")
    if command.is_active is not None:
        changed.append("is_active")
    if command.password is not None:
        changed.append("credential_updated")
    return changed
