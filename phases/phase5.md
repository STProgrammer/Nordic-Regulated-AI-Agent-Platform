# Phase 5 — Backend Repository and Service Layer

## Phase objective

Establish the production-quality repository and service-layer foundation for the
FastAPI backend. The phase must turn the Phase 4 SQLAlchemy schema into a
tenant-safe, testable data-access boundary: repositories own persistence queries;
services own small units of application work and safe persistence-error
translation; future route handlers remain thin adapters.

The implementation must provide common, typed pagination, filtering, sorting,
soft-archive, and audit-event helpers that later phases can reuse without
duplicating unsafe SQL or forgetting organization predicates. Every
organization-scoped access path introduced in this phase must require an explicit
`organization_id` and enforce it in the database query itself.

This phase deliberately establishes backend infrastructure only. It does not
expose CRUD HTTP operations, authenticate users, make authorization decisions,
or implement a product workflow.

## How this phase fits the final product

The PRD requires that cases, documents, logs, evaluations, and settings are
isolated by organization, and that important actions can be audited without
leaking sensitive information. The architecture requires repository/service
separation, backend-enforced organization scoping, typed schemas at boundaries,
and no business logic in route handlers.

Phases 1–4 already supplied the workspace, local services, FastAPI shell,
central safe error response contract, async SQLAlchemy session lifecycle, and a
PostgreSQL/pgvector schema for all core product records. Phase 5 puts an
intentional application boundary in front of those models. Phase 6 will bind the
authenticated current user and RBAC policies to this boundary. Phase 8 and later
feature phases will add actual case/document/workflow API operations on top of
the services added here.

## Relevant specification context and constraints

- PostgreSQL is the system of record. Use the existing SQLAlchemy 2 async
  session path from `app.db.session`; do not introduce a second ORM, raw-SQL
  CRUD layer, or database connection lifecycle.
- `organization_id` is the tenancy boundary. All tenant-scoped repository reads,
  lists, updates, soft archives, and related-resource lookups must include a
  database-level organization predicate. A record identifier by itself is never
  sufficient for a tenant-scoped lookup.
- Authorization is not yet implemented. Phase 5 receives an explicit
  organization identifier from the caller; it must not infer an organization
  from headers, cookies, an untrusted request body, or a global mutable context.
  Phase 6 will establish that the caller is allowed to act for that organization.
- Preserve Phase 4 model conventions: UUIDs, `inserted_at`/`updated_at`,
  `archived_at`, timezone-aware PostgreSQL values, JSONB, conservative foreign
  keys, `lazy="raise"` relationships, and append-only `audit_events`.
- Repositories must not return records across tenants, even when a UUID happens
  to exist in another organization. Treat that result as not found rather than
  revealing whether it belongs to another tenant.
- User-facing routes remain operation-free in this phase. Do not add request or
  response DTOs for cases/documents, change the OpenAPI product surface, or make
  placeholder endpoints that expose storage internals.
- Never expose an `IntegrityError`, SQL statement, database URL, storage key,
  raw exception text, or arbitrary event payload in a public or service error.
  Translate expected persistence conflicts to stable, safe application errors;
  unexpected failures continue through the existing centralized safe error
  handling when a later route owns them.
- Keep current model classes separate from Pydantic API schemas. Typed service
  commands/query options may be introduced in the service layer, but ORM models
  must never be used directly as API response models.
- The database schema is already established. No Alembic migration should be
  needed unless implementation reveals a genuine Phase 4 schema defect. Do not
  add schema fields merely to make a generic CRUD abstraction more convenient.

## In-scope deliverables

1. A clear `app.db.repositories` package with a small, typed base repository and
   explicit repositories for the core tenant roots needed by imminent feature
   phases: organizations, users/roles, cases, documents, workflow runs, and
   audit events.
2. A consistent transaction contract: repositories receive an existing
   `AsyncSession`, never add engines or sessions, and never independently
   commit or roll back request work. Services compose repository operations,
   flush intentionally, and use savepoints where needed to translate known
   database constraint errors safely.
3. An explicit tenant-query mechanism that scopes all applicable lookups and
   mutations by `organization_id`, excludes soft-archived records by default,
   and offers an explicit, typed opt-in for future authorized archival views.
4. Reusable typed query helpers for bounded offset pagination, a stable page
   result, allowlisted filtering/sorting, deterministic default ordering, and
   no untrusted field names or ordering expressions in SQL.
