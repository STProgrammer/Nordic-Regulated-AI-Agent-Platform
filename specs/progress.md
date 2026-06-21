# Progress

Implementation status for each roadmap phase. A phase is `DONE` only when its
implementation, tests, and validation checks pass within its defined scope.

| Phase | Title                              | Status |
| ----- | ---------------------------------- | ------ |
| 1     | Repository and Workspace Foundation | DONE   |
| 2     | Local Docker Development Environment | DONE   |
| 3     | Backend API Skeleton               | DONE   |
| 4     | Database Foundation and Migrations | DONE   |
| 5     | Backend Repository and Service Layer | DONE   |
| 6     | Authentication, Sessions, and RBAC | DONE   |
| 7     | Frontend Application Shell          | DONE   |
| 8     | Case Management Backend             | DONE   |
| 9     | Case Management UI                  | DONE   |
| 10    | Secure Document Upload and Storage  | DONE   |
| 11    | Document Parsing Pipeline            | DONE   |
| 12    | Chunking, Embeddings, and Indexing  | DONE   |
| 13    | Retrieval Service Foundation        | DONE   |
| 14    | Evidence Panel and Document UI      | DONE   |
| 15    | RAG Answering with Citations        | DONE   |
| 16    | Agent Orchestrator Foundation        | DONE   |
| 17    | Intake Graph                         | DONE   |
| 18    | Evidence Graph                        | DONE   |
| 19    | Extraction Graph                      | DONE   |
| 20    | Drafting Graph                        | DONE   |
| 21    | Risk and Compliance Graph              | DONE   |
| 22    | Human Approval Workflow                | DONE   |
| 23    | Workflow Trace and AI Audit Trail      | DONE   |
| 24    | Controlled LangMem Memory              | DONE   |
| 25    | Evaluation Dataset and Deterministic Evaluation Runner | DONE   |
| 26    | AI Quality Evaluation Dashboard        | DONE   |
| 27    | Cost, Latency, Metrics, and Observability | DONE   |
| 28    | Export and Mock Enterprise Integrations | DONE   |
| 29    | Security Hardening                     | DONE   |

## Phase 29 — Security Hardening (DONE)

Completed on 2026-06-22.

Delivered strict environment-configured CORS/CSRF origins, uniform API security headers, deployed
HSTS and documentation defaults, fail-closed HMAC-keyed limits for protected expensive routes, and
bounded multipart/OOXML upload validation. The local Next.js shell retains its same-origin `/api`
rewrite and adds deployment-only CSP/HSTS headers. The locked Python and JavaScript dependency
graphs were upgraded to remove audit findings; local `bandit`, `pip-audit`, production dependency,
and tracked-file secret scans are now available. `SECURITY.md` and `docs/security.md` document the
boundary, reporting, scan, synthetic-data, and malware-scanning limitations.

Validation: focused security/upload/rate-limit tests (64 passed), full API suite (305 passed), web
suite (42 passed), agent-orchestrator suite (29 passed), formatting, lint, type, lock, frozen-install,
and all security checks passed. A rebuilt loopback-only local stack passed `pnpm verify:local-stack`;
live checks confirmed local docs, safe headers, exact allowed/blocked CORS preflights, and CSRF
rejection/pass-through behavior. The stack was shut down cleanly.

## Phase 28 — Export and Mock Enterprise Integrations (DONE)

Completed on 2026-06-22.

Delivered approved-output actions exclusively within the existing protected Approval boundary:

- Admin and Compliance Reviewer users can export a terminal human-approved output as server-owned
  JSON, CSV, Markdown, or PDF. JSON/Markdown/PDF include approved text and safe citation locators;
  CSV contains only structured fields and safe source locators. No raw source text, internal IDs,
  storage data, reviewer comments, or unapproved draft is exported.
- Clearly labelled, synchronous mock ticket, email, Teams, and archive handoffs. They never make a
  network call, enqueue work, alter document/case state, or archive storage; each records one
  metadata-only workflow tool call and append-only audit event.
- Localized terminal Approval Packet controls with fixed downloads, explicit mock-only wording, and
  a confirmation step. No migration or worker routing was added.

Validation: focused renderer, integration, API/OpenAPI, and frontend controls tests passed. The
full backend suite passed (`290 passed, 1 skipped`); web tests passed (`42 passed`); workspace
format/lint/type checks, locked dependency verification, and production web build passed. A rebuilt
local stack passed `pnpm verify:local-stack`, and focused Playwright passed the synthetic reviewer
approval, PDF download, simulated Teams handoff, and case-worker approved-status journey.

## Phase 27 — Cost, Latency, Metrics, and Observability (DONE)

Completed on 2026-06-21.

Delivered safe, process-wide observability without a schema migration, browser telemetry, dashboard,
collector, or cloud-monitoring resource. The API now provides an opt-in, unversioned Prometheus
`/metrics` endpoint (enabled only by local Compose), safe structured request/worker/service logs,
and optional OTLP trace export. Metric labels are deliberately bounded and exclude organization,
user, case, document, request, query, source, prompt, and exception data.

API request latency/count, retrieval latency, workflow/node outcomes and timing, model latency/token
usage/known cost, parsing failures, deterministic evaluation outcomes, approval decisions, and RAG
refusals are emitted through one process-local façade. Worker task spans propagate only W3C headers;
all Celery bodies remain their existing UUID-only argument. Existing persistence, workflow state,
pricing semantics, and Phase 26 UI projections are unchanged.

