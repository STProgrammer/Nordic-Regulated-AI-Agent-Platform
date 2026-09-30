"""Internal organization-root persistence service."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.organization import Organization
from app.db.repositories.organization import OrganizationRepository
from app.services.common.persistence import stage_write
from app.services.errors import NotFoundError


@dataclass(frozen=True)
class OrganizationRegistration:
    """Server-owned organization fields are intentionally absent from this command."""

    name: str
    slug: str
    default_language: str
    retention_policy: dict[str, object] = field(default_factory=dict)
    settings: dict[str, object] = field(default_factory=dict)


class OrganizationService:
    """Small application operations for organization root persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = OrganizationRepository(session)

    async def add(self, command: OrganizationRegistration) -> Organization:
        organization = Organization(
            name=command.name,
            slug=command.slug,
            default_language=command.default_language,
            retention_policy=command.retention_policy,
            settings=command.settings,
        )
        return await stage_write(
            self.session,
            lambda: self.repository.add(organization),
            resource="Organization",
        )

    async def get_required(self, organization_id: UUID) -> Organization:
        organization = await self.repository.get(organization_id)
        if organization is None:
            raise NotFoundError("Organization")
        return organization
