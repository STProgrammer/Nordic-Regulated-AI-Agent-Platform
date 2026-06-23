# Phase 8 — Case Management Backend

## Phase objective

Implement the first complete, protected Case Management API for the Nordic
Regulated AI Agent Platform. Authenticated users must be able to add,
list, search, filter, retrieve, update, assign, transition, and archive cases
within their own organization. Every state-changing action must be validated,
backend-authorized, tenant-scoped, and recorded as a minimal append-only audit
event.

This phase turns the existing Phase 4 `cases` table and Phase 5 persistence
foundation into usable product API operations. It does **not** build the Case
Inbox or Case Detail UI; those surfaces belong to Phase 9.

## How this phase fits the final product

The PRD describes the platform as a traceable enterprise workflow system, not
a generic chat interface. Cases are the durable business records that later
document ingestion, retrieval, LangGraph workflows, approvals, traces, and
evaluations attach to. This phase establishes a reliable lifecycle before any
AI or document action can add competing, ad-hoc case behavior.

The resulting API is the backend contract Phase 9 will consume for Case Inbox,
case submission, and Case Detail. Later phases must extend this lifecycle
through the same service and authorization policy rather than writing directly
to `Case` from routes, workers, or graphs.

## Relevant specification context and constraints

- Roadmap Phase 8 requires case submission, listing, detail, status updates,
  assignment, filtering, search, archiving, audit events, validation of case
  inputs, and API tests for transitions, organization isolation, and audit
  logging.
- PRD `FR-CASE-001` requires title, description, domain pack, priority,
  language, optional due date, optional external reference, and a server-side
  unique case number. Attachments are a Phase 10 concern.
- PRD `FR-CASE-002` requires search by case number or text plus status, risk,
  assignee, domain, and priority filters. Workflow state is not exposed yet;
  workflow execution arrives in Phase 16.
- PRD `FR-CASE-003` defines the lifecycle statuses: New, Processing, Waiting
  for Human Review, Needs More Evidence, Approved, Rejected, Completed,
  Failed, and Archived. Changes must be logged, and approval states require
  backend authorization.
- PRD `FR-AUTH-002`, `FR-AUTH-003`, `FR-AUDIT-001`, and non-functional
  security requirements require RBAC, tenant isolation, protected routes,
  typed validation, and audit records without secrets or unnecessary content.
- Architecture §§10.2 and 11.2 already define the `cases` data model and the
  final REST paths: `GET/POST /api/cases`, `GET/PATCH /api/cases/{case_id}`,
  and `POST /api/cases/{case_id}/archive`.
- Architecture §§11, 13, 17, and 18 require Pydantic boundary schemas,
  SQLAlchemy repository/service separation, server-enforced authorization,
  safe errors, OpenAPI documentation, and API/integration tests.
- API dates must remain machine-readable: `due_date` is an ISO-8601 calendar
  date (`YYYY-MM-DD`) and timestamps are timezone-aware ISO-8601 values. The
  Phase 7 web formatting helpers localize these values for Norwegian Bokmål or
  English; the API must never emit locale-formatted date strings.

## Existing baseline to extend

The implementation must build on these current components rather than adding
parallel case, identity, or audit systems:

- `apps/api/src/app/db/models/case.py` already has tenant-scoped case fields,
  a unique `(organization_id, case_number)` constraint, user foreign-key
  constraints, status/risk/case-number indexes, timestamps, and soft archival.
- `apps/api/src/app/db/repositories/case.py` already provides scoped get/list,
  add, update, and archive primitives. It lacks Phase 8 filtering, search,
  clearable optional updates, lifecycle policy, and atomic archive-status
  behavior.
- `apps/api/src/app/services/cases/service.py` already validates tenant-local
  user references and translates safe persistence failures. Evolve this service
  into the Case Management domain service; do not put policy in route handlers.
- `apps/api/src/app/services/audit/service.py` provides append-only, JSON-safe
  audit writes and blocks secret-bearing metadata keys. Reuse it in the same
  request transaction as each successful case mutation.
