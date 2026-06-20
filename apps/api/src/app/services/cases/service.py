"""Internal case persistence service, deliberately without case workflow policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.case import Case
from app.db.repositories.case import CaseRepository, CaseUpdateValues
from app.db.repositories.identity import UserRepository
from app.services.common.pagination import Page, Pagination
from app.services.common.persistence import stage_write
from app.services.common.querying import SortSpec
from app.services.errors import NotFoundError


@dataclass(frozen=True)
class CaseCreate:
    """Storage input for a future case command; no ID, timestamps, or policy logic."""

    organization_id: UUID
    case_number: str
    title: str
    description: str
    language: str
    domain: str
    priority: str
    status: str
    submitted_by_user_id: UUID
    case_type: str | None = None
    risk_level: str | None = None
    assigned_user_id: UUID | None = None
    due_date: date | None = None
    external_reference: str | None = None


class CaseService:
    """Persistence composition for cases; status/assignment policy is a later phase."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = CaseRepository(session)
        self.users = UserRepository(session)

    async def create(self, command: CaseCreate) -> Case:
        await self._require_user(command.organization_id, command.submitted_by_user_id)
        if command.assigned_user_id is not None:
            await self._require_user(command.organization_id, command.assigned_user_id)
        case = Case(
            organization_id=command.organization_id,
            case_number=command.case_number,
            title=command.title,
            description=command.description,
            language=command.language,
            domain=command.domain,
            priority=command.priority,
            status=command.status,
            submitted_by_user_id=command.submitted_by_user_id,
            case_type=command.case_type,
            risk_level=command.risk_level,
            assigned_user_id=command.assigned_user_id,
            due_date=command.due_date,
            external_reference=command.external_reference,
        )
        return await stage_write(
            self.session, lambda: self.repository.create(case), resource="Case"
        )

    async def get_required(
        self, organization_id: UUID, case_id: UUID, *, include_archived: bool = False
    ) -> Case:
        case = await self.repository.get(
            organization_id, case_id, include_archived=include_archived
        )
        if case is None:
            raise NotFoundError("Case")
        return case

    async def list(
        self,
        organization_id: UUID,
        *,
        pagination: Pagination,
        sort: SortSpec | None = None,
        include_archived: bool = False,
    ) -> Page[Case]:
        return await self.repository.list(
            organization_id,
            pagination=pagination,
            sort=sort,
            include_archived=include_archived,
        )

    async def update(self, organization_id: UUID, case_id: UUID, values: CaseUpdateValues) -> Case:
        case = await self.get_required(organization_id, case_id)
        if values.assigned_user_id is not None:
            await self._require_user(organization_id, values.assigned_user_id)
        return await stage_write(
            self.session,
            lambda: self.repository.update(case, values),
            resource="Case",
        )

    async def archive(self, organization_id: UUID, case_id: UUID) -> Case:
        archived = await self.repository.archive(organization_id, case_id)
        if archived is None:
            raise NotFoundError("Case")
        await self.session.flush()
        return archived

    async def _require_user(self, organization_id: UUID, user_id: UUID) -> None:
        if await self.users.get(organization_id, user_id) is None:
            raise NotFoundError("User")
