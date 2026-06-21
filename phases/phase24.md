# Phase 24 — Controlled LangMem Memory

## Phase objective

Add a small, durable, LangMem-backed memory capability for explicitly approved, non-sensitive preferences and reusable guidance. Memory must be tenant-scoped, user-scoped when applicable, inspectable, disableable by an organization Admin, and auditable at both management and use time.

This phase is a governance boundary, not a learning system. Memory may shape non-factual presentation preferences in an eligible drafting run, but it must never supply evidence, change retrieval, alter risk/approval decisions, decide a case state, or override a user’s explicit request or source-grounded result.

## Relevant context and constraints

- The roadmap requires controlled LangMem memory for UI-language preferences, organization workflow preferences, approved terminology, and reusable process hints; it also requires scoping, Admin disablement, usage logging, suitable inspection, evidence precedence, and tests for scope, disablement, rejected content, and audit events.
- PRD `FR-AGENT-007` permits only organization-scoped, auditable, non-sensitive memory: user UI/language preferences, approved organization workflow preferences, case-independent process hints, and later approved evaluation-feedback patterns. It requires inspection where appropriate and Admin disablement.
- Architecture §8 permits only these categories and expressly forbids raw personal data, sensitive case details, secrets, unapproved profiling, cross-organization leakage, and hidden decision history. Architecture §10 already provides the tenant-aware `memory_entries` table; its `content` field is not permission to store arbitrary JSON.
- Phase 16 established typed graph state, bounded snapshots, server-owned tool registration, deterministic providers, and safe persistence. Phases 18–21 own evidence, drafting, risk, and approval prerequisites. Phase 23 provides safe trace/audit reads and metadata-only tool-call logging. Reuse those boundaries; do not reimplement them in a memory feature.
- The repository currently has a `MemoryEntry` model and organization `settings`, but no memory repository/service, LangMem dependency, API, Admin UI, or runtime integration. The existing Admin router/page is the intended ownership boundary for organization controls; retain the fixed top-level API-router registry instead of creating a competing `/api/memories` group.
- LangMem supports runtime-configured hierarchical namespaces over a LangGraph store. Use a persistent Postgres-backed store in local/deployed runtime and an in-memory fake only in isolated tests; never silently fall back to process-local memory in an application environment. [LangMem namespace guide](https://langchain-ai.github.io/langmem/guides/dynamically_configure_namespaces/)
- Cookie authentication, backend RBAC, organization scoping, strict Pydantic/Zod contracts, Bokmål-first UI, UUID-only worker messages, content-free audit metadata, and no browser storage of protected records remain mandatory.

## In scope

1. A controlled-memory policy with closed scopes, types, schemas, size limits, content checks, lifecycle states, and safe reason codes.
2. A persistent LangMem/LangGraph-store adapter with server-derived tenant/user namespaces and a governed SQL record for inspection, enablement, and audit correlation.
3. Explicit management of the approved organization-level types: workflow presentation preference, approved terminology, and reusable process hint; plus a tightly bounded self-language preference that remains consistent with the existing `User.preferred_language` field.
4. Organization-level memory enablement controlled only by an Admin, with fail-closed retrieval while disabled and without deleting existing governed records.
5. A server-owned retrieval seam used only at the defined Drafting presentation-context point, with source/evidence/case-state precedence enforced in code and demonstrated in tests.
6. Metadata-only memory-use records and compact audit events for configuration, lifecycle, rejection, disablement, lookup, and application outcomes.
7. Localized, accessible Admin memory settings/inspection UI and a narrow self-preference read/write path where it is needed to persist the chosen UI language.
8. Focused graph, service, API, integration, web, and browser coverage using deterministic synthetic fixtures only.

## Out of scope

- Automatic extraction, reflection, summarization, or learning from case text, document text, retrieved sources, user conversations, approval comments, audit events, drafts, or model output. Do not expose `create_manage_memory_tool`, model-owned memory writes, or a generic chat/agent memory tool.
- Any raw personal data, national identifiers, contact information, sensitive-case information, secrets, credentials, cookies, prompts, provider payloads, source excerpts, case IDs, document IDs, or free-form user profiling in memory or usage/audit records.
- Semantic/vector memory search, embeddings, a memory recommendation engine, cross-case learning, team/user profiling, memory sharing across organizations, or memory retention/analytics jobs.
- Changing the Evidence Graph, retrieval query rewriting/reranking/filtering, citation validation, evidence sufficiency, Risk Graph, approval separation of duties, approval packets, case status, or final human-approved output.
- Evaluation-feedback memory until Phase 25 provides approved evaluation data; evaluation dashboards, broader Admin settings, metrics dashboards, exports, notifications, model/prompt administration, and external provider calls.
- A new top-level API route group, browser token storage, bulk import/export, general user-profile editing, or a public/demo endpoint for memory data.

## Likely files, folders, modules, and services affected

| Area | Likely files/folders | Phase-24 responsibility |
| --- | --- | --- |
| Dependencies and configuration | root `pyproject.toml`/workspace lock, `services/agent_orchestrator/pyproject.toml`, `agent_orchestrator/config.py`, `.env.example` only if non-secret store configuration is necessary | Add compatible LangMem and persistent LangGraph-store support through `uv`; validate versions against the locked LangGraph release and keep connection strings/secrets out of code, logs, and browser output. |
| Database | `apps/api/migrations/versions/`, `db/models/memory.py`, `db/models/organization.py`, `db/models/__init__.py` | Constrain and index the existing `memory_entries` control record; add a minimal metadata-only usage record if needed for per-use accountability. |
| Memory domain | new `db/repositories/memory.py`, `services/memory/`, `agent_orchestrator/memory/` | Centralize policy, persistent-store adapter, namespace construction, controlled retrieval, lifecycle, inspection, and audit/use logging. |
| Graph composition | `graphs/drafting_graph.py`, `graphs/drafting_types.py`, drafting prompt/context seam, `services/workflows/drafting.py`, worker composition only as required | Read a bounded approved presentation context after evidence eligibility is established; never write memory from a graph or include it in state snapshots. |
| API | `api/routes/admin.py`, `api/routes/auth.py`, `api/schemas/admin.py` and/or `schemas/auth.py`, `services/auth/policy.py`, dependencies, router/OpenAPI tests | Add only Admin-owned organization memory controls and a self-owned language-preference operation; retain the existing route-group registry. |
| Web | `app/[locale]/admin/page.tsx`, `components/admin/`, `lib/api/`, query hooks, contracts, locale messages, unit tests | Replace only the Admin placeholder portion owned by this phase with controlled-memory controls and inspection; keep future Admin areas honest placeholders. |
| Tests and docs | agent/API/integration/web/E2E tests, `docs/development.md` | Prove isolation, default-deny behavior, evidence precedence, safety, auditability, and the synthetic local demonstration flow. |

Exact filenames may follow current module conventions, but preserve repository/service separation, current route ownership, strict response envelopes, and the Phase 23 trace/audit safety boundary.

## Implementation tasks

### 1. Establish a closed memory policy before adding storage or UI

1. Define frozen Pydantic types and matching strict Zod contracts for exactly these scopes and entry schemas:
   - `user` / `ui_language_preference`: one `nb` or `en` value tied to the authenticated user;
   - `organization` / `workflow_presentation_preference`: a closed eligible workflow and a closed presentation-style/value set;
   - `organization` / `approved_terminology`: locale plus one bounded preferred-term mapping; and
   - `organization` / `process_hint`: a closed hint category plus bounded, administrator-authored, case-independent guidance.
2. Make `memory_scope`, `memory_type`, origin, lifecycle, and use outcome closed vocabularies. Enforce user-scope/user-ID and organization-scope/no-user-ID invariants at the schema, service, and database levels. Reject unknown keys, blank or overlong text, duplicate active natural keys, arbitrary JSON, arbitrary namespaces, arbitrary tags, and browser-supplied organization/user/workflow identifiers.
3. Add one conservative content policy shared by every write path. It must reject direct identifiers and clearly sensitive patterns (including email addresses, Norwegian national identifiers, phone-like contact data, credentials/tokens, URLs/storage references, case/document IDs, prompt-injection phrases, and pasted source/case content). Reuse the deterministic Phase 17 signal logic where compatible; treat an uncertain policy result as rejected rather than retaining it.
4. Memory entries must be explicitly authored by the appropriate trusted actor. They are never distilled from a case or model output. Preserve source as a closed provenance label such as `self_preference` or `admin_approved`, never arbitrary text.
5. Document and test the precedence order: explicit request and UI locale first; authorization/source governance/evidence/citations next; closed risk and approval policy next; only then an enabled, eligible memory may provide non-factual presentation context. A memory conflict must be omitted with a controlled reason, never resolved by a model.

### 2. Make storage durable, namespaced, and inspectable

1. Add the compatible `langmem` package and the persistent LangGraph Postgres-store support to the workspace through `uv`, lock them, and prove the selected API works with the project’s pinned LangGraph version. Do not introduce an unpinned dependency, an external model provider, or an in-memory runtime fallback.
2. Introduce one `ControlledMemoryStore` adapter. It alone constructs namespaces from trusted UUIDs, for example a fixed product prefix followed by `organization/<organization_id>/organization` or `organization/<organization_id>/user/<user_id>`. Namespace segments, store keys, and read limits are never HTTP/model input.
3. Use the existing `memory_entries` table as the governed inspection record and bind each active entry to a stable store key/namespace. Add only the migration fields, check constraints, unique constraints, and active-list indexes necessary to enforce the policy. If a separate LangGraph-store record is used, its value must be the same validated structured payload and reconciliation must fail closed; no second, unmanaged source of truth is allowed.
4. Add a minimal `memory_usage_records` table only if audit events alone cannot represent a read/application without losing workflow correlation. It may store organization ID, memory-entry ID, optional user/workflow-run IDs, operation/outcome/reason code, and timestamp—never memory content, query text, prompts, source/case/document identifiers, provider values, or raw errors. Index by tenant, entry, workflow, and time.
5. Ensure create/update/archive/disable actions either complete their governed SQL and persistent-store work consistently or surface a safe failure with no active partially synchronized entry. On startup/read, stale store references or missing governed rows are ignored and recorded only with a closed failure code.
6. Do not put memory content, namespaces, store exceptions, connection information, or user identifiers into graph snapshots, Celery messages, trace summaries, normal logs, or audit `event_data`. Phase 23 trace output may show only a bounded applied/skipped count and controlled reason codes when a workflow has relevant usage records.

### 3. Add explicit authorization, controls, and auditing

1. Add a `MemoryAction` policy. Only an active Admin may enable/disable organization memory or create, revise, archive, and inspect organization entries. A user may read/update only their own closed UI-language preference; no role may browse another user’s preference through a general memory endpoint.
2. Persist the organization enablement flag in a typed, namespaced portion of `Organization.settings`, preserving unrelated settings. Default to disabled for existing organizations until an Admin explicitly enables it. A disabled organization returns no usable memory, performs no store search, and cannot be re-enabled by a stale browser mutation.
3. Keep `User.preferred_language` the canonical account preference. The self-language operation atomically validates and updates that field plus its governed user-memory representation; on a mismatch, fail safely and repair through the service rather than trusting either client value.
4. Add Admin routes under the existing `/api/admin` boundary for typed memory settings and bounded organization-entry list/create/revise/archive operations. Add only a narrow current-user Auth-bound route needed for the language preference. Return safe IDs, scope/type, allowed structured fields, active state, actor-independent timestamps, and controlled validation codes—never namespace details, raw audit data, provider/store errors, or hidden/foreign existence.
5. Record compact, transactionally aligned audit events for enable/disable, entry create/revise/archive, rejected write, self-preference change, and memory application/blocked use. Event metadata contains resource IDs, closed type/scope/outcome/reason values, and counts only. Use the Phase 23 audit reader rather than adding memory-specific audit browsing.
6. Handle concurrent Admin revisions and active-entry uniqueness deterministically with row locking/constraints. Archiving disables only the target entry; organization disablement preserves history but prevents all use immediately.

### 4. Integrate only the permitted non-evidentiary drafting context

1. Add a server-composed memory-read port to the agent/runtime boundary. It receives a trusted `WorkflowContext`, not a browser payload, and returns a small typed `PresentationMemoryContext` plus metadata-only use outcomes.
2. In Drafting, load memory only after the existing eligible Evidence package has been revalidated and before the fixed presentation/clarity context is prepared. Read at most a small configured number of active entries in deterministic type/updated-time order; do not run vector/semantic search or invoke a model to choose memory.
3. Only permit the context to select the already supported output language or bounded presentation/terminology wording. It must not add facts, citations, sources, instructions that supersede evidence, retrieval filters, workflow routing, risk level, approval requirement, case status, or final text. The existing citation validator and unsupported-claim gate remain authoritative.
4. If memory is disabled, empty, stale, user/organization-mismatched, malformed, conflicting with an explicit language choice, or unsafe, omit it and continue the normal evidence-grounded drafting path. Do not fail a safe draft merely because optional memory is unavailable.
5. Persist one metadata-only usage outcome per considered/applied entry as appropriate, emit the matching content-free audit event, and keep snapshots/node summaries limited to `memory_enabled`, count, applied count, and closed outcome codes. Never feed raw memory content into the trace/audit payload.
6. Do not add any model-callable memory management/search tool. If LangMem offers generic manager/tool helpers, keep them behind the server adapter or unused; model state and prompts must not gain autonomous write/delete authority.

### 5. Deliver the small Admin and self-preference surfaces

1. Replace the Phase 7 Admin placeholder only with a protected Controlled Memory section. It must show current enablement, explain the allowed/forbidden categories, let an Admin change the organization toggle, list active/archived organization entries with safe structured fields, and create/revise/archive only the closed entry types.
2. Provide a narrow language-preference control only where the existing locale UI can use it without changing routing semantics. An explicit user locale selection updates the self preference through the typed API and invalidates current-user data; rendering must still work when the preference endpoint is unavailable or memory is disabled.
3. Use Bokmål by default and complete English translations. Include semantic labels, clear validation/error text, keyboard-operable controls, confirmation for archive/disable, `aria-live` status feedback, loading/empty/error states, visible focus, and non-color-only enabled/disabled/status cues.
4. Validate every API response with Zod before rendering. Do not put entry content, memory settings, user preferences, usage history, or API results in local/session storage. Non-Admins may see a safe denied state in the Admin page but must gain no data or controls.
5. Update the local developer guide with a synthetic-only walkthrough: enable memory as an Admin, add an approved terminology entry, inspect the tenant-scoped record, run an eligible deterministic Drafting workflow, inspect metadata-only usage/audit events, disable memory, and confirm the next draft runs without applied memory.

## Required tests

### Policy, store, and graph tests

- Closed scope/type/content schemas reject extra fields, arbitrary namespace/key/workflow/user/organization input, overlong text, duplicate active entries, raw PII/contact/identifier/secrets/prompt-injection/source content, and unsupported lifecycle changes.
- Namespace construction is deterministic and has separate organization and user layouts. Cross-organization, cross-user, inactive, archived, malformed, missing-governance, and stale-store records are never returned or applied.
- Persistent-store adapter tests prove an enabled valid entry survives a new service/runtime instance; application environments cannot silently use `InMemoryStore`; isolated tests use a fake/in-memory implementation only through the adapter port.
- Disabled memory performs no usable lookup/application. Re-enable is explicit; archive and disable outcomes are deterministic and do not delete audit history.
- The Drafting integration receives only bounded typed presentation context. It proves an explicit output-language request wins, no memory can introduce an unsupported fact/citation, and evidence insufficiency/risk/approval/case state are identical with memory enabled or disabled.
- No graph state snapshot, node summary, tool-call record, queue message, trace projection, normal log, or error response contains memory content, namespace, secrets, PII, prompt/provider data, or raw store error.

### Persistence, API, authorization, and audit tests

- Migration tests cover constraints, indexes, tenant/user foreign-key invariants, existing-row default-disabled behavior, upgrade/downgrade, and safe access to legacy records.
- Admin-only enablement and organization-entry mutation/inspection enforce cookie auth, active account checks, exact role checks, strict request bodies, organization isolation, concurrency/idempotency, archive behavior, and safe unknown/foreign-resource responses.
- The self-language route can change only the current user’s `nb`/`en` preference; it synchronizes the canonical user value and governed memory record and cannot be used to inspect or alter another user.
- Content-policy rejections leave no active SQL/store entry, usage record, or unsafe audit payload. Store/database failures leave no usable partial entry.
- Valid management and usage flows create the expected metadata-only usage records and append-only content-free audit events. Phase 23’s filtered audit reader can display those events without revealing entry content.
- Existing Drafting, evidence/citation, risk, approval, auth/RBAC, audit/trace, OpenAPI, and router-registry focused tests remain green.

### Web and focused browser tests

- Zod/API-client tests reject malformed settings/entry/preference payloads and never persist results in browser storage.
- Component tests cover Admin and non-Admin states, enable/disable confirmation, closed entry validation, list/archive state, error/empty/loading states, Bokmål/English translations, localized timestamps, semantic labels, and keyboard use.
- Browser coverage with deterministic synthetic data verifies an Admin can configure a safe organization entry, an eligible draft records only metadata usage, a second organization cannot inspect or apply it, disabling memory stops later application, and a non-Admin cannot mutate or inspect the organization memory surface.

## Validation steps

Run focused checks first. Run the focused browser test only after the API/orchestration/web checks pass. Use deterministic providers and synthetic content; do not configure a real model or embedding provider.

```bash
# Required focused checks
uv run pytest services/agent_orchestrator/tests/test_controlled_memory.py
uv run pytest apps/api/tests/api/test_admin_memory.py apps/api/tests/api/test_auth_memory_preference.py
uv run pytest apps/api/tests/integration/test_controlled_memory_service.py
pnpm test:web -- controlled-memory
uv run ruff check apps/api services/agent_orchestrator
uv run mypy apps/api services/agent_orchestrator
pnpm lint:web
pnpm typecheck:web

# Required because this phase changes migrations, a worker-owned workflow seam, and Admin UI
pnpm dev:up
docker compose --env-file .env.example exec api uv run alembic upgrade head
docker compose --env-file .env.example exec api uv run alembic current
pnpm verify:local-stack
pnpm --filter @nordic-regulated-ai-agent-platform/web exec playwright test e2e/controlled-memory.spec.ts
pnpm dev:down
git diff --check
```

If the focused browser test fails, diagnose and fix the current Phase 24 issue, then rerun it once. If it fails again, stop and use the manual fallback below; do not loop or broaden into a full E2E suite.

### Manual fallback validation checklist

Use only after the focused browser E2E fails twice or when explicitly requested.

1. Start the synthetic local stack and log in as an Admin at `http://127.0.0.1:3000/nb/admin`.
2. Enable controlled memory, add one safe approved-terminology entry, and verify the page exposes only its closed safe fields and no namespace/store diagnostics.
3. Run a deterministic eligible Drafting workflow; inspect its trace/audit page and confirm only metadata/count/outcome information is visible—not memory content or protected workflow data.
4. Disable memory, run the same eligible workflow again, and confirm normal source-grounded drafting continues with no applied-memory usage.
5. Log in as a non-Admin and a second-organization user; verify neither can inspect or modify the first tenant’s memory configuration. Review the protected API contracts at `http://127.0.0.1:8000/docs` without exposing cookies or credentials.

## Validation Plan

### Focused validation

- Required: controlled-memory policy/namespace/store tests, Drafting precedence tests, memory service/API/auth tests, audit/usage tests, targeted web tests, and affected lint/type checks.
- Required: migration upgrade/current check and the one focused `controlled-memory.spec.ts` browser journey after focused automated checks pass.

### Broader validation

- Conditional: run `uv run pytest services/agent_orchestrator/tests` when shared runtime, graph state, or persistence ports change; run the affected Drafting/Auth/Audit/Trace API and integration tests when shared services/schemas change; run `pnpm test:web` when shared API contracts, layout, locale controls, or current-user queries change.
- Run router-registry and OpenAPI tests whenever Auth/Admin operations are added. Do not run full API, full integration, or full Playwright suites by default.

### Expensive validation

- The local-stack migration/health verification and focused browser E2E above are required because this phase changes an Alembic schema, a worker-owned graph seam, authenticated Admin UI, and a persisted language preference.
- Full local suites, full Playwright, Docker rebuilds beyond `pnpm dev:up`, deployment checks, manual browser checks, and real provider calls are not required for normal Phase 24 completion; reserve them for explicit CI/release work or a concrete unresolved risk.

## Completion criteria

- Controlled memory accepts only the documented non-sensitive user/organization schemas, stores them durably under server-derived namespaces, remains organization/user isolated, and has no unmanaged in-memory application fallback.
- An Admin can enable/disable and safely manage only organization-level approved entries; a user can change only their own `nb`/`en` preference; disabled, archived, stale, malformed, foreign, or unsafe memory is never retrieved or applied.
- Drafting can consume only a bounded non-factual presentation context after evidence is eligible. Source-grounded evidence, citation validation, explicit user choice, risk, approval, and case-state behavior demonstrably take precedence over memory.
- Memory management and use have content-free, tenant-scoped audit/usage records that can be inspected through existing protected audit/trace surfaces without leaking content, namespaces, PII, secrets, prompts, provider data, or raw errors.
- The localized accessible Admin/self-preference surfaces use strict API contracts and no browser persistence for protected data. Required focused tests, affected static checks, migration/local-stack verification, and focused browser E2E pass. Only then may a later implementation turn mark Phase 24 `(DONE)` and update `specs/progress.md`.

## Risks, dependencies, and notes for the implementation agent

- LangMem’s generic memory-manager/tool helpers can permit model-generated writes. This phase must retain server-only mutation authority and treat LangMem as a persistence/namespace integration behind a narrow adapter, not as a model capability.
- The existing `memory_entries.content` JSONB is a high-risk escape hatch. Closed per-type schemas, database constraints where possible, write-time content screening, and response-side DTOs are all required; no single layer is sufficient.
- Keep store namespaces keyed by trusted UUIDs and recheck tenant/user ownership after every store lookup. A namespace template is not authorization by itself.
- Do not let a preference become a hidden policy instruction. If a process hint or terminology entry conflicts with an explicit request or grounded evidence, omit it and preserve the ordinary Drafting outcome with a safe reason code.
- Database/store synchronization and disablement are security-sensitive. Prefer fail-closed omission over serving stale or ungoverned memory. Tests must cover restart, rollback/failure, duplicate delivery, concurrency, and cross-tenant attempts.
- Preserve the current dirty Phase 23 worktree changes. This is plan-only work: do not mark Phase 24 done or modify `specs/roadmap.md` or `specs/progress.md` during generation.