5. Thin service modules for the core repository groups. They provide typed
   add/read/list/update/archive primitives appropriate to persistence
   infrastructure, validate tenant context, map not-found/conflict conditions to
   safe service errors, and leave feature-specific policies to their owning
   phases.
6. An append-only audit-event writer and read helper that always records the
   organization, optional actor/case, event/resource identifiers, timestamp,
   and JSON-safe data. It must provide no update/delete operation and must not
   implicitly write events for reads.
7. Unit and PostgreSQL integration tests proving tenant isolation, basic CRUD
   behavior, archive defaults, pagination/sorting safety, append-only audit
   behavior, transaction behavior, and safe errors.
8. Accurate developer documentation for the new internal layering and test
   commands, without claiming that authentication or feature endpoints exist.

## Out of scope

- Login/logout, password hashing, sessions/tokens, current-user dependencies,
  failed-login rate limiting, role permissions, or separation-of-duties checks
  (Phase 6).
- Public API CRUD endpoints, endpoint request/response DTOs, OpenAPI protected
  operations, or frontend integration (Phases 6–9).
- Case-number allocation, domain validation, case-status transition rules,
  assignment workflow, user-facing search semantics, and case audit event
  production (Phase 8).
- Upload/blob-storage access, MIME checks, parsing, document text/chunk writes,
  embeddings, indexing, or retrieval (Phases 10–13).
- LangGraph execution, workflow state business rules, model calls, risk policy,
  approvals, evaluation execution, memory provider integration, exports,
  observability metrics, or background jobs.
- PostgreSQL row-level security, production database roles, retention/deletion
  jobs, encryption, and infrastructure hardening. The service layer must make
  later enforcement straightforward, but it must not claim it replaces RBAC.
- A generic repository that indiscriminately exposes every model/table or allows
  arbitrary filter expressions. Global roles and the architecture's
  global-or-organization prompt/evaluation entities need explicit semantics in
  their respective future feature phases rather than accidental tenant behavior.
- Changes to `specs/roadmap.md` or `specs/progress.md` during plan generation.

## Likely files, folders, modules, and services affected

### Database repositories

- `apps/api/src/app/db/repositories/__init__.py`
- `apps/api/src/app/db/repositories/base.py` — typed repository protocol/base,
  explicit tenant scope and archival predicates, safe query helpers
- `apps/api/src/app/db/repositories/organization.py`
- `apps/api/src/app/db/repositories/identity.py` — users, global roles, and
  tenant-bound role assignments; no authorization policy
- `apps/api/src/app/db/repositories/case.py`
- `apps/api/src/app/db/repositories/document.py`
- `apps/api/src/app/db/repositories/workflow.py`
- `apps/api/src/app/db/repositories/audit.py`

### Application services and shared service types

- `apps/api/src/app/services/__init__.py`
- `apps/api/src/app/services/common/__init__.py`
- `apps/api/src/app/services/common/pagination.py`
- `apps/api/src/app/services/common/querying.py` — typed filter/sort
  allowlists and deterministic order helpers
- `apps/api/src/app/services/errors.py`
- `apps/api/src/app/services/organization/service.py`
- `apps/api/src/app/services/identity/service.py`
- `apps/api/src/app/services/cases/service.py`
- `apps/api/src/app/services/documents/service.py`
- `apps/api/src/app/services/workflows/service.py`
- `apps/api/src/app/services/audit/service.py`

### Dependency wiring, tests, and documentation

- `apps/api/src/app/api/dependencies.py` — only add typed internal session/service
  dependency aliases or factories if they are needed by future routes; do not
  add route operations
- `apps/api/src/app/db/session.py` — only if a narrow typed session-dependency
  refinement is required; preserve its lazy engine and outer transaction contract
- `apps/api/tests/unit/test_pagination.py`
- `apps/api/tests/unit/test_querying.py`
- `apps/api/tests/unit/test_service_errors.py`
- `apps/api/tests/integration/test_repositories.py`
- `apps/api/tests/integration/test_services.py`
- `apps/api/tests/integration/test_audit_service.py`
- `apps/api/tests/conftest.py` and small synthetic factories/fixtures as needed
- `README.md` and/or `docs/development.md`

