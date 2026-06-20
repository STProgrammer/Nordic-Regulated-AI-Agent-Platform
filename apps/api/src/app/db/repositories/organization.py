"""Persistence queries for the organization tenant root."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.organization import Organization


class OrganizationRepository:
    """Narrow organization-root persistence operations, without tenant child scope."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, organization: Organization) -> Organization:
        """Stage an organization in the caller-owned transaction."""

        self.session.add(organization)
        return organization

    async def get(
        self, organization_id: UUID, *, include_archived: bool = False
    ) -> Organization | None:
        """Look up an organization root by id."""

        statement = select(Organization).where(Organization.id == organization_id)
        if not include_archived:
            statement = statement.where(Organization.archived_at.is_(None))
        return cast(Organization | None, await self.session.scalar(statement))

    async def get_by_slug(
        self, slug: str, *, include_archived: bool = False
    ) -> Organization | None:
        """Look up an organization root by its unique slug."""

        statement = select(Organization).where(Organization.slug == slug)
        if not include_archived:
            statement = statement.where(Organization.archived_at.is_(None))
        return cast(Organization | None, await self.session.scalar(statement))

    async def update(
        self,
        organization: Organization,
        *,
        name: str | None = None,
        default_language: str | None = None,
        retention_policy: dict[str, object] | None = None,
        settings: dict[str, object] | None = None,
    ) -> Organization:
        """Apply explicit persistence fields without defining organization policy."""

        if name is not None:
            organization.name = name
        if default_language is not None:
            organization.default_language = default_language
        if retention_policy is not None:
            organization.retention_policy = retention_policy
        if settings is not None:
            organization.settings = settings
        return organization