- `apps/api/src/app/api/dependencies.py` resolves an opaque Phase 6 session to
  a current `Principal`. `app.services.auth.policy` contains pure tenant and
  role checks, and `RoleName` is the canonical role enum.
- `apps/api/src/app/api/routes/cases.py` is the intentional Phase 8 route
  placeholder. `SuccessResponse`, `ErrorResponse`, request IDs, centralized
  service-error translation, and documented cookie authentication already exist.
- Phase 7 supplies the web shell and shared locale-aware date formatter, but
  its Cases destination is still a deliberate placeholder. No data UI exists
  yet.

No database migration is expected for the Phase 8 contract: the Phase 4 table
already contains every required field and tenant constraint. Do not modify the
schema merely to duplicate application-level enums. If implementation proves a
new index is essential for a bounded query, add one narrowly scoped Alembic
migration and extend the migration verification coverage; otherwise retain the
existing schema.

## In-scope deliverables

1. Protected, documented Case API operations at the architecture-defined
   endpoints:

   - `POST /api/cases`
   - `GET /api/cases`
   - `GET /api/cases/{case_id}`
   - `PATCH /api/cases/{case_id}`
   - `POST /api/cases/{case_id}/archive`

2. Typed request, query, and response schemas for safe case submission,
   patching, pagination, filtering, sorting, and case views. Every endpoint
   must preserve the established `SuccessResponse`/`ErrorResponse` envelope and
   request-id metadata.

3. A canonical Case lifecycle policy with closed status, priority, domain, and
   language values; validated transitions; role checks; and no caller-supplied
   organization, submitter, case number, case type, or risk level.

4. Tenant-safe repository queries for the required filters and bounded text
   search, using SQLAlchemy expressions and allowlisted sort keys only.

5. Assignment and unassignment support that accepts only an active user in the
   caller's organization, including correct handling of explicit `null` for
   clearable fields.

6. Server-generated, database-enforced unique case numbers and minimal audit
   events for every successful case mutation.

7. Focused unit, API, and PostgreSQL integration coverage plus full workspace
   static checks and local-stack validation.

## Explicit API contract

### Access policy

Authentication is mandatory for every Case endpoint. The organization is
always derived from the server-validated principal; neither request bodies nor
query strings may accept an organization identifier.

| Action | Allowed roles | Notes |
| --- | --- | --- |
| List and get active cases | Admin, Compliance Reviewer, Case Worker, Manager, Read-only Auditor | Read-only Auditor remains read-only. Archived cases remain excluded from normal reads. |
| Submit a case | Admin, Case Worker, Manager | `submitted_by_user_id` is always the current principal. |
| Edit metadata, assign/unassign, or make ordinary lifecycle transitions | Admin, Case Worker, Manager | No team/ownership model exists yet, so scope is organization plus role only. |
| Move a case to `approved` or `rejected` | Admin, Compliance Reviewer | This is a status authorization boundary, not the Phase 22 approval-record workflow. |
| Archive a case | Admin, Case Worker, Manager | Archive is a dedicated operation, never a generic PATCH status value. |

`Read-only Auditor` must never receive a mutating Case operation. All role
checks remain backend checks. A future team-membership or per-case visibility
model may narrow access, but Phase 8 must not invent that data model.

### Request and response shapes

Add `apps/api/src/app/api/schemas/cases.py` (and package exports where the
current schema convention needs them) with closed Pydantic models and
`extra="forbid"` for every write input.

`POST /api/cases` accepts only:

- `title`
- `description`
- `domain`
- `priority`
- `language`
- optional `due_date`
- optional `external_reference`

It returns `201` with a complete safe case view. The API must generate
the case number, set status to `new`, derive the submitter and organization from
the principal, and leave `case_type` and `risk_level` unset for later workflow
phases.

`GET /api/cases` accepts bounded `limit` and `offset` plus these explicit query
options:

- `status`
- `risk_level`
- `assigned_user_id`
- `domain`
- `priority`
- `q` for a bounded, normalized case-number/title/description text search
- allowlisted `sort` and `direction`