Use the existing Phase 4 models and migration test fixture. Avoid changing
`apps/api/migrations/`, model definitions, route modules, or unrelated
workspace/infrastructure files unless an implementation necessity is discovered
and documented.

## Implementation tasks

### 1. Define the layering and transaction contract

1. Add the repository package and document its rules in module docstrings:
   repositories own SQLAlchemy statements and persistence-only behavior;
   services own application-level composition, command validation, safe error
   mapping, and future audit orchestration; routes will later parse HTTP and
   authorize callers.
2. Make every repository constructor receive an `AsyncSession`. Do not call
   `get_sessionmaker`, construct engines, access `Request`, or import FastAPI in
   repositories/services.
3. Preserve `get_db_session()` as the outer API transaction boundary. Repository
   methods must use `add`, `execute`, `scalar`, and `flush` as appropriate, but
   must not call `commit()` or `rollback()` themselves. A service that needs to
   translate a predictable uniqueness/foreign-key failure must use a narrowly
   scoped savepoint so the caller's session remains usable.
4. Establish a small hierarchy of safe service exceptions such as not-found,
   conflict, and invalid-query/command. Their public messages and codes must be
   stable and contain no database internals. Keep HTTP-status mapping out of the
   repository; integrate with `ApiError` only through an intentional adapter if
   a real endpoint later needs it.
5. Keep ORM relationship loading explicit. Because Phase 4 models use
   `lazy="raise"`, repositories must request only the relation data a concrete
   service needs using an explicit loader option; no service may accidentally
   trigger a broad graph/document/audit load.

### 2. Build reusable tenant and archival query primitives

1. Introduce a typed repository base/protocol for models that expose both `id`
   and `organization_id`. Its single-record methods must accept
   `organization_id` and `record_id`, and generate a predicate equivalent to
   `model.id == record_id AND model.organization_id == organization_id`.
2. Provide explicit helpers for tenant-scoped `get`, required-get, list,
   update-by-id, and soft-archive-by-id operations. A cross-organization ID must
   follow the same safe not-found path as an absent ID.
3. Apply `archived_at IS NULL` by default for archivable models. An
   `include_archived` option must be explicit and typed; it must not become a
   client-controlled query-string behavior in this phase. Audit events and other
   non-archivable records must not be forced through this predicate.
4. Treat `organizations` as the tenant root rather than a tenant-scoped child:
   expose only narrowly needed lookup/add/update persistence methods, with no
   misleading organization predicate. Treat `roles` as global as specified by
   the architecture, while keeping `UserRole` mutations/queries explicitly
   organization-bound.
5. For any service operation that associates tenant resources, verify all
   referenced tenant records through scoped repository lookups before writing,
   or rely on the existing composite FK only after deliberately translating its
   safe failure. Never fetch an associated record unscoped and then attach its
   ID to a record in another organization.

### 3. Add safe pagination, filtering, and sorting helpers

1. Add immutable, typed pagination input with a conservative default page
   size, a documented maximum, and validation for negative offsets/invalid
   limits. Return a typed page result containing items, limit, offset, and a
   total count obtained from the same tenant/archival filter set.
2. Provide a typed sort direction and allowlisted sort specification. Repository
   callers must select from a mapping of stable public sort keys to SQLAlchemy
   columns; never interpolate a client-supplied column name, SQL fragment, or
   direction.
3. Apply a deterministic tie-breaker (normally UUID or `inserted_at` plus UUID)
   to every list operation so pagination does not reorder equal values between
   calls. Define an explicit default ordering per core repository, normally
   newest first for time-based records.
4. Design filtering as typed, entity-owned filter data or approved SQLAlchemy
   predicate functions. The common helper may compose predicates, but it must
   not offer a generic arbitrary-field filter API. Keep Phase 8 case filter and
   full-text search semantics out of this phase; only provide the safe reusable
   mechanism they will use.
5. Ensure total counts, list rows, and every filter/sort expression inherit the
   same organization and archival predicates. Do not perform an unscoped count
   followed by a scoped page query.

### 4. Implement core repositories

1. Implement `OrganizationRepository` for intentional tenant-root lookup by ID
   or slug and basic persistence operations. It must not become a public
   organization-admin API.
2. Implement `UserRepository` and `RoleRepository`/role-assignment access with
   organization-bounded user lookup/list/write methods and explicit global-role
   lookup. Preserve the Phase 4 composite tenant membership invariant; do not
   decide which roles may do what.
