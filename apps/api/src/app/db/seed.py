"""Idempotent, deliberately synthetic fixtures for the explicit local seed command."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, text

from app.core.config import AppSettings, get_settings
from app.core.security import PasswordSecurity
from app.db.models.identity import Role, User, UserRole
from app.db.models.organization import Organization
from app.db.models.prompt import PromptVersion
from app.db.session import get_sessionmaker


@dataclass(frozen=True)
class SeedUser:
    """A clearly synthetic identity and its one required global role."""

    email: str
    display_name: str
    role_name: str


ROLE_DESCRIPTIONS: dict[str, str] = {
    "Admin": "Synthetic fixture role for local administration.",
    "Compliance Reviewer": "Synthetic fixture role for compliance review.",
    "Case Worker": "Synthetic fixture role for case work.",
    "Manager": "Synthetic fixture role for management.",
    "Read-only Auditor": "Synthetic fixture role for read-only audit inspection.",
}
SEED_USERS = (
    SeedUser("kari.eksempel+caseworker@demo.invalid", "Kari Eksempel", "Case Worker"),
    SeedUser("ole.eksempel+reviewer@demo.invalid", "Ole Eksempel", "Compliance Reviewer"),
    SeedUser("elin.eksempel+manager@demo.invalid", "Elin Eksempel", "Manager"),
    SeedUser("per.eksempel+admin@demo.invalid", "Per Eksempel", "Admin"),
    SeedUser("ida.eksempel+auditor@demo.invalid", "Ida Eksempel", "Read-only Auditor"),
)
DEMO_ORGANIZATION_SLUG = "synthetic-nordlys-demo"
LOCAL_SEED_ADVISORY_LOCK_KEY = 763_983_741


async def seed_local(
    settings: AppSettings | None = None, *, local_password: str | None = None
) -> tuple[int, int, int]:
    """Insert safe fixtures, optionally enabling local-only password login.

    Password-free fixture identities remain the default. A caller must pass an
    explicit password value sourced outside committed configuration to provision
    local credentials, and production/staging invocations are refused.
    """

    resolved_settings = settings if settings is not None else get_settings()
    if local_password is not None and resolved_settings.environment not in {"local", "test"}:
        raise ValueError("Local password seeding is not allowed in this environment.")
    password_security = PasswordSecurity(
        minimum_length=resolved_settings.password_min_length,
        maximum_length=resolved_settings.password_max_length,
    )
    sessionmaker = get_sessionmaker(resolved_settings)
    async with sessionmaker() as session, session.begin():
        # Browser workers can bootstrap their independent fixtures at the same
        # time. Serialize the shared organization/role/user seed transaction
        # so concurrent read-then-insert checks remain idempotent.
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": LOCAL_SEED_ADVISORY_LOCK_KEY},
        )
        organization = await session.scalar(
            select(Organization).where(Organization.slug == DEMO_ORGANIZATION_SLUG)
        )
        if organization is None:
            organization = Organization(
                name="Syntetisk Nordlys Eksempelkommune",
                slug=DEMO_ORGANIZATION_SLUG,
                default_language="nb",
                retention_policy={"classification": "synthetic", "retention_days": 30},
                settings={"seed_fixture": True, "login_enabled": False},
            )
            session.add(organization)
            await session.flush()

        roles: dict[str, Role] = {}
        for name, description in ROLE_DESCRIPTIONS.items():
            role = await session.scalar(select(Role).where(Role.name == name))
            if role is None:
                role = Role(name=name, description=description)
                session.add(role)
                await session.flush()
            roles[name] = role

        for seed_user in SEED_USERS:
            user = await session.scalar(select(User).where(User.email == seed_user.email))
            if user is None:
                user = User(
                    organization_id=organization.id,
                    email=seed_user.email,
                    display_name=seed_user.display_name,
                    password_hash=None,
                    identity_provider="seed-fixture",
                    identity_subject=f"synthetic:{seed_user.role_name.lower().replace(' ', '-')}",
                    preferred_language="nb",
                    is_active=True,
                )
                session.add(user)
                await session.flush()

            if local_password is not None:
                existing_hash = user.password_hash
                verification = (
                    password_security.verify(local_password, existing_hash)
                    if existing_hash is not None
                    else None
                )
                if verification is None or not verification.verified or verification.needs_rehash:
                    user.password_hash = password_security.hash(local_password)

            membership = await session.scalar(
                select(UserRole).where(
                    UserRole.user_id == user.id,
                    UserRole.role_id == roles[seed_user.role_name].id,
                    UserRole.organization_id == organization.id,
                )
            )
            if membership is None:
                session.add(
                    UserRole(
                        user_id=user.id,
                        role_id=roles[seed_user.role_name].id,
                        organization_id=organization.id,
                    )
                )

        # A synthetic local-only prompt lets the deterministic Intake plumbing be
        # exercised after an explicit seed. Production prompt provisioning is not
        # performed by this helper and remains an operational responsibility.
        if resolved_settings.environment in {"local", "test"}:
            intake_prompt = await session.scalar(
                select(PromptVersion).where(
                    PromptVersion.organization_id == organization.id,
                    PromptVersion.name == "intake_classification",
                    PromptVersion.version == "local-v1",
                )
            )
            if intake_prompt is None:
                session.add(
                    PromptVersion(
                        organization_id=organization.id,
                        name="intake_classification",
                        version="local-v1",
                        content=(
                            "Return only the server-declared structured Intake "
                            "classification JSON. "
                            "This synthetic local prompt is not production policy."
                        ),
                        description="Synthetic local Intake fixture prompt.",
                        is_active=True,
                    )
                )
            extraction_prompt = await session.scalar(
                select(PromptVersion).where(
                    PromptVersion.organization_id == organization.id,
                    PromptVersion.name == "extraction_fields",
                    PromptVersion.version == "local-v1",
                )
            )
            if extraction_prompt is None:
                session.add(
                    PromptVersion(
                        organization_id=organization.id,
                        name="extraction_fields",
                        version="local-v1",
                        content=(
                            "Return only the server-declared structured source-linked "
                            "Extraction JSON. This synthetic local prompt is not production policy."
                        ),
                        description="Synthetic local Extraction fixture prompt.",
                        is_active=True,
                    )
                )
            drafting_prompt = await session.scalar(
                select(PromptVersion).where(
                    PromptVersion.organization_id == organization.id,
                    PromptVersion.name == "drafting_response",
                    PromptVersion.version == "local-v1",
                )
            )
            if drafting_prompt is None:
                session.add(
                    PromptVersion(
                        organization_id=organization.id,
                        name="drafting_response",
                        version="local-v1",
                        content=(
                            "Return only the server-declared structured cited Drafting JSON. "
                            "This synthetic local prompt is not production policy."
                        ),
                        description="Synthetic local Drafting fixture prompt.",
                        is_active=True,
                    )
                )

    return 1, len(ROLE_DESCRIPTIONS), len(SEED_USERS)