The response contains stable page metadata (`items`, `limit`, `offset`,
`total`, `has_more`) and safe case summary data. The implementation must not
accept arbitrary database field names, SQL fragments, raw filter expressions,
or an `include_archived` escape hatch in this phase.

`GET /api/cases/{case_id}` returns the same complete safe case view within the
principal's organization; an absent, archived, or cross-organization ID returns
the existing safe `404 not_found` response.

`PATCH /api/cases/{case_id}` accepts only an explicitly supplied, non-empty
subset of mutable metadata, assignment, and `status`. It must distinguish an
omitted field from a supplied `null` so `assigned_user_id`, `due_date`, and
`external_reference` can be intentionally cleared. It must reject attempts to
edit immutable/system-owned fields such as `case_number`, `organization_id`,
`submitted_by_user_id`, `case_type`, and `risk_level`.

`POST /api/cases/{case_id}/archive` has no body. It atomically sets both the
soft-archive timestamp and the persisted status to `archived`, returns the
archived case view, and makes the case unavailable from normal list/detail
reads.

A `CaseData` response must include at least the case UUID, case number, title,
description, language, domain, nullable case type, priority, status, nullable
risk level, assigned-user identifier, submitter identifier, optional due date,
optional external reference, inserted/updated timestamps, and archival
timestamp when returned by the archive operation. Do not expose user emails,
passwords, session values, raw audit payloads, or future workflow state. If an
assignee display value is included for the Phase 9 consumer, retrieve it through
a tenant-scoped projection and expose only a minimal ID/display-name summary;
do not lazy-load ORM relationships or introduce N+1 queries.

### Canonical values and validation

Use explicit API/domain enums or equivalent closed validation, then persist the
existing normalized strings. Do not accept arbitrary status, priority, domain,
or language values.

- Statuses: `new`, `processing`, `waiting_for_human_review`,
  `needs_more_evidence`, `approved`, `rejected`, `completed`, `failed`, and
  `archived`.
- Priorities: `low`, `normal`, `high`, and `urgent`.
- Initial domain packs: `public_sector`, `banking_compliance`,
  `energy_operations`, and `internal_policy`, reflecting the PRD's primary
  use cases. Do not introduce organization-configurable domain packs yet.
- Languages: `nb` and `en`, matching the established application locale/user
  preference convention. The default is not silently inferred from arbitrary
  browser input; the client supplies one validated value.
- Title: trim surrounding whitespace; require meaningful content; cap at 500
  characters.
- Description: trim surrounding whitespace; require meaningful content; cap at
  20,000 characters. Never copy it into audit metadata or logs.
- Due date: accept only a calendar date, serialize as `YYYY-MM-DD`, and reject
  a past date. Use a testable clock/date seam rather than a brittle hidden
  time dependency if the service performs this rule.
- External reference: optional, trimmed, non-blank when supplied, and capped
  at the existing 255-character storage limit. It is business content, not
  audit metadata.
- Search query: trim and cap at 200 characters; reject a supplied blank query
  rather than silently broadening a search.
- Assignment: accept a UUID or explicit `null`; reject a missing, inactive, or
  cross-organization assignee as safe `404 not_found`/validation behavior
  without exposing a foreign tenant's existence.

Generate the case number server-side as a non-guessable, durable value within
the existing 100-character storage limit, for example
`CASE-<uppercase-UUID-hex>`. The existing unique tenant constraint remains the
authority for collision safety; do not add a fragile application counter or
allow clients to choose their own case number.

### Lifecycle transition policy

Keep transition policy in a pure, tested domain helper used by the Case service.
Routes and repositories must not each maintain their own lifecycle map.

| Current status | Allowed PATCH target status |
| --- | --- |
| `new` | `processing` |
| `processing` | `waiting_for_human_review`, `needs_more_evidence`, `completed`, `failed` |
| `waiting_for_human_review` | `approved`, `rejected`, `needs_more_evidence` |
| `needs_more_evidence` | `processing` |
| `approved` | `completed` |
| `rejected` | none |
| `completed` | none |
| `failed` | `processing` |
| `archived` | none |