Validation: focused observability/API/service/integration and deterministic agent tests passed; Ruff,
strict mypy, repository formatting, and `git diff --check` passed. The rebuilt local stack passed
`pnpm verify:local-stack`; an explicit `GET /openapi.json` trigger was followed by a successful
`/metrics` check for `nordic_api_http_*` samples. The stack was then shut down cleanly.

## Phase 26 — AI Quality Evaluation Dashboard (DONE)

Completed on 2026-06-21.

Delivered an Admin-only, organization-scoped evaluation dashboard in Norwegian Bokmål and English.
It shows latest and paginated run history, typed aggregate metrics, honest missing latency/cost
states, safe failed-result links, and a terminal-run Markdown download. The API now replaces the
free-form run summary with an allowlisted metric projection, exposes safe nested result detail, and
generates/audits the bounded report server-side. No corpus question, source, prompt, model payload,
tenant identifier, or arbitrary JSONB is sent to the browser or report.

The report is rendered from the same projection as the screen, has fixed server-owned filename and
format, supports fixed Bokmål/English labels, and logs only run/dataset identity plus `markdown`.
No schema migration, evaluator/worker policy change, hosted judging, p95 telemetry, or generic
export framework was added.

Validation: focused projection, integration, API/OpenAPI/router/audit tests (20) passed; the web
suite passed 39 tests; frontend lint/typecheck, Ruff, mypy, and repository format checks passed.
The rebuilt local stack migrated cleanly, passed `pnpm verify:local-stack`, and focused Playwright
passed both the Admin dashboard-to-failed-result-to-report path and non-Admin denial. `git diff
--check` passed after clean shutdown.

## Phase 25 — Evaluation Dataset and Deterministic Evaluation Runner (DONE)

Completed on 2026-06-21.

Delivered a checked-in, versioned, Pydantic-validated synthetic corpus spanning Norwegian Bokmal and
English public-sector, banking, energy, and internal-policy scenarios. The pure local runner uses
logical fixture keys and existing closed Intake-routing/final-risk policies to measure exact
retrieval, citation, structural answer-criterion, refusal, risk, and routing behavior without a
model, embedding provider, network call, or database dependency.

The canonical corpus loads idempotently into the existing evaluation tables. Tenant-owned runs bind
to an immutable dataset version/hash, persist one safe result per case, prevent concurrent active
duplicates, and are exposed through an Admin-only, cookie-authenticated API. Celery receives only a
run UUID on the dedicated `evaluation` queue; its worker reloads server-owned data and records only
safe summaries, numeric metrics, pass/fail, logical case keys, and closed failure codes. No dashboard,
hosted judge, semantic-quality claim, cost/latency reporting, or browser work was added.

Validation: all 11 evaluation corpus/runner/CLI tests passed; focused API, worker, OpenAPI/router,
audit, migration, retrieval-citation, Intake, and Risk checks passed; Ruff, mypy, and repository
format checks passed. A rebuilt local stack migrated to `e25a1c6d7f90`, passed
`pnpm verify:local-stack`, and completed a cookie-authenticated synthetic Admin queued-run smoke
with four persisted passing result projections.

## Phase 24 — Controlled LangMem Memory (DONE)

Completed on 2026-06-21.

Delivered an explicitly managed, durable controlled-memory boundary. LangMem-compatible LangGraph
Postgres storage sits behind a server-owned adapter with tenant/user UUID namespaces; SQL remains the
governed inspection record. Closed payload schemas permit only self `nb`/`en` language preference,
organization Drafting presentation preference, approved terminology, and case-independent process
hints. Conservative screening rejects contact/identifier data, storage references, credentials,
prompt-injection language, and case/document references. Existing organizations default to disabled;
Admin controls are tenant-scoped, auditable, and preserve archived history.

Drafting reads only bounded, non-evidentiary presentation context after eligible Evidence has been
revalidated. Explicit language remains authoritative, source/citation/risk/approval/case-state behavior
is unchanged, and state/trace/audit projections contain only enabled/count/outcome metadata. The
localized Admin surface exposes typed settings/inspection/create/revise/archive controls; the existing
locale switcher updates only the current user's closed language preference and keeps working if that
optional request is unavailable.

Validation: controlled-memory policy/store tests (3), Drafting regression tests (3), focused
API/Auth/Audit/Trace/OpenAPI/router tests (24), Postgres persistence integration, and database
foundation migration tests (5) passed; the web suite passed 29 tests. Workspace, format, lint, Ruff,
mypy, and TypeScript checks passed. The rebuilt local stack migrated to `f24d9a7c4102`, passed
`pnpm verify:local-stack`, and the focused Playwright journey passed with Admin enable/create,
metadata-only Drafting use, disablement, and non-Admin denial.

## Phase 23 — Workflow Trace and AI Audit Trail (DONE)

Completed on 2026-06-21.

Delivered a tenant-scoped, metadata-only investigation surface: protected per-run traces of
lifecycle/node/retry/tool/model/source/accounting/final-state metadata; append-only filtered audit
inspection; and safe case-scoped audit reads. A new bounded `workflow_tool_calls` record closes the
durable tool-invocation gap. Response-side sanitization and strict DTO/Zod contracts independently
exclude stored unsafe data, prompts, raw content, credentials, provider bodies, storage details, and
transport diagnostics. The localized Bokmål/English Audit Trail and Workflow Trace views are
accessible, use server-authorized IDs, and retain existing source-context authorization.