3. Implement `CaseRepository` using the scoped base for add, get, required
   get, bounded list, persistence-field update, and soft archive. It may persist
   values provided by a future service but must not generate case numbers, set
   status-transition policy, implement assignment behavior, or expose search.
4. Implement `DocumentRepository` using the scoped base for metadata-level
   add/get/list/update/archive primitives only. It must not read/write object
   storage, parsed text, chunks, or embeddings.
5. Implement `WorkflowRunRepository` for tenant-scoped workflow-run persistence
   and list/get operations needed by future orchestration. It must not execute a
   graph, calculate costs, or expose trace behavior.
6. Implement `AuditEventRepository` with only append and scoped read/list
   operations. Do not provide generic update, delete, archive, or replacement
   methods for audit rows. Any future retention behavior needs its own
   authorized, documented design.
7. Keep model-specific allowlisted sort keys close to each repository. Do not
   implement repositories for every Phase 4 table solely for completeness;
   evidence, evaluation, model-usage, prompt, and memory rules remain with their
   dedicated future services.

### 5. Implement thin core services

1. Add typed command/query models or dataclasses internal to the service layer
   for the common persistence primitives. Commands must carry an explicit
   `organization_id` when operating on tenant data and must exclude server-owned
   fields such as IDs/timestamps.
2. Implement small services for organizations, identity persistence, cases,
   documents, workflow runs, and audits. Each service should orchestrate only
   the repository work required by one persistence action, call `flush` at the
   proper point, and return a typed internal result/ORM object for a later API
   schema adapter.
3. Translate duplicate/constraint failures to safe conflicts without leaking the
   constraint name, database values, or SQL. Preserve unexpected errors for the
   centralized error handler and structured logs; do not catch broad exceptions
   merely to replace them with ambiguous failures.
4. Implement `AuditService.record_event(...)` with a typed input that requires
   organization/event/resource data and permits only JSON-serializable event
   metadata. It must retain actor/case/IP/user-agent values only when the caller
   intentionally supplies them. It must not serialize credentials, authorization
   tokens, raw exception objects, or arbitrary request bodies.
5. Provide audit list/read helpers scoped by organization with reusable bounded
   pagination and approved base filters such as event type, resource type, case,
   actor, and time range. Do not expose an Audit API endpoint or role checks yet.
6. Do not make generic persistence services automatically emit audit events in
   this phase. Future product commands must explicitly choose a meaningful event
   type and event payload; automatic writes for reads or incomplete low-level
   updates would add misleading compliance evidence.

### 6. Wire only reusable internal dependencies

1. If useful, add a typed `AsyncSession` dependency alias next to the existing
   settings/request-ID aliases so future route modules can request the existing
   database session consistently. Do not mount an endpoint or require a
   database connection at import time.
2. Provide simple service-construction functions only where dependency injection
   materially improves testability. They must accept the session explicitly and
   remain free of authentication/current-user assumptions.
3. Preserve FastAPI app factory, health endpoints, readiness checks, route
   registry, OpenAPI metadata, request correlation, and error-envelope behavior
   from Phases 2–4. This phase must not make normal app import/startup require a
   migrated database.

### 7. Test the data-access and safety contract

1. Add pure unit tests for pagination bounds/defaults, page metadata, accepted
   sort keys/directions, deterministic tie-breaker behavior, rejection of
   unallowlisted sort/filter input, and safe service exception serialization.
2. Reuse the pgvector PostgreSQL Testcontainers fixture from Phase 4 for
   integration tests. Seed two synthetic organizations and otherwise add only
   synthetic `demo.invalid` users/cases/documents/workflow records.
3. For each tenant-scoped core repository, prove that an organization can add
   and retrieve its own record but cannot retrieve, list, update, or archive an
   identically addressed record from the other organization. Verify the outcome
   is a safe not-found result rather than a cross-tenant disclosure.
4. Exercise basic add/get/list/update/archive behavior with valid model
   values. Verify archived cases/documents are excluded by default, appear only
   through the explicit internal `include_archived` choice, and are not deleted.
5. Verify pagination count and page contents are tenant-consistent; verify
   expected stable ordering under ties; verify only allowlisted sorting is
   executable. Include filtering tests that prove the shared predicate path
   cannot drop organization/archival clauses.