`archived` is reachable only through the archive endpoint from any active
status. The archive operation must be idempotence-safe in effect: an already
archived record is no longer visible in normal scope and therefore returns the
same safe `404` rather than disclosing archival state. A request that keeps the
same status, jumps across the table, or attempts to patch `archived` is an
`invalid_command`/`422` and must not add an audit event.

The `approved` and `rejected` transitions require an Admin or Compliance
Reviewer. Phase 8 does not add approval records, pause workflows, validate
AI evidence, or replace Phase 6's future high-risk separation-of-duties policy;
those belong to Phases 17–22. Phase 22 must reuse or deliberately extend this
status policy when it adds durable approval decisions.

### Audit event contract

For every successful state change, write one append-only `AuditEvent` in the
same request-owned database transaction as the case mutation. Use these stable
event types:

- the case-submission audit event
- `case.updated`
- `case.status_changed`
- `case.assignment_changed`
- `case.archived`

Set `organization_id`, `actor_user_id`, `case_id`, `resource_type="case"`, and
`resource_id` from trusted persisted data. Audit `event_data` may contain safe
operational facts such as the case number, changed field names, old/new status,
and old/new assignee UUID strings. It must not include the title, description,
external reference, request body, cookies, credentials, user email, raw errors,
or any secret-bearing key. Reads must not add audit events.

## Out of scope

- Case Inbox, Case Detail, submission, form, loading, empty, and error UI;
  Playwright case navigation; and changes to the Phase 7 placeholder routes
  (Phase 9).
- Document attachment/upload/storage/parsing, object storage, checksums, or
  document links (Phases 10–14).
- Case classification, PII detection, risk calculation, user-editable risk,
  workflow execution, workflow state, LangGraph, prompt/model calls, retrieval,
  evidence, extraction, drafting, or workflow traces (Phases 12–23).
- Approval queue, approval records, human edit tracking, workflow interruptions,
  or full high-risk approval decisions (Phase 22).
- Public audit read endpoints and audit-timeline UI (Phase 23). Phase 8 writes
  audit rows only.
- Team, department, per-case ACL, or configurable-domain models; enterprise
  identity-provider work; CORS/CSRF/security-hardening work; retention deletion;
  exports; cloud changes; or unrelated schema redesign.
- Real personal data, committed credentials, synthetic data outside existing
  local fixtures, or client-side session storage.

## Likely files and modules affected

| Area | Expected changes |
| --- | --- |
| `apps/api/src/app/api/routes/cases.py` | Replace the Phase 8 placeholder with the five protected HTTP operations and accurate OpenAPI summaries/responses. |
| `apps/api/src/app/api/schemas/cases.py` | Add closed request/query/response schemas, enums, page data, and validation helpers. |
| `apps/api/src/app/api/dependencies.py` | Add a request-scoped Case service dependency and reusable principal dependencies only where they reduce duplication. |
| `apps/api/src/app/services/cases/service.py` | Evolve the existing service into the transactional case command/query owner: number generation, validation, assignment checks, lifecycle checks, and audit writes. |
| `apps/api/src/app/services/auth/policy.py` | Add pure Case role/action and transition authorization helpers if needed; preserve the existing tenant guard and approval policy. |
| `apps/api/src/app/db/repositories/case.py` | Add a typed filter object, bounded search/filter predicates, sort allowlist, explicit clearable updates, and an atomic archive implementation that also writes `archived` status. |
| `apps/api/src/app/db/models/case.py` | Update only comments/type-adjacent documentation if necessary; retain the existing schema unless a justified migration is required. |
| `apps/api/src/app/main.py` and route descriptions | Update inaccurate "no case operations" Phase 3 wording so generated API documentation is truthful. |
| `apps/api/tests/unit/` | Add focused lifecycle/authorization/validation unit coverage. |
| `apps/api/tests/api/test_cases.py` | Add HTTP contract, authentication/RBAC, input-validation, error-envelope, and OpenAPI coverage using the established dependency-override approach. |
| `apps/api/tests/integration/` | Extend PostgreSQL-backed repository/service/audit coverage for filters, search, tenancy, transactions, transitions, and archiving. |
| `apps/api/alembic/versions/` and migration tests | Touch only if a newly demonstrated required index needs a migration; include upgrade/downgrade verification if touched. |
| `docs/development.md` and/or `README.md` | Update only the currently documented implemented endpoint list and local API examples if they would otherwise be inaccurate. |