Validation: focused tool, API, integration, and web tests passed (27 Vitest tests); strict Ruff,
mypy, ESLint, and TypeScript checks passed; and `git diff --check` passed. The rebuilt local stack
migrated to `c23f4a7b8d91`, passed `pnpm verify:local-stack`, and passed the focused two-test
Playwright flow for trace access, audit filtering, and denied/unknown-resource behavior. The
migration was additionally exercised through a downgrade/upgrade cycle after correcting its UUID
server default.

## Phase 22 — Human Approval Workflow (DONE)

Completed on 2026-06-21.

Delivered a durable, tenant-scoped human approval boundary: a paused approval workflow, review
queue and packet, explicit reviewer decisions, role and separation-of-duties enforcement, and
localized reviewer/case-worker views. The original AI draft remains immutable while an
edit-and-approve result stores separate human final text.

Validation: format, lint, type checks, workspace checks, orchestration tests (23), web tests (24),
and API/integration tests (259 passed, one optional skip) passed. The Compose stack migrated to
Alembic head and passed the local-stack verifier. A manual two-session reviewer/case-worker check
confirmed the approved terminal case state. Completion is recorded with explicit user acceptance of
that manual validation.

## Phase 21 — Risk and Compliance Graph (DONE)

Completed on 2026-06-21.

Delivered the closed, deterministic final-risk assessment slice:

- A fixed seven-node LangGraph workflow that rechecks completed Intake, Evidence, and Draft results
  before evaluating PII, evidence sufficiency, high-impact actions, policy conflict, and
  prompt-injection indicators. It emits only the closed low/medium/high level, reason codes,
  next-state, and approval-required flag; it has no model call or browser-owned risk facts.
- Tenant/RBAC-protected start, status, and latest-assessment reads, UUID-only dedicated Celery
  dispatch, active-run protection, and atomic persistence of one RiskAssessment together with the
  case risk level. High risk always requires later human review, while this phase deliberately
  creates no approval or action.
- A localized, read-only Case Detail panel that starts and polls the closed workflow, displays the
  final level/reasons/next state, and makes the future human-review requirement explicit without
  offering approval controls.

Validation: `pnpm format:check`, `pnpm lint`, `pnpm typecheck`, and `pnpm check:workspace` passed;
the focused graph suite passed (20 tests), the API suite passed (255 passed, 1 intentional Azurite
skip), and the web unit suite passed (22 tests). A clean deterministic Compose stack migrated to
Alembic head, passed `pnpm verify:local-stack`, and passed the complete Playwright Case-to-Intake-to-
Evidence-to-Extraction-to-Drafting-to-Risk browser flow, returning a persisted high-risk result with
no approval action exposed.

## Phase 18 — Evidence Graph (DONE)

Completed on 2026-06-21.

Delivered the first tenant-safe Evidence Graph workflow slice:

- A fixed ten-node LangGraph workflow for server-owned query construction, hybrid candidate
  retrieval, deterministic merge/reranking, permission and approved-source filtering, evidence
  sufficiency, contradiction signalling, and safe persistence. State snapshots and node summaries
  contain only bounded counts, booleans, closed reason codes, and identifier-only citation metadata.
- Closed Evidence start/status operations, UUID-only Celery dispatch, tenant/RBAC enforcement,
  duplicate-delivery protection, persisted source provenance, and content-free audit events. Weak or
  contradictory evidence produces a controlled `needs_more_evidence` terminal state without
  overwriting an independent case outcome.
- A localized Bokmål/English Case Detail Evidence Package panel that can start the closed workflow,
  poll only active runs, show a truthful terminal status, and open the existing authorized bounded
  source-context view for persisted citations. It adds no answer, draft, approval, edit, trace, or
  browser-owned retrieval controls.

Validation: graph tests (5 passed), API suite (253 collected, passing), web unit suite (19 passed),
browser smoke test (1 passed) with a disposable synthetic account, workspace/format/lint/type checks,
and rebuilt local-stack migration/health/OpenAPI verification all passed. The local stack used the
explicit deterministic embedding provider for plumbing only; it does not assert retrieval quality.

## Phase 19 — Extraction Graph (DONE)

Completed on 2026-06-21.

Delivered the Evidence-backed structured-information workflow slice:

- A fixed five-node Extraction Graph with a closed taxonomy for people, organizations, dates,
  deadlines, amounts, references, obligations, tasks, risk observations, missing information, and
  suggested next actions. Provider output is validated per kind and citation membership before any
  field is persisted; raw case/evidence/model data remains out of snapshots and audit records.
- Closed UUID-only extraction dispatch, latest eligible Evidence revalidation, stable field
  persistence, terminal safe status projections, and non-destructive reruns. Missing or stale
  Evidence returns an ordinary `needs_more_evidence` extraction outcome without changing case
  lifecycle or risk.
- Dedicated latest-result field read and typed edit endpoints. Edits retain the original source link,
  mark `human_edited`, update the row timestamp, and atomically write a content-free audit event.
  The localized Case Detail panel renders typed values, confidence bands, source context, and bounded
  field-specific editing; it exposes no generic JSON editor, draft, approval, or final-risk control.

Validation: graph tests (7 passed), API suite (253 collected, passing), web unit suite (20 passed),
and the browser smoke test (1 passed) all passed. A rebuilt deterministic local stack passed Alembic
head, local-stack verification, documentation endpoints, Evidence-to-Extraction execution, typed
field edit, and durable human-edit persistence checks.

## Phase 20 — Drafting Graph (DONE)

