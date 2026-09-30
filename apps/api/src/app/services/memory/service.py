"""Governed memory management and fail-closed Drafting presentation retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from agent_orchestrator.graphs.drafting_types import OutputLanguage
from agent_orchestrator.memory.policy import (
    ApprovedTerminologyPayload,
    MemoryOrigin,
    MemoryPolicyError,
    MemoryScope,
    MemoryType,
    MemoryUseOutcome,
    PresentationMemoryContext,
    ProcessHintPayload,
    UserLanguagePreferencePayload,
    WorkflowPresentationPreferencePayload,
    memory_natural_key,
    payload_as_dict,
    validate_memory_payload,
)
from agent_orchestrator.memory.store import ControlledMemoryStore
from agent_orchestrator.types import WorkflowContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.identity import User
from app.db.models.memory import MemoryEntry, MemoryUsageRecord
from app.db.repositories.identity import UserRepository
from app.db.repositories.memory import MemoryRepository
from app.db.repositories.organization import OrganizationRepository
from app.services.audit.service import AuditEventInput, AuditService
from app.services.auth.policy import MemoryAction, authorize_memory_action
from app.services.auth.principal import Principal
from app.services.common.persistence import stage_write
from app.services.errors import NotFoundError

_SETTINGS_KEY = "controlled_memory"
_MAX_PRESENTATION_TERMS = 2
_MAX_PRESENTATION_HINTS = 1


class MemoryStoreUnavailableError(RuntimeError):
    """Safe internal signal; callers must not expose a provider/store error."""


@dataclass(frozen=True)
class MemoryEntryInput:
    memory_type: MemoryType
    content: object


@dataclass(frozen=True)
class MemoryEntryRevision:
    content: object


@dataclass(frozen=True)
class MemoryReadResult:
    """Metadata-safe result for graph composition, not a durable graph state object."""

    presentation: PresentationMemoryContext
    memory_enabled: bool
    considered_count: int
    applied_count: int
    outcome_codes: tuple[str, ...]


class ControlledMemoryService:
    """Own all memory writes and the only approved runtime lookup seam."""

    def __init__(self, session: AsyncSession, *, store: ControlledMemoryStore) -> None:
        self._session = session
        self._store = store
        self._entries = MemoryRepository(session)
        self._organizations = OrganizationRepository(session)
        self._users = UserRepository(session)
        self._audit = AuditService(session)

    async def enabled_for_organization(self, organization_id: UUID) -> bool:
        organization = await self._organizations.get(organization_id)
        if organization is None:
            return False
        return _memory_enabled(organization.settings)

    async def set_enabled(self, principal: Principal, *, enabled: bool) -> bool:
        authorize_memory_action(principal, MemoryAction.CONFIGURE)
        organization = await self._organizations.get(principal.organization_id)
        if organization is None:
            raise NotFoundError("Organization")
        settings = dict(organization.settings)
        settings[_SETTINGS_KEY] = {"enabled": enabled}
        organization.settings = settings
        await self._audit.record_event(
            AuditEventInput(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="memory.organization_enabled"
                if enabled
                else "memory.organization_disabled",
                resource_type="organization_memory",
                resource_id=organization.id,
                event_data={"enabled": enabled},
            )
        )
        return enabled

    async def list_organization_entries(
        self, principal: Principal, *, include_archived: bool
    ) -> tuple[MemoryEntry, ...]:
        authorize_memory_action(principal, MemoryAction.INSPECT)
        return await self._entries.list_organization(
            principal.organization_id, include_archived=include_archived
        )

    async def add_organization_entry(
        self, principal: Principal, command: MemoryEntryInput
    ) -> MemoryEntry:
        authorize_memory_action(principal, MemoryAction.MANAGE)
        payload = validate_memory_payload(
            memory_scope=MemoryScope.ORGANIZATION,
            memory_type=command.memory_type,
            payload=command.content,
        )
        content = payload_as_dict(payload)
        entry = MemoryEntry(
            organization_id=principal.organization_id,
            user_id=None,
            memory_scope=MemoryScope.ORGANIZATION.value,
            memory_type=command.memory_type.value,
            content=content,
            source=MemoryOrigin.ADMIN_APPROVED.value,
            store_key=str(uuid4()),
            natural_key=memory_natural_key(command.memory_type, payload),
            is_active=True,
        )
        await stage_write(self._session, lambda: self._entries.add(entry), resource="Memory entry")
        try:
            await self._store.put(
                organization_id=entry.organization_id,
                user_id=None,
                key=entry.store_key,
                value=content,
            )
        except Exception as error:
            await self._session.rollback()
            raise MemoryStoreUnavailableError() from error
        await self._audit.record_event(
            AuditEventInput(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="memory.entry_created",
                resource_type="memory_entry",
                resource_id=entry.id,
                event_data={
                    "memory_scope": entry.memory_scope,
                    "memory_type": entry.memory_type,
                    "source": entry.source,
                },
            )
        )
        return entry

    async def revise_organization_entry(
        self, principal: Principal, entry_id: UUID, command: MemoryEntryRevision
    ) -> MemoryEntry:
        authorize_memory_action(principal, MemoryAction.MANAGE)
        entry = await self._entries.get_for_update(principal.organization_id, entry_id)
        if entry is None or entry.memory_scope != MemoryScope.ORGANIZATION.value:
            raise NotFoundError("Memory entry")
        memory_type = _memory_type(entry.memory_type)
        payload = validate_memory_payload(
            memory_scope=MemoryScope.ORGANIZATION, memory_type=memory_type, payload=command.content
        )
        content = payload_as_dict(payload)
        natural_key = memory_natural_key(memory_type, payload)
        try:
            await self._store.put(
                organization_id=entry.organization_id,
                user_id=None,
                key=entry.store_key,
                value=content,
            )
        except Exception as error:
            raise MemoryStoreUnavailableError() from error
        entry.content = content
        entry.natural_key = natural_key
        await self._session.flush()
        await self._audit.record_event(
            AuditEventInput(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="memory.entry_revised",
                resource_type="memory_entry",
                resource_id=entry.id,
                event_data={"memory_scope": entry.memory_scope, "memory_type": entry.memory_type},
            )
        )
        return entry

    async def archive_organization_entry(self, principal: Principal, entry_id: UUID) -> MemoryEntry:
        authorize_memory_action(principal, MemoryAction.MANAGE)
        entry = await self._entries.get_for_update(principal.organization_id, entry_id)
        if entry is None or entry.memory_scope != MemoryScope.ORGANIZATION.value:
            raise NotFoundError("Memory entry")
        try:
            await self._store.delete(
                organization_id=entry.organization_id, user_id=None, key=entry.store_key
            )
        except Exception as error:
            raise MemoryStoreUnavailableError() from error
        entry.is_active = False
        entry.archived_at = datetime.now(UTC)
        await self._session.flush()
        await self._audit.record_event(
            AuditEventInput(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="memory.entry_archived",
                resource_type="memory_entry",
                resource_id=entry.id,
                event_data={"memory_scope": entry.memory_scope, "memory_type": entry.memory_type},
            )
        )
        return entry

    async def update_self_language(self, principal: Principal, *, language: OutputLanguage) -> User:
        """Atomically update the canonical account value and its governed representation."""

        user = await self._users.get(principal.organization_id, principal.user_id)
        if user is None or not user.is_active:
            raise NotFoundError("User")
        payload = UserLanguagePreferencePayload(language=language)
        content = payload_as_dict(payload)
        entry = await self._user_language_entry_for_update(
            principal.organization_id, principal.user_id
        )
        if entry is None:
            entry = MemoryEntry(
                organization_id=principal.organization_id,
                user_id=principal.user_id,
                memory_scope=MemoryScope.USER.value,
                memory_type=MemoryType.UI_LANGUAGE_PREFERENCE.value,
                content=content,
                source=MemoryOrigin.SELF_PREFERENCE.value,
                store_key=str(uuid4()),
                natural_key=memory_natural_key(MemoryType.UI_LANGUAGE_PREFERENCE, payload),
                is_active=True,
            )
            await stage_write(
                self._session, lambda: self._entries.add(entry), resource="Language preference"
            )
        else:
            entry.content = content
            entry.is_active = True
            entry.archived_at = None
        try:
            await self._store.put(
                organization_id=principal.organization_id,
                user_id=principal.user_id,
                key=entry.store_key,
                value=content,
            )
        except Exception as error:
            await self._session.rollback()
            raise MemoryStoreUnavailableError() from error
        user.preferred_language = language.value
        await self._session.flush()
        await self._audit.record_event(
            AuditEventInput(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="memory.self_language_changed",
                resource_type="memory_entry",
                resource_id=entry.id,
                event_data={"memory_scope": entry.memory_scope, "memory_type": entry.memory_type},
            )
        )
        return user

    async def record_rejected_write(
        self, principal: Principal, *, memory_type: MemoryType, reason_code: str
    ) -> None:
        """Persist the compact rejection audit event before an HTTP validation error exits."""

        await self._audit.record_event(
            AuditEventInput(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                event_type="memory.write_rejected",
                resource_type="memory_entry",
                event_data={"memory_type": memory_type.value, "reason_code": reason_code},
            )
        )
        await self._session.commit()

    async def presentation_context_for_drafting(
        self,
        context: WorkflowContext,
        *,
        requested_language: OutputLanguage,
        explicit_language: bool,
    ) -> MemoryReadResult:
        """Load bounded validated non-factual presentation values after evidence eligibility."""

        if not await self.enabled_for_organization(context.organization_id):
            return MemoryReadResult(
                presentation=PresentationMemoryContext(),
                memory_enabled=False,
                considered_count=0,
                applied_count=0,
                outcome_codes=("memory_disabled",),
            )

        entries = await self._entries.list_active_for_drafting(
            context.organization_id, context.initiated_by_user_id
        )
        language: OutputLanguage | None = None
        style: Literal["plain", "formal"] | None = None
        terminology: list[tuple[str, str]] = []
        process_hints: list[str] = []
        outcome_codes: list[str] = []
        applied_count = 0
        validated: list[tuple[MemoryEntry, MemoryUseOutcome, str, object | None]] = []
        for entry in entries:
            outcome, reason, payload = await self._validated_store_payload(context, entry)
            validated.append((entry, outcome, reason, payload))

        for _entry, outcome, _reason, payload in validated:
            if (
                outcome is MemoryUseOutcome.APPLIED
                and isinstance(payload, UserLanguagePreferencePayload)
                and not explicit_language
            ):
                language = payload.language
        effective_language = (
            requested_language if explicit_language or language is None else language
        )

        for entry, outcome, reason, payload in validated:
            if payload is not None and outcome is MemoryUseOutcome.APPLIED:
                if isinstance(payload, UserLanguagePreferencePayload):
                    if explicit_language:
                        outcome, reason = MemoryUseOutcome.SKIPPED, "explicit_language_precedence"
                elif isinstance(payload, WorkflowPresentationPreferencePayload):
                    style = payload.style
                elif isinstance(payload, ApprovedTerminologyPayload):
                    if payload.locale is effective_language:
                        terminology.append((payload.source_term, payload.preferred_term))
                    else:
                        outcome, reason = MemoryUseOutcome.SKIPPED, "locale_mismatch"
                elif isinstance(payload, ProcessHintPayload):
                    process_hints.append(payload.guidance)
                else:
                    outcome, reason = MemoryUseOutcome.SKIPPED, "type_not_eligible_for_drafting"
            if outcome is MemoryUseOutcome.APPLIED:
                applied_count += 1
            outcome_codes.append(reason)
            await self._record_usage(context, entry, outcome=outcome, reason_code=reason)

        # Organization terminology follows the eventual target language.  A user
        # preference can set it; otherwise callers retain the normal case/request language.
        presentation = PresentationMemoryContext(
            language=language,
            style=_presentation_style(style),
            terminology=tuple(terminology[:_MAX_PRESENTATION_TERMS]),
            process_hints=tuple(process_hints[:_MAX_PRESENTATION_HINTS]),
        )
        return MemoryReadResult(
            presentation=presentation,
            memory_enabled=True,
            considered_count=len(entries),
            applied_count=applied_count,
            outcome_codes=tuple(sorted(set(outcome_codes)))[:8],
        )

    async def _validated_store_payload(
        self, context: WorkflowContext, entry: MemoryEntry
    ) -> tuple[MemoryUseOutcome, str, object | None]:
        try:
            scope = MemoryScope(entry.memory_scope)
            memory_type = _memory_type(entry.memory_type)
            if scope is MemoryScope.USER and entry.user_id != context.initiated_by_user_id:
                return MemoryUseOutcome.BLOCKED, "user_scope_mismatch", None
            if scope is MemoryScope.ORGANIZATION and entry.user_id is not None:
                return MemoryUseOutcome.BLOCKED, "organization_scope_mismatch", None
            if scope is MemoryScope.USER and entry.source != MemoryOrigin.SELF_PREFERENCE.value:
                return MemoryUseOutcome.BLOCKED, "invalid_origin", None
            if (
                scope is MemoryScope.ORGANIZATION
                and entry.source != MemoryOrigin.ADMIN_APPROVED.value
            ):
                return MemoryUseOutcome.BLOCKED, "invalid_origin", None
            payload = validate_memory_payload(
                memory_scope=scope, memory_type=memory_type, payload=entry.content
            )
            stored = await self._store.get(
                organization_id=context.organization_id,
                user_id=entry.user_id,
                key=entry.store_key,
            )
            if stored != payload_as_dict(payload):
                return MemoryUseOutcome.SKIPPED, "stale_store_record", None
        except MemoryPolicyError:
            return MemoryUseOutcome.BLOCKED, "invalid_governance_record", None
        except Exception:
            return MemoryUseOutcome.SKIPPED, "store_unavailable", None
        return MemoryUseOutcome.APPLIED, "applied", payload

    async def _record_usage(
        self,
        context: WorkflowContext,
        entry: MemoryEntry,
        *,
        outcome: MemoryUseOutcome,
        reason_code: str,
    ) -> None:
        record = MemoryUsageRecord(
            organization_id=context.organization_id,
            memory_entry_id=entry.id,
            workflow_run_id=context.workflow_run_id,
            operation="drafting_presentation",
            outcome=outcome.value,
            reason_code=reason_code,
        )
        await stage_write(
            self._session,
            lambda: self._entries.add_usage(record),
            resource="Memory usage record",
        )
        await self._audit.record_event(
            AuditEventInput(
                organization_id=context.organization_id,
                actor_user_id=context.initiated_by_user_id,
                event_type="memory.use_recorded",
                resource_type="memory_entry",
                resource_id=entry.id,
                case_id=context.case_id,
                event_data={
                    "memory_scope": entry.memory_scope,
                    "memory_type": entry.memory_type,
                    "outcome": outcome.value,
                    "reason_code": reason_code,
                },
            )
        )

    async def _user_language_entry_for_update(
        self, organization_id: UUID, user_id: UUID
    ) -> MemoryEntry | None:
        from sqlalchemy import select

        statement = (
            select(MemoryEntry)
            .where(
                MemoryEntry.organization_id == organization_id,
                MemoryEntry.user_id == user_id,
                MemoryEntry.memory_scope == MemoryScope.USER.value,
                MemoryEntry.memory_type == MemoryType.UI_LANGUAGE_PREFERENCE.value,
            )
            .order_by(MemoryEntry.updated_at.desc(), MemoryEntry.id.desc())
            .with_for_update()
        )
        from typing import cast

        return cast(MemoryEntry | None, await self._session.scalar(statement))


def _memory_enabled(settings: dict[str, object]) -> bool:
    value = settings.get(_SETTINGS_KEY)
    return isinstance(value, dict) and value.get("enabled") is True


def _memory_type(value: str) -> MemoryType:
    try:
        return MemoryType(value)
    except ValueError as error:
        raise MemoryPolicyError("invalid_memory_type") from error


def _presentation_style(value: str | None) -> Literal["plain", "formal"] | None:
    if value == "plain":
        return "plain"
    if value == "formal":
        return "formal"
    return None