`apps/web` is not an implementation target for this phase. Its existing
formatting helpers already accept ISO dates and will be consumed in Phase 9.

## Implementation tasks

1. **Define the case API vocabulary and schemas.**

   - Add closed enums for case status, priority, domain, and language.
   - Define separate add, patch, list-query, complete-case, and paginated
     case-view models; reuse the established response envelope rather than
     adding a special Case response format.
   - Keep write inputs intentionally small. Omit `organization_id`,
     `submitted_by_user_id`, `case_number`, `risk_level`, and `case_type` from
     caller-controlled models.
   - Normalize strings at the boundary and preserve the distinction between
     omitted and explicit `null` fields using `model_fields_set` or a typed
     internal unset sentinel.
   - Declare documented `401`, `403`, `404`, `409`, and `422` error responses
     consistently with the existing error envelope and cookie-auth scheme.

2. **Extend tenant-scoped repository queries without raw SQL.**

   - Add a `CaseFilters` value object containing only the approved list filters
     and search text.
   - Build SQLAlchemy predicates from the existing `scoped_predicates` helper,
     so the same organization and non-archived condition applies to result rows
     and total counts.
   - Implement parameterized, case-insensitive search across case number,
     title, and description. Keep it bounded and combine it predictably with
     filters; never concatenate user input into SQL.
   - Extend the existing sort allowlist only for real case columns required by
     the API, preserve deterministic UUID tie-breaking, and reject unknown
     sort/direction values through existing safe query errors.
   - Refactor `CaseUpdateValues` or introduce an equally typed command shape so
     nullable fields can be cleared without treating `None` as "not supplied".
   - Override/archive through a scoped atomic statement that changes both
     `archived_at` and `status="archived"`. Continue to use the shared archive
     predicate so a foreign or already archived row is indistinguishable from
     missing.

3. **Implement the Case domain service.**

   - Evolve the existing `CaseService`; retain its tenant-aware repository and
     user-reference behavior rather than adding a second service hierarchy.
   - Add explicit command/query dataclasses for submit, patch, list, and
     archive actions. Keep the current caller-owned transaction model: services
     and repositories never independently commit or roll back.
   - Generate the server-owned case number, force initial `new` status, and set
     the submitter to the current principal before persisting a submission.
   - Resolve assignees only in the principal's organization and require them to
     be active. Support intentional unassignment.
   - Validate the lifecycle matrix and action role before mutation. Reject an
     invalid transition before writing either the case or its audit event.
   - Use `AuditService.record_event` after the case write is staged/flushed so
     the persisted case ID is available. Keep mutation and event within the
     request transaction so neither commits alone.
   - Return tenant-safe not-found failures for foreign case/user IDs and retain
     narrow savepoint handling for known database conflicts.

4. **Add pure authorization policy.**

   - Put role/action checks and terminal-status authorization in the existing
     `app.services.auth.policy` module or a narrowly scoped sibling. The helper
     takes a trusted `Principal` and trusted/persisted case facts; it performs
     no database access.
   - Reuse `ensure_roles` and `guard_tenant_resource`; never accept an
     organization claim from a client or rely on frontend navigation to enforce
     permissions.
   - Keep Phase 6's `authorize_approval` intact for Phase 22. Do not fabricate
     approval persistence merely to support the `approved`/`rejected` status
     boundary.

5. **Expose the HTTP routes and keep handlers thin.**

   - Add a Case service dependency that receives `get_db_session`; use the
     existing current-principal dependency so FastAPI/OpenAPI continues to
     document the opaque cookie scheme.
   - Parse HTTP inputs, construct typed service commands, map persisted case
     views to response models, and attach request-id metadata. Route handlers
     must not contain SQL, lifecycle maps, audit construction rules, or role
     policy logic.
   - Use `201` for submission and ordinary success envelopes for list/detail,
     patch, and archive. Ensure every documented error uses the existing safe
     centralized handler.
   - Update the Cases tag description and top-level API description to state
     the real Phase 8 surface while leaving documents, workflows, approvals,
     retrieval, evaluations, audit reads, and admin boundaries untouched.

