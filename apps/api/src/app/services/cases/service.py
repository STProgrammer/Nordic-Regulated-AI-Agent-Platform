"""Tenant-safe Case Management commands, queries, lifecycle checks, and audit writes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.case import Case
from app.db.repositories.case import CaseFilters, CaseRepository, CaseUpdateValues, Unset
from app.db.repositories.identity import UserRepository
from app.services.audit.service import AuditEventCreate, AuditService, JSONValue
from app.services.auth.policy import CaseAction, authorize_case_action
from app.services.auth.principal import Principal
from app.services.cases.policy import is_approval_status, validate_case_transition
from app.services.common.pagination import Page, Pagination
from app.services.common.persistence import stage_write
from app.services.common.querying import SortSpec
from app.services.errors import InvalidCommandError, InvalidQueryError, NotFoundError


@dataclass(frozen=True)
class CaseCreate:
    """Trusted submission values; tenant, submitter, number, and status are server-owned."""

    title: str
    description: str
    language: str
    domain: str
    priority: str
    due_date: date | None = None
    external_reference: str | None = None


@dataclass(frozen=True)
class CasePatch:
    """Service command preserving whether each mutable field was omitted or set to null."""

    title: str | Unset = Unset.VALUE
    description: str | Unset = Unset.VALUE
    language: str | Unset = Unset.VALUE
    domain: str | Unset = Unset.VALUE
    priority: str | Unset = Unset.VALUE
    status: str | Unset = Unset.VALUE
    assigned_user_id: UUID | None | Unset = Unset.VALUE
    due_date: date | None | Unset = Unset.VALUE
    external_reference: str | None | Unset = Unset.VALUE

    def changed_fields(self) -> tuple[str, ...]:
        """Return stable storage-field names without exposing business content."""

        values = (
            ("title", self.title),
            ("description", self.description),
            ("language", self.language),
            ("domain", self.domain),
            ("priority", self.priority),
            ("status", self.status),
            ("assigned_user_id", self.assigned_user_id),
            ("due_date", self.due_date),
            ("external_reference", self.external_reference),
        )
        return tuple(name for name, value in values if not isinstance(value, Unset))

    def has_non_status_change(self) -> bool:
        """Whether a patch needs normal metadata/assignment edit permission."""

        return any(field != "status" for field in self.changed_fields())


class CaseService:
    """The sole Case API domain owner; routes do not make lifecycle or audit decisions."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        case_number_factory: Callable[[], str] | None = None,
        today_provider: Callable[[], date] | None = None,
    ) -> None:
        self.session = session
        self.repository = CaseRepository(session)
        self.users = UserRepository(session)
        self.audit = AuditService(session)
        self._case_number_factory = case_number_factory or _new_case_number
        self._today_provider = today_provider or date.today

    async def submit(self, principal: Principal, command: CaseCreate) -> Case:
        """Create one new case with trusted tenant ownership and a minimal audit row."""

        authorize_case_action(principal, CaseAction.SUBMIT)
        self._validate_due_date(command.due_date)
        case = Case(
            organization_id=principal.organization_id,
            case_number=self._case_number_factory(),
            title=command.title,
            description=command.description,
            language=command.language,
            domain=command.domain,
            priority=command.priority,
            status="new",
            submitted_by_user_id=principal.user_id,
            due_date=command.due_date,
            external_reference=command.external_reference,
        )
        created = await stage_write(
            self.session, lambda: self.repository.create(case), resource="Case"
        )
        await self._record_case_event(
            created,
            principal,
            event_type="case.created",
            event_data={"case_number": created.case_number},
        )
        return created

    async def get_required(self, principal: Principal, case_id: UUID) -> Case:
        """Load a current-tenant, active case only for a role that may read it."""

        authorize_case_action(principal, CaseAction.READ)
        case = await self.repository.get(principal.organization_id, case_id)
        if case is None:
            raise NotFoundError("Case")
        return case

    async def list(
        self,
        principal: Principal,
        *,
        pagination: Pagination,
        filters: CaseFilters | None = None,
        sort: SortSpec | None = None,
    ) -> Page[Case]:
        """List visible cases after read authorization and safe query normalization."""

        authorize_case_action(principal, CaseAction.READ)
        selected_filters = filters if filters is not None else CaseFilters()
        normalized_search = self._normalized_search(selected_filters.search_text)
        return await self.repository.list(
            principal.organization_id,
            pagination=pagination,
            filters=CaseFilters(
                status=selected_filters.status,
                risk_level=selected_filters.risk_level,
                assigned_user_id=selected_filters.assigned_user_id,
                domain=selected_filters.domain,
                priority=selected_filters.priority,
                search_text=normalized_search,
            ),
            sort=sort,
        )

    async def list_assignee_options(self, principal: Principal) -> tuple[tuple[UUID, str], ...]:
        """Expose the minimal Case-owned assignee view for authorized readers."""

        authorize_case_action(principal, CaseAction.READ)
        return await self.repository.list_assignee_options(principal.organization_id)

    async def patch(self, principal: Principal, case_id: UUID, command: CasePatch) -> Case:
        """Apply one allowed case mutation and write exactly one matching audit event."""

        if not command.changed_fields():
            raise InvalidCommandError("At least one mutable case field is required.")
        case = await self._get_active_case(principal.organization_id, case_id)
        if command.has_non_status_change():
            authorize_case_action(principal, CaseAction.EDIT)

        old_status = case.status
        old_assignee = case.assigned_user_id
        if not isinstance(command.status, Unset):
            validate_case_transition(case.status, command.status)
            authorize_case_action(
                principal,
                CaseAction.APPROVE_OR_REJECT
                if is_approval_status(command.status)
                else CaseAction.EDIT,
            )
        if not isinstance(command.assigned_user_id, Unset) and command.assigned_user_id is not None:
            await self._require_active_user(principal.organization_id, command.assigned_user_id)
        if not isinstance(command.due_date, Unset):
            self._validate_due_date(command.due_date)

        updated = await stage_write(
            self.session,
            lambda: self.repository.update(
                case,
                CaseUpdateValues(
                    title=command.title,
                    description=command.description,
                    language=command.language,
                    domain=command.domain,
                    priority=command.priority,
                    status=command.status,
                    assigned_user_id=command.assigned_user_id,
                    due_date=command.due_date,
                    external_reference=command.external_reference,
                ),
            ),
            resource="Case",
        )
        await self._record_case_event(
            updated,
            principal,
            event_type=_patch_event_type(command),
            event_data=_patch_event_data(command, updated.case_number, old_status, old_assignee),
        )
        return updated

    async def archive(self, principal: Principal, case_id: UUID) -> Case:
        """Atomically archive one active case and append a same-transaction audit event."""

        authorize_case_action(principal, CaseAction.ARCHIVE)
        archived = await self.repository.archive(principal.organization_id, case_id)
        if archived is None:
            raise NotFoundError("Case")
        await self.session.flush()
        await self._record_case_event(
            archived,
            principal,
            event_type="case.archived",
            event_data={"case_number": archived.case_number, "status": "archived"},
            include_archived_case=True,
        )
        return archived

    async def _get_active_case(self, organization_id: UUID, case_id: UUID) -> Case:
        case = await self.repository.get(organization_id, case_id)
        if case is None:
            raise NotFoundError("Case")
        return case

    async def _require_active_user(self, organization_id: UUID, user_id: UUID) -> None:
        user = await self.users.get(organization_id, user_id)
        if user is None or not user.is_active:
            raise NotFoundError("User")

    def _validate_due_date(self, due_date: date | None) -> None:
        if due_date is not None and due_date < self._today_provider():
            raise InvalidCommandError("The due date must not be in the past.")

    @staticmethod
    def _normalized_search(search_text: str | None) -> str | None:
        if search_text is None:
            return None
        normalized = search_text.strip()
        if not normalized:
            raise InvalidQueryError("The search query must not be blank.")
        if len(normalized) > 200:
            raise InvalidQueryError("The search query is too long.")
        return normalized.casefold()

    async def _record_case_event(
        self,
        case: Case,
        principal: Principal,
        *,
        event_type: str,
        event_data: dict[str, JSONValue],
        include_archived_case: bool = False,
    ) -> None:
        await self.audit.record_event(
            AuditEventCreate(
                organization_id=case.organization_id,
                actor_user_id=principal.user_id,
                event_type=event_type,
                resource_type="case",
                resource_id=case.id,
                case_id=case.id,
                event_data=event_data,
                include_archived_case=include_archived_case,
            )
        )


def _new_case_number() -> str:
    """Return a durable, non-guessable number under the existing storage limit."""

    return f"CASE-{uuid4().hex.upper()}"


def _patch_event_type(command: CasePatch) -> str:
    """Prefer the most meaningful single event type for an atomic mixed patch."""

    if not isinstance(command.status, Unset):
        return "case.status_changed"
    if not isinstance(command.assigned_user_id, Unset):
        return "case.assignment_changed"
    return "case.updated"


def _patch_event_data(
    command: CasePatch,
    case_number: str,
    old_status: str,
    old_assignee: UUID | None,
) -> dict[str, JSONValue]:
    """Build allowlisted operational audit facts without duplicating business content."""

    data: dict[str, JSONValue] = {
        "case_number": case_number,
        "changed_fields": list(command.changed_fields()),
    }
    if not isinstance(command.status, Unset):
        data["old_status"] = old_status
        data["new_status"] = command.status
    if not isinstance(command.assigned_user_id, Unset):
        data["old_assigned_user_id"] = str(old_assignee) if old_assignee is not None else None
        data["new_assigned_user_id"] = (
            str(command.assigned_user_id) if command.assigned_user_id is not None else None
        )
    return data