Completed on 2026-06-21.

Delivered the Evidence-gated original-draft workflow slice:

- A fixed six-node Drafting Graph with closed Norwegian Bokmål/English language selection, exact
  inline citation validation, a bounded unsupported-claim gate, a no-freeform clarity stage, and
  default-deny snapshot/node projections. Citation or support failure becomes
  `needs_more_evidence` and does not persist or display a draft.
- UUID-only Celery dispatch and an Evidence-rechecking worker that persist exactly one protected
  original `agent_messages` draft and copied same-run source provenance only after validation. The
  start/status contracts expose safe availability, language, citation counts, and closed reason
  codes; the distinct tenant/RBAC-protected draft read route returns only draft text and source ids.
- A localized, accessible Case Detail Draft panel with closed language selection, active-run polling,
  source-context links, and explicit AI-draft/review-required framing. It intentionally has no edit,
  approval, finalization, risk, export, or trace controls.

Validation: graph tests (10 passed), API suite (253 collected, passing), web unit suite (21 passed),
and the Playwright browser smoke test (1 passed) passed. Project workspace/format/lint/type checks
passed; a rebuilt deterministic local stack passed Alembic head, `pnpm verify:local-stack`, and a
real synthetic Evidence-to-Extraction-to-Drafting execution with a completed draft, one citation,
and protected source-context presentation.

## Phases 16–17 — Agent Orchestrator Foundation and Intake Graph (DONE)

Completed on 2026-06-20.

Delivered the first executable, tenant-safe LangGraph workflow slice:

- A strictly typed `agent_orchestrator` workspace package with a bounded LangGraph runtime,
  default-deny state/node summaries, finite retry semantics, provider-neutral structured-output
  ports, deterministic local/test fixtures, tenant-aware prompt loading, and a server-owned tool
  registry. Raw case text, prompt content, provider bodies, credentials, vectors, and exceptions
  are excluded from durable snapshots and normal logs.
- The closed eight-node Intake graph: input validation, language detection, structured case-type and
  domain classification, PII and prompt-injection signals, preliminary risk, suggested next
  workflow, and durable result persistence. It neither launches a later workflow nor changes case
  lifecycle state, creates approvals, or claims final risk.
- Cookie-secured start/status/correction endpoints, a UUID-only Celery task on the dedicated
  `agent-orchestrator` queue, tenant-scoped run/node/model/audit persistence, and an atomic
  low-confidence human correction that accepts only closed case type/domain/reason values.
- A localized Bokmål-first/English Case Detail Intake panel with start, safe polling/result display,
  and accessible low-confidence correction controls. Browser token storage and raw workflow traces
  are not introduced.

Validation: `pnpm check:workspace` (94 paths), `pnpm format:check`, `pnpm lint`, `pnpm typecheck`,
`pnpm test:web` (18 passed), `pnpm test:api` (253 collected, passing), and the focused LangGraph
suite (3 passed) all passed. A rebuilt Compose stack passed migrations, seed, `pnpm verify:local-stack`,
and a real cookie-authenticated synthetic Intake run through API dispatch, Celery, all eight nodes,
PostgreSQL persistence, and the safe status response. No real model credential was used; the local
run used clearly labelled deterministic fixture plumbing.

## Phase 15 — RAG Answering with Citations (DONE)

Completed on 2026-06-20.

Delivered the protected direct RAG answer boundary:

- `POST /api/retrieval/answer` accepts only a readable case, question, and optional `nb`/`en`
  output selection. It always retrieves current approved sources through the existing governed hybrid
  retrieval service, with no client-owned model, source, prompt, score, or context controls.
- Deterministic preliminary evidence checks and server-owned context budgets return a localized
  `needs_more_evidence` result without calling a model when source count/content is insufficient.
  Generated answers require exact, run-local inline `[S#]` labels; unknown, duplicate, malformed, or
  missing citations are suppressed as safe refusals.
- A narrow OpenAI/Azure OpenAI completion adapter builds a fixed source-grounding prompt, treats
  excerpts as untrusted reference material, normalizes safe usage metadata, and returns only a
  neutral `503` for provider or malformed-response failures. Completion credentials and configured
  prices stay secret-safe and are required for staging/production settings.
- Each accepted request creates a `rag_answer` workflow run and persists selected source provenance,
  assistant output where a model ran, model usage/accounting, terminal state, and one content-free
  RAG audit event. No workflow-node rows, case-status changes, graph runtime, or answer UI were added.

Validation: `pnpm test:api` passed (252 passed, 1 skipped), `pnpm format:check`, `pnpm lint`,
`pnpm typecheck`, `pnpm test:web` (18 passed), and `pnpm check:workspace` all passed. A rebuilt
Compose stack passed migration/status validation and `pnpm verify:local-stack`; OpenAPI confirmed the
cookie-secured answer route and `/docs` remained reachable. A real completion response was not run
because no real provider credential was configured locally.

## Phase 3 — Backend API Skeleton (DONE)

Completed on 2026-06-20.

Delivered the durable FastAPI application foundation:

- Typed, injectable application settings (`app.core.config`) read from the
  `NORDIC_API_` environment prefix, with a cached `get_settings` provider and a
  test reset/override seam. No secrets and no database/Redis/Azurite values are part
  of this settings class.
- Safe structured logging (`app.core.logging`) via `structlog`, with idempotent
  configuration, static service/environment context, and request-correlation
  helpers. Request bodies, headers, query values, and raw exceptions are never
  logged.