6. Verify global-role lookup remains functional while user-role membership is
   organization-bound and cannot be assigned across tenants. This is a data
   consistency test, not an RBAC-permission test.
7. Verify a constraint violation is mapped to the intended safe service error,
   leaves no partial committed state, and does not expose SQL, DSNs, constraint
   names, or the offending database value. Verify repository/session behavior
   remains usable after a deliberately handled savepoint failure.
8. Verify audit rows can be appended and read only in their organization,
   preserve valid JSON metadata, honour base filters/pagination, and have no
   repository/service update/delete method. Confirm read operations do not write
   new audit events.
9. Run the existing Phase 3/4 suite to ensure the repository layer neither
   changes database migrations nor regresses health/OpenAPI/safe error behavior.

### 8. Document the internal API honestly

1. Update developer documentation with the repository → service → future route
   layering, explicit organization-context requirement, session/transaction
   ownership, archive default, and commands for repository/service tests.
2. Explain that services are internal backend interfaces, not public HTTP APIs;
   authentication and RBAC are intentionally deferred to Phase 6.
3. State that `audit_events` are append-only and that only explicit product
   actions in later phases should write them. Include safe payload guidance and
   forbid secrets/request bodies/raw exception text.
4. Review the diff for accidental schema mutations, public endpoints, raw SQL
   interpolation, broad exception handling, real data, credentials, or future
   feature implementation.

## Required tests and validation

Run checks from the repository root after locked dependencies are installed.
Resolve all failures before declaring the phase complete.

### Focused repository and service validation

```bash
uv run pytest apps/api/tests/unit apps/api/tests/integration
```

The PostgreSQL integration portion must run against PostgreSQL 16 with pgvector,
not SQLite, because tenant composite FKs, JSONB, archive semantics, and
transaction behavior must match the production data platform. The focused tests
must cover the tenant-isolation, CRUD, pagination/sorting, audit append-only,
and safe-error cases listed above.

### Full backend and static validation

```bash
uv run pytest apps/api/tests
pnpm format:check
pnpm lint
pnpm typecheck
uv run ruff format --check apps services packages scripts
uv run ruff check apps services packages scripts
uv run mypy apps services packages scripts
```

All new Python must satisfy the existing strict mypy configuration. Do not add
broad `Any`, blanket type ignores, untyped SQLAlchemy expressions, or catch-all
exception suppression merely to satisfy the checks.

### Local stack compatibility validation

1. Start the existing local stack:

   ```bash
   pnpm dev:up
   ```

2. Apply the existing schema explicitly if the local environment has not already
   done so, then run the focused repository/service suite using the documented
   local/test configuration. This phase must not add implicit migration or seed
   execution to application startup.

3. Verify existing infrastructure remains healthy:

   ```bash
   pnpm verify:local-stack
   curl --fail http://127.0.0.1:8000/health/live
   curl --fail http://127.0.0.1:8000/health/ready
   curl --fail http://127.0.0.1:8000/openapi.json
   ```

4. Confirm no new product route operations have appeared in the generated
   OpenAPI schema and no application import attempts a database query.

5. Stop the stack normally after validation:

   ```bash
   pnpm dev:down
   ```

### Manual review checklist

- Inspect every tenant-scoped statement for an organization predicate, including
  count, list, get, mutation target, and related-resource lookup statements.
- Confirm an object ID from another organization is indistinguishable from a
  missing ID at the repository/service boundary.
- Confirm sort keys are allowlisted SQLAlchemy columns, not raw strings or SQL
  fragments, and every list has deterministic ordering.
- Confirm repositories do not commit/rollback independent of the outer
  transaction and that known constraint translation uses a narrowly scoped
  savepoint.
- Confirm audit events cannot be updated/deleted through the new repository or
  service interfaces, and payload guidance excludes secrets/unsafe raw data.
- Confirm no schema migration, auth/RBAC behavior, route operation, document
  pipeline, workflow graph, or UI was added prematurely.

## Completion criteria

Phase 5 is complete only when all of the following are true:

- The API has a typed repository/service boundary that keeps SQLAlchemy queries
  and persistence mechanics out of future route handlers.
- Core repositories receive existing sessions, make no independent commits or
  rollbacks, use explicit relationship loading, and support the defined basic
  persistence primitives without inventing product behavior.