6. **Keep documentation and surrounding contracts truthful.**

   - Remove only stale statements that Cases has no operations. Do not claim
     that documents, workflows, approval queues, or audit-read APIs exist.
   - If local developer documentation lists the Phase 6 endpoint surface,
     extend it with the exact Case endpoints, authentication expectation, and
     ISO-date contract. Do not place passwords, session IDs, or real personal
     data in examples.
   - Do not modify `specs/roadmap.md` or `specs/progress.md` during planning.
     The implementation agent may mark Phase 8 done only after all required
     validation has passed.

## Required tests

### Unit tests

- Enum/value and boundary validation for title, description, language, domain,
  priority, due date, external reference, blank search text, and forbidden
  extra/system-owned write fields.
- Lifecycle matrix: every allowed transition succeeds; every disallowed jump,
  terminal-state mutation, same-status patch, and direct `archived` PATCH is
  rejected without a mutation/event.
- Role policy: Read-only Auditor cannot mutate; permitted operational roles can
  perform ordinary actions; only Admin/Compliance Reviewer can approve/reject.
- Audit metadata builder tests proving it contains only allowlisted operational
  facts and never title, description, external reference, request body, or
  secret-like keys.

### API tests

- Missing/invalid opaque session yields `401`; authenticated roles receive the
  expected `403` for forbidden Case actions.
- Successful `POST /api/cases` returns `201`, server-generated case number,
  current-principal organization/submitter, initial `new` status, ISO date, and
  standard response metadata; caller-supplied tenant/system fields yield `422`.
- List pagination, each filter, combined filters, bounded search, sort
  allowlisting, and safe invalid-query errors are covered.
- Detail and mutation of a foreign-tenant or archived ID return `404` without
  leaking data.
- Patch covers metadata update, assignment, explicit unassignment/clearing,
  allowed status change, unauthorized approval status, invalid status change,
  and no-op/empty patch behavior.
- Archive writes `archived` status, removes the record from normal reads, and
  returns the safe archived view.
- OpenAPI includes the five specified paths, typed request/response models,
  documented cookie auth, and protected-route error responses.

### PostgreSQL integration tests

- Repository results and counts remain tenant-scoped for every filter/search
  combination; a matching record in another organization is never returned.
- Search covers case number/title/description through parameterized predicates,
  respects archive exclusion, and works with pagination and deterministic sort.
- Assignment rejects a foreign or inactive user; explicit null updates clear
  only the intended nullable fields.
- The service adds a unique server-owned case number and safely handles a
  database uniqueness conflict without poisoning the request session.
- Transition and archive operations update case state and append exactly the
  expected audit event in the same successful transaction. Failed validation,
  forbidden mutation, and failed transition append no event.
- Audit rows remain append-only, tenant-safe, JSON-safe, and free of case body
  content. Existing Phase 5/6 repository, service, auth, and audit coverage
  must remain green.

## Validation steps

Run the implementation checks from the repository root after adding tests and
before considering the phase complete:

```bash
pnpm format:check
pnpm lint
pnpm typecheck
pnpm check:workspace
pnpm test:api
pnpm test:web
pnpm --filter @nordic-regulated-ai-agent-platform/web build
```

Run the focused backend work while iterating, then the full backend suite:

```bash
uv run pytest apps/api/tests/unit apps/api/tests/api apps/api/tests/integration -q
uv run ruff format --check apps services packages scripts
uv run ruff check apps services packages scripts
uv run mypy apps services packages scripts
```

If Phase 8 adds an Alembic migration, also run the migration checks and the
empty-database upgrade/downgrade/replay coverage before the full suite. Do not
claim a migration is needed merely because the phase introduces repository
queries.

Perform a local Compose smoke check after automated checks pass:

```bash
pnpm dev:up
docker compose --env-file .env.example exec api alembic -c apps/api/alembic.ini upgrade head
docker compose --env-file .env.example exec api python scripts/check_migrations.py
pnpm verify:local-stack
```