- Request-correlation middleware (`app.api.middleware`) that assigns/validates an
  `X-Request-ID`, binds it to the log context, returns it on every response, and
  emits one safe completion event.
- A single JSON success/error contract (`app.api.schemas.common`) and centralized
  exception handlers (`app.core.errors`) for explicit API errors, request
  validation (422), unknown routes/method errors (404/405), and unexpected errors
  (500). Error responses never expose internals or secrets.
- A source-of-truth route registry (`app.api.router`) mounting ten operation-free
  product route boundaries under `/api`: auth, users, cases, documents, workflows,
  approvals, retrieval, evaluations, audit, admin.
- Truthful OpenAPI metadata plus local `/docs`, `/redoc`, and `/openapi.json`.
- The worker readiness app and the `/health/live` + `/health/ready` endpoint
  contract are preserved; the readiness storage dependency was later renamed from
  `minio` to `azurite` (see the storage-emulator migration below).

Validation: `pnpm format:check`, `pnpm lint`, `pnpm typecheck`, and
`uv run pytest apps/api/tests` (62 tests) all pass. The local Docker stack
(`pnpm dev:up`) serves health and documentation endpoints, `pnpm verify:local-stack`
passes, and live logs contain only safe context with no secrets.

## Storage emulator migration — MinIO → Azurite

The local object-storage emulator was migrated from MinIO to Azurite (the Azure
Blob Storage emulator) to match the Azure deployment target before any storage code
is built, when the change surface is smallest. This touched only local
infrastructure and the health probe: the Compose `azurite` and `azurite-init`
services, `.env.example` (`AZURITE_*` values using Azurite's well-known public dev
account), the API/worker readiness probe (the `minio` dependency became `azurite`),
the local-stack verifier, and docs. No application storage code exists yet; real
Azure Blob SDK integration still arrives in Phase 10.

## Phase 4 — Database Foundation and Migrations (DONE)

Completed on 2026-06-20.

Delivered the PostgreSQL 16 + pgvector persistence baseline:

- Typed SQLAlchemy 2 models for all Architecture §10.2 entities, with PostgreSQL UUIDs, JSONB,
  INET, arrays, numerics, conservative foreign keys, tenant-reference constraints, soft-archival
  fields, and `lazy="raise"` relationships.
- One Alembic baseline migration enabling `pgcrypto` and `vector`, creating all tables, named
  indexes and constraints, a `vector(1536)` HNSW cosine index, a language-neutral GIN full-text
  index, and database triggers for UTC `updated_at` values. The downgrade/replay path retains
  shared PostgreSQL extensions safely.
- Secret-safe runtime/Alembic database configuration, lazy async engine/session construction, a
  migration status checker, and explicit pool disposal during API shutdown.
- Explicit, idempotent synthetic local fixtures: one fake Norwegian organization, the five future
  RBAC roles, and `demo.invalid` identities without password hashes or a login path.
- PostgreSQL Testcontainers integration coverage for migration/index contracts, all representative
  entity persistence, tenant and uniqueness constraints, seed idempotence, and downgrade/re-upgrade.

Validation: all static checks pass; the focused database suite (`uv run pytest apps/api/tests/unit
apps/api/tests/integration`) passes 36 tests and the complete API suite passes 68 tests. A rebuilt
local Compose stack passed explicit migration/status/seed, rollback and replay, local-stack
verification, health, readiness, and OpenAPI checks. The stack was shut down normally after
validation.

## Phase 5 — Backend Repository and Service Layer (DONE)

Completed on 2026-06-20.

Delivered the internal FastAPI data-access boundary on top of the Phase 4
PostgreSQL schema:

- Explicit async SQLAlchemy repositories for organization roots, tenant-scoped
  users and user-role assignments, cases, document metadata, workflow runs, and
  append-only audit events. Tenant queries require `organization_id` in every
  get, list, update, archive, and count predicate; a cross-organization UUID is
  indistinguishable from a missing record.
- Typed, bounded offset pagination, stable page metadata, model-owned sort
  allowlists, deterministic UUID tie breakers, and explicit archive inclusion
  for cases/documents only. No caller-controlled SQL field or direction is used.
- Thin typed internal services that validate tenant-bound references, retain the
  outer request transaction owner, and translate known `IntegrityError` failures
  through a narrow savepoint to stable safe service errors.
- Explicit `AuditService.record_event` support with JSON-safe metadata
  validation and forbidden secret/request-body fields. Audit reads do not emit
  events; the repository intentionally has no update, delete, or archive API.
- Shared PostgreSQL/pgvector integration fixtures and unit/integration coverage
  for isolation, CRUD persistence, archives, pagination/sorting, savepoint
  recovery, role-assignment scoping, and append-only audit access. Product routes
  remain operation-free, and authentication/RBAC is still deferred to Phase 6.

Validation: `uv run pytest apps/api/tests` passes 85 tests, including PostgreSQL
Testcontainers coverage. `pnpm format:check`, `pnpm lint`, `pnpm typecheck`,
`uv run ruff format --check apps services packages scripts`, `uv run ruff check
apps services packages scripts`, and `uv run mypy apps services packages scripts`
all pass. A rebuilt local Compose stack passed explicit migration/status checks,
`pnpm verify:local-stack`, and live/readiness/OpenAPI curl checks, then was
stopped normally.

## Phase 6 — Authentication, Sessions, and RBAC (DONE)

Completed on 2026-06-20.