- Every tenant-scoped access path introduced by the phase accepts and enforces
  `organization_id` at query time; cross-organization reads and mutations are
  safely blocked without resource-existence leakage.
- Pagination, filtering, and sorting are typed, bounded, deterministic, and
  allowlisted; counts and lists use the same tenant/archive predicates.
- Soft-archivable core records are excluded by default and only included by an
  explicit internal option; audit events remain append-only.
- Core services translate expected persistence conflicts/not-found conditions to
  stable safe errors and do not expose SQL/connection details or add partial
  writes.
- Audit helper tests prove tenant scope, append-only behavior, safe structured
  data handling, and no audit rows from reads.
- Repository/service unit and PostgreSQL integration tests pass, as do full API
  tests, formatting, linting, strict type checks, and existing local stack
  health/OpenAPI checks.
- Documentation accurately describes an internal repository/service foundation
  only; no auth, RBAC, public CRUD endpoint, or later feature is claimed as
  complete.
- The implementation remains within this phase and a successful implementation
  is then marked `(DONE)` in `specs/roadmap.md`, with `specs/progress.md`
  updated consistently.

## Risks and dependencies

| Risk or dependency | Impact | Required handling in this phase |
| --- | --- | --- |
| Tenant predicates are omitted from one query path, count, or mutation | A cross-organization record can be disclosed or altered. | Centralize scoped statement construction, require organization ID in every tenant method, and write two-tenant integration tests for every core CRUD path. |
| A generic repository becomes an unrestricted data-access back door | Future code bypasses archive rules, sort allowlists, and domain boundaries. | Keep the base small, expose explicit model repositories, and reject arbitrary columns, SQL fragments, and unscoped `get_by_id` methods. |
| Phase 5 is mistaken for authorization | Callers might supply another organization ID before Phase 6 binds identity/RBAC. | Document the explicit-context trust boundary; implement data isolation now and authentication/authorization only in Phase 6. |
| Repository commits conflict with request transactions | Composite product actions can partially commit or be impossible to roll back. | Repositories never commit/rollback; services use flush/savepoints; retain `get_db_session()` as outer transaction owner. |
| Broad IntegrityError handling leaks SQL or leaves a broken session | Safe error behavior and later requests become unreliable. | Translate only known errors inside scoped savepoints and test error content plus subsequent session usability. |
| Generic filtering/sorting accepts raw caller input | SQL injection or unintended data exposure becomes possible. | Use typed allowlists and SQLAlchemy column expressions only; do not interpolate field names, directions, or filter fragments. |
| Auto-auditing low-level repository operations adds misleading evidence or sensitive logs | The compliance record becomes noisy, incomplete, or unsafe. | Provide an explicit audit writer only; later product services select meaningful event types and minimal payloads. |
| Existing Phase 4 models have lazy relationships and tenant composite FKs | Naive repository code can cause `lazy="raise"` failures or cross-tenant reference errors. | Load relationships explicitly, validate scoped references, and keep integration tests on PostgreSQL/pgvector. |
| Scope expands into Phase 6/8 feature logic | The foundation becomes harder to review and future phases lose clear ownership. | Keep routes operation-free and defer auth/RBAC, case workflow rules, search, upload, orchestration, and UI work exactly as listed above. |

## Notes for the implementation agent

- Treat `architecture.md` §§10–11 and the existing Phase 4 models/migration as
  the persistence contract. If an implementation detail is absent, choose the
  smallest reversible internal abstraction and record the assumption in the
  final implementation report.
- `organization_id` is required for isolation but is not proof of authorization
  until Phase 6. Do not hide that distinction by introducing an unofficial
  current-user mechanism.
- Prefer clear, small explicit repositories over clever generic metaprogramming.
  The system must be easy for a reviewer to verify for tenant safety.
- Keep query options and service command types internal. Public Pydantic API
  request/response schemas belong to the feature phase that owns each endpoint.
- Do not manufacture audit events for reads or raw repository mutations. Audit
  relevance and event taxonomy will be supplied by actual product actions in
  later phases.
- Preserve synthetic-only test data. Use `demo.invalid` identities and avoid
  password hashes, credentials, storage secrets, request bodies, and realistic
  personal data in tests or documentation.
- Do not mark Phase 5 `(DONE)` or update progress until every stated test and
  local validation check has passed and no scope blocker remains.