On a disposable local database, provision only a synthetic local password by
passing an environment variable name to `scripts/seed_local.py`, then use
`http://127.0.0.1:8000/docs` or a cookie jar to verify login, one case
submission, filtered list/search, a permitted status/assignment change,
archive, and the post-archive `404`. Never print the password or session value.
After manual verification, shut the stack down normally:

```bash
pnpm dev:down
```

## Completion criteria

Phase 8 is complete only when all of the following are true:

- The five architecture-defined Case endpoints are implemented, authenticated,
  tenant-scoped, and accurately represented in OpenAPI.
- New cases validate only the allowed inputs, receive a server-generated unique
  case number, derive tenant/submitter from the session principal, and begin in
  `new` status.
- List/detail operations support the specified bounded filters/search/page
  behavior and do not expose foreign or archived records.
- Patch and archive operations safely support metadata changes, assignment and
  unassignment, the documented lifecycle matrix, and terminal-status RBAC.
- Every successful Case mutation records exactly one minimal, append-only audit
  event in the same transaction, while rejected/read operations record none.
- No route handler contains business lifecycle, authorization, audit, or SQL
  logic; repository/service/dependency boundaries remain consistent with the
  existing architecture.
- Unit, API, integration, formatting, linting, type checking, workspace, web
  regression, build, migration (if applicable), and local-stack checks pass.
- Manual local verification confirms the protected Case flow without exposing a
  password, cookie, secret, raw exception, or real personal data.
- Only after those checks pass, mark Phase 8 `(DONE)` in `specs/roadmap.md` and
  update `specs/progress.md` consistently.

## Risks, dependencies, and explicit assumptions

- **Phase 6 is a hard dependency.** Case authorization must use the existing
  opaque-session principal and canonical role enum, not a new bearer-token or
  frontend authorization mechanism.
- **Existing PostgreSQL fixtures/Testcontainers are required** for meaningful
  tenant, archive, transaction, and audit proof. Keep tests resilient to the
  database-generated UUID/timestamp behavior.
- **No team model exists.** This plan therefore scopes Case access by tenant and
  role, not by an invented manager/team/department relation. A later approved
  data model can refine ownership rules.
- **No actual workflow/approval record exists yet.** The Phase 8 status policy
  is an operational lifecycle baseline. Do not pretend it proves Phase 22
  approval interruption, evidence handling, or high-risk decision tracking.
- **Text search is scoped and bounded.** Implement it with typed SQLAlchemy
  predicates first. Add an index only if testing or a measured query need
  justifies a migration; do not introduce OpenSearch or a standalone search
  service.
- **Only synthetic data is permitted.** Case titles/descriptions/references may
  appear in API responses to authorized users but must not be duplicated into
  logs, audit metadata, tests committed with real data, or documentation.
- **The dirty Phase 7 worktree is pre-existing context.** Preserve it. This
  planning task changes only `phases/phase8.md`; do not rewrite or mark any
  implementation status.

## Notes for the implementation agent

- Read this plan first, then consult the current Phase 6 auth code and Phase 5
  case/audit service boundaries before editing. Treat this plan as the Phase 8
  scope source of truth.
- Keep all external representations typed and explicit. API schemas and
  internal command dataclasses serve different purposes; do not expose ORM
  models directly.
- Prefer a single pure transition/authorization policy and a single Case service
  composition path. In particular, do not let a route set `case.status` while a
  worker or service applies a different transition map.
- Preserve current error semantics: foreign tenant identifiers resolve as safe
  `404`, role violations are `403`, malformed/unsupported inputs are `422`, and
  known database conflicts are safe `409` responses.
- Do not add frontend Case screens, document endpoints, workflow run routes,
  audit-read routes, migrations, or dependencies unless the verified Phase 8
  implementation strictly requires the narrowly justified change described
  above.
- Do not mark the roadmap/progress status complete until every listed test and
  validation step has passed. Report the exact commands, results, assumptions,
  and any narrowly scoped follow-up note at implementation handoff.