Delivered the first protected product APIs and their security boundary:

- Argon2id local-password handling with bounded input validation, malformed-hash
  safety, rehash support, and dummy verification for non-eligible accounts.
- Opaque, HTTP-only, finite Redis sessions with user-wide invalidation on
  password replacement/deactivation, current active-user validation, and current
  role loading from PostgreSQL on every protected request.
- Atomic Redis failed-login limits keyed by HMAC-derived normalized-email and
  client-origin digests, safe `429`/`Retry-After` handling, and fail-closed login
  behavior when the security store is unavailable.
- Cookie-secured `/api/auth/login`, `/api/auth/logout`, and `/api/auth/me`, plus
  OpenAPI cookie security documentation and consistent safe response envelopes.
- Canonical backend RBAC for Admin, Compliance Reviewer, Case Worker, Manager,
  and Read-only Auditor; reusable role/tenant dependencies; and a tested future
  high-risk self-approval separation-of-duties policy.
- Admin-only, organization-scoped `/api/users` and `/api/roles` operations with
  bounded user listing, canonical role replacement, password/deactivation session
  invalidation, safe cross-tenant not-found behavior, sole-active-Admin continuity,
  and minimal append-only audit events.
- Explicit local-only synthetic password provisioning through an environment
  variable name, never a committed credential; updated developer/API guidance.

Validation: focused security/auth/API coverage plus the full backend suite pass
(`108 passed`). `pnpm format:check`, `pnpm lint`, `pnpm typecheck`, Ruff format/
lint, and strict mypy all pass. A rebuilt Compose stack passed migrations,
local-stack verification, health/readiness/OpenAPI checks, and manual login,
cookie, logout, rate-limit, and log-leakage checks before normal shutdown.

## Phase 7 — Frontend Application Shell (DONE)

Completed on 2026-06-20.

Delivered the localized, session-aware Next.js foundation:

- A strict TypeScript App Router web application with Tailwind CSS, next-intl,
  TanStack Query, React Hook Form, Zod, Vitest, Testing Library, and focused
  shared UI primitives.
- Route-based Norwegian Bokmål (`/nb`) as the default UI language, with English
  (`/en`) and a route-preserving, keyboard-operable language switcher. Shared
  date, number, and currency format helpers are ready for future data features.
- A typed same-origin `/api/...` client for the existing Phase 6 login, current
  user, and logout envelopes. It keeps cookies HTTP-only, maps safe failures and
  `Retry-After` values, preserves request ids as support context, and rejects
  malformed responses without displaying raw API payloads.
- Localized login, session lookup, authenticated redirects, retryable
  availability errors, logout, semantic layout landmarks, a skip link, active
  navigation semantics, and account role display. The Cases, Approvals,
  Evaluations, Administration, and Audit routes are deliberate no-data
  placeholders, not fabricated feature behavior.
- A Compose-native Next.js development service and server-only API rewrite,
  replacing the static readiness page. The local verifier now checks a stable
  web-shell marker, while documentation covers Compose versus host API origins
  and safe synthetic-local login provisioning.

Validation: `pnpm format:check`, `pnpm lint`, `pnpm typecheck`, `pnpm test:web`
(10 tests), `pnpm test:api` (108 tests), `pnpm check:workspace`, and a production
web build all pass. A rebuilt Compose stack passed migrations and
`pnpm verify:local-stack`; a generated synthetic local password then verified
same-origin proxy login, reloadable current-user lookup, English login copy,
logout, and post-logout denial without printing credentials or session values.

## Phase 8 — Case Management Backend (DONE)

Completed on 2026-06-20.

Delivered the protected, organization-scoped Case Management API:

- Typed, closed Case submission, patch, response, and list contracts at
  `POST/GET /api/cases`, `GET/PATCH /api/cases/{case_id}`, and
  `POST /api/cases/{case_id}/archive`, with the standard success/error envelope
  and documented opaque-cookie authentication.
- Server-owned organization, submitter, initial `new` status, and non-guessable
  unique case numbers; bounded input validation for title, description, domain,
  priority, language, due date, external reference, filters, pagination, and
  allowlisted sorting.
- A pure lifecycle policy, backend RBAC for reads, submissions, ordinary edits,
  approval-status transitions, and archives, plus safe tenant-local assignee
  validation and explicit nullable field clearing.
- Tenant-safe repository filtering and parameterized case-number/title/
  description search, deterministic pagination, and atomic archive operations
  that set both `archived_at` and persisted `archived` status.
- Exactly one minimal append-only audit row for each successful case mutation in
  the request transaction, without case body content, external references,
  cookies, credentials, or secrets.

Validation: `pnpm format:check`, `pnpm lint`, `pnpm typecheck`,
`pnpm check:workspace`, `pnpm test:api` (133 passed), `pnpm test:web` (10 passed),
and the production web build pass. Ruff format/lint and strict mypy pass. A
rebuilt Compose stack passed explicit migration/status checks and
`pnpm verify:local-stack`. Manual synthetic Case Worker verification covered
login, submission, filtered search, assignment, allowed status transition,
archive, and the expected post-archive `404`, without printing a password or
session value.

## Phase 9 — Case Management UI (DONE)

Completed on 2026-06-20.

Delivered the first usable Case workflow:

- A protected, localized Case Inbox with server-backed text search; status,
  risk, assignee, domain, and priority filters; URL-preserved pagination; safe
  loading/empty/error states; and accessible real metadata displays.
