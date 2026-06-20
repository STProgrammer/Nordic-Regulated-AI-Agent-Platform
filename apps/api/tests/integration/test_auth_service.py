"""PostgreSQL integration coverage for authentication tenant and audit behavior."""

from __future__ import annotations

import asyncio
from uuid import UUID

from app.core.config import AppSettings
from app.core.security import PasswordSecurity
from app.core.session_store import InMemorySessionStore
from app.db.models import AuditEvent, Organization, Role, User, UserRole
from app.db.session import dispose_database_engines, get_sessionmaker
from app.services.auth.principal import RoleName
from app.services.auth.service import (
    AuthenticationService,
    LoginCommand,
    LoginRejected,
    LoginSucceeded,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def test_authentication_uses_persisted_tenant_and_retains_known_failure_audit(
    database_settings: AppSettings,
) -> None:
    asyncio.run(_run_authentication(database_settings))


async def _run_authentication(settings: AppSettings) -> None:
    try:
        await _exercise_authentication(settings)
    finally:
        await dispose_database_engines()


async def _exercise_authentication(settings: AppSettings) -> None:
    security = PasswordSecurity(minimum_length=12, maximum_length=128)
    session_store = InMemorySessionStore()
    sessionmaker = get_sessionmaker(settings)
    organization_id, user_id = await _seed_authentication_records(sessionmaker, security)

    async with sessionmaker() as session, session.begin():
        service = AuthenticationService(
            session,
            password_security=security,
            session_store=session_store,
            session_ttl_seconds=600,
        )
        success = await service.login(
            LoginCommand(email="ADMIN.USER@demo.invalid", password="Synthetic test password 42")
        )
        assert isinstance(success, LoginSucceeded)
        assert success.principal.organization_id == organization_id
        assert success.principal.roles == frozenset({RoleName.ADMIN})
        assert await session_store.get(success.session_id) is not None

    async with sessionmaker() as session, session.begin():
        service = AuthenticationService(
            session,
            password_security=security,
            session_store=session_store,
            session_ttl_seconds=600,
        )
        known_failure = await service.login(
            LoginCommand(email="admin.user@demo.invalid", password="wrong password")
        )
        unknown_failure = await service.login(
            LoginCommand(email="unknown@demo.invalid", password="wrong password")
        )
        inactive_failure = await service.login(
            LoginCommand(email="inactive.user@demo.invalid", password="wrong password")
        )
        passwordless_failure = await service.login(
            LoginCommand(email="passwordless.user@demo.invalid", password="wrong password")
        )
        assert isinstance(known_failure, LoginRejected)
        assert isinstance(unknown_failure, LoginRejected)
        assert isinstance(inactive_failure, LoginRejected)
        assert isinstance(passwordless_failure, LoginRejected)

    async with sessionmaker() as session:
        authenticated_user = await session.scalar(select(User).where(User.id == user_id))
        assert authenticated_user is not None
        assert authenticated_user.last_login_at is not None
        events = tuple(
            (
                await session.scalars(
                    select(AuditEvent)
                    .where(AuditEvent.organization_id == organization_id)
                    .order_by(AuditEvent.event_type.asc())
                )
            ).all()
        )
        assert [event.event_type for event in events] == [
            "auth.login_failed",
            "auth.login_failed",
            "auth.login_failed",
            "auth.login_succeeded",
        ]
        assert all(event.event_data == {} for event in events)
        assert all("password" not in str(event.event_data) for event in events)


async def _seed_authentication_records(
    sessionmaker: async_sessionmaker[AsyncSession], security: PasswordSecurity
) -> tuple[UUID, UUID]:
    async with sessionmaker() as session, session.begin():
        organization = Organization(
            name="Authentication synthetic organization",
            slug="authentication-synthetic",
            default_language="nb",
            retention_policy={},
            settings={},
        )
        isolated_organization = Organization(
            name="Authentication isolated organization",
            slug="authentication-isolated",
            default_language="nb",
            retention_policy={},
            settings={},
        )
        admin_role = Role(name=RoleName.ADMIN.value, description="Synthetic administrator role")
        session.add_all([organization, isolated_organization, admin_role])
        await session.flush()
        authenticated_user = User(
            organization_id=organization.id,
            email="admin.user@demo.invalid",
            display_name="Authentication Admin",
            preferred_language="nb",
            password_hash=security.hash("Synthetic test password 42"),
            is_active=True,
        )
        inactive_user = User(
            organization_id=organization.id,
            email="inactive.user@demo.invalid",
            display_name="Inactive User",
            preferred_language="nb",
            password_hash=security.hash("Synthetic inactive password 42"),
            is_active=False,
        )
        passwordless_user = User(
            organization_id=organization.id,
            email="passwordless.user@demo.invalid",
            display_name="Passwordless User",
            preferred_language="nb",
            password_hash=None,
            is_active=True,
        )
        session.add_all([authenticated_user, inactive_user, passwordless_user])
        await session.flush()
        session.add(
            UserRole(
                organization_id=organization.id,
                user_id=authenticated_user.id,
                role_id=admin_role.id,
            )
        )
        return organization.id, authenticated_user.id