- A validated Case submission route and a Case Detail route that uses typed
  same-origin API contracts, preserves opaque-cookie handling, formats
  calendar dates and timestamps safely, and labels every future capability as
  unavailable rather than fabricating data.
- Complete Norwegian Bokmål and English Case copy, active nested Cases
  navigation, reusable textual status/risk indicators, and direct-link handling
  for malformed or unavailable Case ids.
- A narrow `GET /api/cases/assignees` Case-read model so all Case readers can
  select a human-readable assignee without exposing the Admin-only Users API or
  a general user directory. It returns only active users assigned to visible,
  non-archived current-tenant cases.
- Focused API/client, inbox, form, contract, and repository coverage plus a
  Playwright smoke scenario for synthetic login, submission, search, and Case
  Detail navigation. Browser traces, videos, and screenshots are disabled in
  normal runs and generated output is ignored.

Validation: `pnpm format:check`, `pnpm lint`, `pnpm typecheck`,
`pnpm check:workspace`, `pnpm test:web` (14 tests), `pnpm test:api` (134
passed), and a production web build all pass. A rebuilt Compose stack passed
migration checks and `pnpm verify:local-stack`. The Playwright scenario passed
against that stack with a transient synthetic password, without printing or
persisting credentials.

## Phase 10 — Secure Document Upload and Storage (DONE)

Completed on 2026-06-20.

Delivered the secure raw-document ingestion boundary:

- An authenticated `POST /api/documents/upload` multipart endpoint for one
  supported file or pasted email text attached to an active current-tenant case.
  Its safe typed response exposes only metadata; no blob key, blob URL,
  checksum, credential, or raw content is returned.
- Bounded one-pass validation for PDF, DOCX, TXT, Markdown, CSV, XLSX, EML,
  and pasted email content. It enforces the 25 MiB configured cap while reading,
  normalizes filenames, checks content/signatures and OOXML ZIP structure, and
  calculates the SHA-256 from the exact accepted bytes.
- An injected Azure Blob-compatible private-storage adapter for Azurite locally
  and Azure Blob configuration in cloud environments. It verifies the target
  container is private, writes immutable server-keyed objects, and compensates a
  newly written object when metadata/audit persistence fails.
- Tenant-safe document metadata persistence with `draft`/`internal` defaults,
  closed source-status and confidentiality values, server-owned uploader/case/
  object identity, and `pending` parsing status. No parsing, document download,
  browser UI, retrieval, or source-governance behavior was introduced.
- A least-privilege upload policy for Admin, Case Worker, and Manager roles,
  plus one success-only `document.uploaded` audit event containing only
  operational type/size/status values.

Validation: `pnpm install --frozen-lockfile`, `pnpm format:check`, `pnpm lint`,
`pnpm typecheck`, `pnpm check:workspace`, `pnpm test:web` (14 tests), and
`pnpm test:api` (158 passed, 1 opt-in emulator test skipped) pass. The opt-in
live Azurite adapter test passed, Compose migration/status checks passed, and
`pnpm verify:local-stack` passed. A local synthetic Case Worker login created a
case and successfully uploaded pasted email text; metadata, one audit event,
and one private object were confirmed, while an unsupported-file upload returned
safe `415` and left no additional document/audit/object record.

## Phase 11 — Document Parsing Pipeline (DONE)

Completed on 2026-06-20.

Delivered the governed asynchronous parsing boundary:

- A Redis-backed Celery `document-parser` queue and real local worker with
  JSON UUID-only messages, bounded retries, task time limits, periodic pending
  reconciliation, expired-claim recovery, and a broker/consumer health check.
- Bounded private storage reads that verify the stored byte length and SHA-256
  before parser selection. Raw storage, object keys, checksums, task ids,
  broker details, parser exceptions, and extracted content remain absent from
  public APIs, audit event data, and queue payloads.
- Deterministic parsers for PDF, DOCX, TXT, Markdown, CSV, XLSX, EML, and
  pasted-email EML. Successful extraction stores one canonical `document_texts`
  record plus compact zero-based, half-open page/section location metadata and
  a language value (`nb`, `en`, or `unknown`).
- Guarded `pending` → `processing` → `parsed`/`failed` transitions with
  duplicate-task safety. A failed parse preserves raw metadata, Case state,
  audit history, and a prior good text record; terminal outcomes write only
  stable neutral summaries and safe audit codes.
- Protected metadata-only `GET /api/documents/{document_id}` and
  `POST /api/documents/{document_id}/reprocess` operations. Read access covers
  all Case-read roles; reprocessing is restricted to Admin, Case Worker, and
  Manager, is tenant/archival safe, returns `409` during active processing, and
  writes a minimal reprocess audit event.

Validation: `uv lock --check`, Compose configuration validation, full Ruff and
strict mypy checks, `pnpm check:workspace`, `pnpm format:check`, `pnpm lint`,
`pnpm typecheck`, `pnpm test:web` (14 tests), and `pnpm test:api` (186 passed,
1 opt-in Azurite test skipped) pass. A rebuilt local Compose stack passed
migration/status checks and `pnpm verify:local-stack`; an ephemeral synthetic
TXT document was privately stored, dispatched through the real worker, and
reached `parsed`. The stack was then stopped normally.

## Phase 12 — Chunking, Embeddings, and Indexing (DONE)

Completed on 2026-06-20.

Delivered the governed retrieval-index boundary:

- A durable, independent document indexing lifecycle with `not_ready`,
  `pending`, `indexing`, `indexed`, and `failed` states; safe errors and
  timestamps; a forward migration that backfills parsed documents; and
  conditional tenant-safe claims/recovery.
- Tokenizer-aware chunking of canonical Phase 11 text only. Every stored chunk
  retains contiguous index/order, tenant and document identity, bounded exact
  token count, trusted page/section/location offsets, compact parser/language/
  configuration provenance, and no public content exposure.
- Validated OpenAI and Azure OpenAI embedding adapters plus an explicit
  local/test-only deterministic plumbing provider. Batch results must preserve
  input order and pass finite 1536-dimension checks before persistence.
- Atomic complete-set replacement of `document_chunks`, retaining a prior good
  set through re-index failure. The existing pgvector HNSW cosine and GIN
  `simple` full-text indexes remain the only retrieval storage/indexes; no
  query, ranking, citation, or RAG surface was added.
- A separate `document-indexer` Celery route with UUID-only task messages,
  finite retries/timeouts, stale-claim and pending-work reconciliation, and
  parser-success dispatch after its committed state change. Worker database
  pools are disposed per task to remain safe across Celery event loops.
- Safe additive document metadata and an authorized `POST
  /api/documents/{document_id}/reindex` endpoint. Admin, Case Worker, and
  Manager can request re-indexing; read-only roles cannot. The route returns
  only lifecycle metadata and safe `409`/`422`/`503` behavior.

Validation: `uv lock --check`, full backend tests (`205 passed, 1 skipped`),
Ruff, strict mypy, `pnpm check:workspace`, `pnpm format:check`, `pnpm lint`,
`pnpm typecheck`, `pnpm test:web` (14 passed), and the production web build
pass. Compose configuration validation, the Phase 12 migration upgrade to
`2f7d0bc4a8e1`, and `pnpm verify:local-stack` pass. A local synthetic,
metadata-only re-index request returned `202` and reached `indexed` through the
real worker; audit events recorded the safe re-index request and terminal index
event.

## Phase 13 — Retrieval Service Foundation (DONE)

Completed on 2026-06-20.

Delivered the secure hybrid source-search foundation:

- A protected `POST /api/retrieval/search` route with closed request input and
  bounded, typed source results. It is case-contextual, tenant-scoped, and
  returns no answer, citation, raw document, full chunk, embedding, storage
  metadata, or provider detail.
- A reusable retrieval service with deterministic Unicode query normalization,
  one validated query embedding, separate pgvector cosine and PostgreSQL
  `simple` full-text candidate queries, fixed reciprocal-rank fusion, stable
  tie-breaking, bounded excerpts, and source-status warnings.
- SQL-level organization, active-document, parsed/indexed lifecycle,
  selection, source-status, and restricted-confidentiality predicates on both
  retrieval methods. Approved is the safe default; draft/deprecated are
  explicit operational selections, while restricted and archived selections
  require the documented entitlement and archived sources require exact
  document selection.
- Backend-only retrieval RBAC that excludes Read-only Auditor, plus a safe,
  content-free `retrieval.search_completed` audit event for every successful
  search. No workflow is fabricated and no future retrieved-source, model,
  answer, or citation rows are created.

Validation: `uv lock --check`, Compose configuration validation, focused
retrieval tests (14 unit, 1 PostgreSQL/pgvector/GIN integration, 3 API), full
backend suite, workspace structure/format/lint/type checks, web tests, and
production web build pass. A deterministic-provider Compose stack was rebuilt,
migrated, verified with `pnpm verify:local-stack`, and checked live through an
authorized synthetic Case Worker flow: TXT upload, parse/index completion,
approved-source retrieval, response redaction, and completion audit event.
The disposable credential was neither printed nor persisted in project files.

## Phase 14 — Evidence Panel and Document UI (DONE)

Completed on 2026-06-20.

Delivered the localized Case Detail document and evidence experience:

- Case-scoped document metadata list/detail, lifecycle and confidentiality display, and a narrow
  source-status mutation restricted by backend RBAC to Admin and Compliance Reviewer roles. The
  `archived` source label remains distinct from physical document archival and every successful
  status change writes one content-free audit event.
- A purpose-specific, retrieval-governed, server-bounded source-context endpoint. It reuses the
  Phase 13 tenant, role, source-status, restricted-confidentiality, parsing, and indexing checks;
  it never returns raw documents, storage data, generic chunks, offsets, vectors, or provider data.
- Localized Bokmål/English Documents and Source Evidence sections, typed same-origin clients,
  controlled governance/re-index affordances, truthful ranking/warning displays, and lazy
  keyboard-closeable context opening. No upload UI, download, preview, raw-text browser, model
  answer, or verified answer reference was introduced.
- API, integration, policy, client, component, and Playwright coverage for safe display, source
  governance, context access, evidence rendering, role restrictions, and an indexed synthetic
  document flow.

Validation: `pnpm install --frozen-lockfile`, `uv sync --all-packages --locked`, `uv lock --check`,
Compose configuration, `pnpm check:workspace`, `pnpm format:check`, `pnpm lint`, `pnpm typecheck`,
the production web build, `pnpm test:web` (18 passed), and `pnpm test:api` (231 passed, 1 skipped)
pass. A deterministic-provider local stack migrated to head and passed `pnpm verify:local-stack`.
The authenticated live validation covered document upload, parse/index completion, metadata list,
Case Worker source-status denial, governed retrieval, bounded context redaction, and re-index
acceptance. The browser flow passed against that stack (1 passed) using synthetic data only.
