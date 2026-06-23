# Phase 23 — Workflow Trace and AI Audit Trail

## Phase objective

Make the regulated AI workflows built in Phases 16–22 inspectable without exposing protected content or secrets. Implement a tenant-scoped workflow trace for each persisted run and a read-only, filterable audit trail. The trace must assemble the run lifecycle, LangGraph node attempts, metadata-only tool calls, model-call accounting, governed retrieved-source references, controlled errors/retries, timing, token usage, estimated cost, and a safe final-state projection.

This phase turns the existing bounded operational records into an honest review surface for case workers, reviewers, and auditors. It must preserve the privacy and authorization boundaries that made the earlier workflows safe: a trace explains how a workflow progressed; it is never a raw state dump, document browser, prompt viewer, credential inspector, or generic operations console.

## Relevant context and constraints

- The roadmap requires trace views for workflow runs, LangGraph nodes, tool calls, model calls, retrieved sources, errors, retries, timing, token usage, cost estimate, and final state. It also requires audit filtering by organization, case, resource type, event type, and time, plus tests for completeness, filtering, roles, and absence of secrets.
- PRD `FR-AUDIT-001` requires immutable important-event records with organization, actor, event type, timestamp, and resource references; audit users must be able to filter and inspect them. `FR-AUDIT-002` requires a per-workflow AI action trace with nodes, timing/status, tool and model calls, token/cost data, errors, and source links, excluding secrets and raw credentials. `FR-HITL-001` and `FR-UI-002` require reviewers and Case Detail users to be able to reach workflow context/trace safely.
- Architecture §§6–7 and §10 establish the records to reuse: `workflow_runs`, `workflow_node_runs`, `agent_messages`, `retrieved_sources`, `model_usage_records`, and `audit_events`. Architecture §11 reserves `GET /api/workflows/{workflow_run_id}/trace`, `GET /api/audit/events`, and `GET /api/cases/{case_id}/audit`; do not invent competing route prefixes.
- The current `GraphRuntime` already records safe node start/finish summaries, retry count, controlled error codes, timing, and a bounded `state_snapshot`. The `WorkflowRun`, `WorkflowNodeRun`, `RetrievedSource`, and `ModelUsageRecord` records already hold most trace metadata. These are source records, not permission to return ORM rows or JSON blobs unchanged.
- The current audit repository/service is already append-only, tenant-scoped, and supports exact event/resource/case/time filters internally. The `/api/audit` router and the `/[locale]/audit` page are intentionally placeholders. Extend those ownership boundaries rather than adding a parallel audit subsystem.
- The server-owned `ToolRegistry` validates and times calls but currently has no durable tool-call history. Add only the minimum metadata-only persistence/port needed for truthful trace rows. Existing graphs may legitimately have no tool calls; do not fabricate calls for direct service composition.
- Model content, prompt text, provider request/response bodies, `AgentMessage.content`, raw document/case text, source excerpts, state dumps, credentials, session/cookie data, storage keys, query text, embeddings, SQL, stack traces, IP address, and user-agent data must not appear in trace or audit responses. Existing safe storage is a helpful first boundary, but Phase 23 must apply an explicit response-side allowlist/redaction boundary as well.
- Every read must derive organization scope from the cookie-authenticated principal. A requested `organization_id` must never select another tenant or become a filter that reveals tenant existence. Foreign or unknown resources remain indistinguishable from not found.
- Preserve existing cookie authentication, backend-enforced RBAC, response/error envelopes, cursor/offset pagination conventions, strict Pydantic/Zod contracts, Bokmål-default i18n, accessible UI patterns, same-origin `/api` browser access, and query-cache conventions. Do not put trace/audit payloads in browser storage.
- The current worktree includes unrelated Phase 22 edits. Preserve them and do not change roadmap/progress state while generating or implementing this phase.

## In-scope deliverables

1. A protected, tenant-scoped workflow-trace read model and `GET /api/workflows/{workflow_run_id}/trace` endpoint built from persisted workflow, node, model-usage, metadata-only tool-call, and governed-source records.
2. A narrowly scoped durable tool-call trace record and recorder port so actual registered tool invocations can appear in future/current graph traces without persisting payload bodies or adding a tool-management product surface.
3. Read-only audit APIs for a paginated filtered tenant audit list and a case-scoped convenience view, with filters for case, resource type, event type, and UTC time range; organization scope is always the authenticated tenant.
4. Purpose-built safe trace/audit DTOs and defensive redaction/size/depth limits that prevent stored unsafe keys or future schema changes from leaking secrets, credentials, prompts, raw content, or exception details.
5. Localized, accessible Workflow Trace and Audit Trail UI: an Audit page with filters/pagination, a per-run trace page reachable from Case Detail/relevant workflow state, and bounded source-context links that reuse existing authorization.
6. Focused backend, persistence, orchestration, web, and browser coverage using deterministic/synthetic fixtures, plus accurate local validation documentation.

## Out of scope

- LangMem memory, memory inspection, or memory usage logging (Phase 24).
- Evaluation datasets/runners, evaluation dashboards, quality metrics dashboards, exports, enterprise integrations, notifications, or provider/model administration (Phases 25–28).
- General structured logging, metrics aggregation, OpenTelemetry export, tracing backends, alerts, retention jobs, p95 dashboards, or a service-wide observability platform (Phase 27).
- Raw LangGraph state export, replay, arbitrary rerun/cancel/resume controls, live event streaming, WebSockets, trace mutation/deletion, or audit-event addition from the browser.
- Prompt content/version-management views, model request/response bodies, AI draft text in the trace, document download/preview, generic chunk browsing, source excerpts, numerical retrieval scores, raw tool input/output, credentials, or exception/stack-trace diagnostics. Existing dedicated draft and authorized source-context routes retain their ownership.
- Changing workflow decisions, risk/approval policy, approval packet semantics, case lifecycle transitions, source-governance rules, or model/provider behavior merely to improve trace presentation.

## Likely files, folders, modules, and services affected

| Area | Likely files/folders | Phase-23 responsibility |
| --- | --- | --- |
| Database | `apps/api/migrations/versions/`, `apps/api/src/app/db/models/workflow.py` | Add an additive metadata-only workflow-tool-call record and indexes required for trace/audit filtering; retain all existing records and audit immutability. |
| Workflow persistence | `apps/api/src/app/db/repositories/workflow.py`, `apps/api/src/app/services/workflows/service.py`, `apps/api/src/app/services/workflows/orchestrator.py` | Add scoped read/query projections and the API-side tool-call recorder; do not move graph policy into routes. |
| Agent core | `services/agent_orchestrator/src/agent_orchestrator/tools/registry.py`, `persistence/ports.py`, related types/tests | Extend the server-composed tool invocation seam to record only identity/status/timing/controlled code and bounded summaries. |
| Audit domain | `apps/api/src/app/db/repositories/audit.py`, `apps/api/src/app/services/audit/service.py`, `apps/api/src/app/services/auth/policy.py` | Complete filter validation, trace/audit read policy, safe event projections, and tenant/case protections. |
| API | `apps/api/src/app/api/routes/audit.py`, `routes/workflows.py`, `routes/cases.py`, `schemas/audit.py`, `schemas/workflows.py`, `dependencies.py` | Implement the architecture-reserved protected GET endpoints and their strict OpenAPI schemas. |
| Web | `apps/web/src/app/[locale]/audit/page.tsx`, a new `app/[locale]/workflows/[workflowRunId]/trace/page.tsx`, `components/audit/`, `components/workflow/`, `components/cases/case-detail.tsx`, `lib/api/`, `lib/*/query.ts`, `messages/nb.json`, `messages/en.json` | Replace the audit placeholder and add link-driven, accessible trace presentation; retain truthful placeholders for later phases. |
| Tests/docs | `apps/api/tests/`, `services/agent_orchestrator/tests/`, `apps/web/src/tests/unit/`, `apps/web/e2e/`, `docs/development.md` | Cover data minimization/roles/filtering and document the synthetic local inspection flow. |

Exact names may follow established conventions, but preserve the existing API router ownership, repository/service separation, and typed frontend API-client boundary.

## Implementation tasks

### 1. Define the safe public trace and audit contracts first

1. Add frozen, `extra="forbid"` Pydantic DTOs and matching strict Zod schemas for:
   - workflow trace header: run ID/name/version, case ID, status, started/finished timestamps, duration, total tokens, estimated cost, and controlled final error code;
   - ordered node attempts: node ID/name, status, start/finish, duration, retry count, allowlisted input/output summaries, and controlled error code;
   - tool-call metadata: tool name, status, start/finish, duration, retry count, and safe result/error classification only;
   - model-call metadata: provider/model/operation, success, input/output/total tokens where available, estimated cost, latency, and controlled error code only;
   - retrieved-source references: citation label, document/chunk IDs for the existing authorized context route, rank, and retrieval method; no excerpt, raw score, or inaccessible source metadata;
   - a final-state projection selected from known safe snapshot fields, reason codes, booleans, enum labels, and counts rather than the persisted JSON object; and
   - audit-list item/page/filter contracts with IDs, safe event/resource/case/actor references, timestamp, and a separately sanitized bounded metadata projection.
2. Establish a closed public status/error vocabulary. Show a persisted controlled error code only; never map it to an exception string or transport/provider details.
3. Implement one recursive response-side sanitizer for summaries and audit metadata. It must default-deny forbidden key names (including case-insensitive/nested secret, authorization, cookie, credential, password, token, prompt, request/response body, query, excerpt, embedding/vector, storage, SQL, exception, traceback, IP, and user-agent variants), bound object depth/keys/list length/string length, reject non-finite numerics, and produce a neutral omitted/invalid marker rather than serializing the unsafe value.
4. Do not expose `AgentMessage.content` or `structured_output` through the trace. A trace may indicate model-call metadata and final-state availability; protected draft/source endpoints remain the only content paths.

### 2. Close the persistence gap for tool-call trace metadata

1. Add one additive Alembic migration and SQLAlchemy model for `workflow_tool_calls` (or an established equivalent) linked to its `workflow_run` and optionally the owning node attempt. Store only tool name, status, started/finished timestamps, non-negative duration/retry count, bounded input/output *summaries*, and a controlled error code. Do not store tool payloads, result bodies, URLs, headers, credentials, document text, or arbitrary exceptions.
2. Add foreign keys, non-negative constraints, and run/node query indexes appropriate to ordered trace assembly. Keep organization scoping through the tenant-owned workflow run and enforce it in every repository query; do not add an unscoped lookup.
3. Extend the agent-core persistence/trace port and the API-side `ToolRegistry` composition so a registered tool invocation records start/finish/failure metadata under an already trusted workflow context. Tool name/graph eligibility stay server-owned. Validation failures and disallowed tools must record only a controlled status/code when a trace row is appropriate; they must never serialize the rejected payload.
4. Preserve the current registry’s typed validation and timing behavior. Existing graphs with direct service calls must yield an empty tool-call collection, not invented calls. Add a deterministic test-only registered tool to prove the recorder contract without introducing a business tool or external call.
5. Do not use `audit_events` as an unstructured substitute for per-invocation workflow trace data. Continue emitting compact content-free audit events where existing workflow behavior already requires them.

### 3. Build tenant-safe trace assembly and read policy

1. Add a trace repository/service that loads the parent run by `(organization_id, workflow_run_id)` and then obtains node attempts, tool calls, model usage, and retrieved sources with explicit parent/run predicates and deterministic ordering. Do not trust a child ID without its tenant-owned run relationship.
2. Verify the case remains readable to the caller before returning a trace. Define and test the role matrix explicitly:
   - a user with existing case-read access may inspect a safe trace only for a case they may read, preserving the Case Detail workflow-trace link;
   - Admin, Compliance Reviewer, and Read-only Auditor may inspect the trace for tenant-readable cases in their read scope;
   - no trace route grants approval, source-search, document-context, case mutation, or cross-organization access.
   Keep the actual enforcement in a dedicated policy/service check, not in conditional frontend rendering.
3. Revalidate every returned retrieved-source reference against current organization/document/source-governance access. If a source has become archived, unavailable, or no longer readable, omit its identifying data and expose at most a safe unavailable count/status; the trace must not become a bypass around document controls.
4. Return node/tool/model/source collections in stable chronological/order-by-rank order and expose null/empty fields truthfully when a workflow did not call a model/tool or has no sources. Do not synthesize accounting values; use persisted run totals and recorded model rows only.
5. Map only allowlisted state snapshot keys into the final-state section. Unknown historical or future keys are ignored. The trace endpoint must remain safe even if a bad legacy row contains prohibited data.
6. Add `GET /api/workflows/{workflow_run_id}/trace` to the existing Workflows router. It is a read-only, cookie-authenticated endpoint with documented 401/403/404/validation contracts and no generic trace query controls.

### 4. Implement audit querying without weakening immutability or tenant isolation

1. Add a dedicated `AuditAction.READ` policy. Permit tenant-wide audit-list inspection to Admin, Compliance Reviewer, and Read-only Auditor; deny Case Worker and Manager tenant-wide browsing. Keep all writes absent from the router and all update/delete/archive repository methods absent.
2. Implement `GET /api/audit/events` with existing bounded pagination plus exact optional `case_id`, `resource_type`, `event_type`, `inserted_after`, and `inserted_before` filters. The organization filter is implicit from the authenticated principal; do not accept a requested organization ID. Validate ISO-8601 UTC bounds, reject an inverted range, normalize ordering, and impose the existing safe page limits.
3. Add the architecture-reserved `GET /api/cases/{case_id}/audit` convenience view. It must first enforce current-tenant case-read authorization, then use the same audit query/projection code with a server-owned case filter. Do not duplicate query logic or expose the tenant-wide list to ordinary Case Workers.
4. Keep audit events append-only. Add only additive filter indexes if query plans require them, prioritizing tenant + case + timestamp and tenant + resource/event type + timestamp access patterns. Preserve existing historical events and their ordering.
5. Return safe actor IDs/display references only where the requesting role is entitled to inspect them. Do not expose password/session/login metadata, IP address, user agent, raw audit `event_data`, or foreign resource existence. Sanitize event metadata again on read even though it was validated on write.
6. Update the Audit router description/OpenAPI documentation so it accurately distinguishes audit-event inspection from the per-workflow trace endpoint.

### 5. Deliver the localized, accessible investigation views

1. Replace the Audit placeholder at `/[locale]/audit` with a protected Audit Trail page. It must offer clearly labelled filters for event type, resource type, case ID, and an inclusive UTC-compatible time range; show active filter state, deterministic paging, loading/empty/error states, and a compact event timeline/table using non-color-only status cues.
2. Add a protected workflow-trace page at `/[locale]/workflows/[workflowRunId]/trace`. Present a semantic summary first, then ordered sections for final state, nodes/retries/errors, tool calls, model calls/accounting, and source references. Empty sections must say that no calls/sources were recorded, not imply missing data.
3. Add trace links from the relevant Case Detail workflow status/panels without embedding a raw trace in every case page. Render links only from server-authorized workflow IDs and handle not-found/forbidden states safely. Source references may open only the existing authorized bounded document-context flow after a deliberate user action.
4. Use Bokmål as the default and add complete English translations. Format timestamps, counts, token values, and NOK cost estimates with existing locale helpers; display unavailable/null accounting distinctly from zero.
5. Use semantic headings, labelled filter inputs, keyboard-operable pagination/source links, visible focus, `aria-live` loading/error feedback, accessible tables or lists with responsive alternatives, and text/icon state labels. Do not rely on color or disclose authorization differences in the UI.
6. Extend the typed web API client/query hooks and tests; all payloads must be Zod-validated before rendering and never cached in local/session storage.

### 6. Document operation and preserve scope

1. Update the developer guide with a synthetic-only trace/audit inspection flow: run an existing deterministic workflow, open its trace from Case Detail, inspect safe timing/retry/model/source metadata, filter its related audit events, and verify that source context remains separately authorized.
2. State clearly that trace/audit data is metadata-only and that Phase 23 does not export/replay workflows, expose prompts/raw model bodies, provide an observability dashboard, or invoke external providers/tools for automated validation.
3. Do not mark Phase 23 `(DONE)` or update `specs/progress.md` in this planning task. A future implementation turn may do so only after the required validations pass.

## Required tests

### Trace, persistence, and safety tests

- The trace assembler returns one complete, deterministic projection for a synthetic run containing multiple node attempts/retries, model usage, tool invocation metadata, retrieved-source references, totals, controlled failure, and a safe final-state subset.
- Runs with no model/tool/source records return truthful empty collections and null accounting rather than fabricated rows or zero values.
- New tool-call persistence records success, controlled failure, duration/retry metadata, and allowed summaries for a test-only tool; it rejects/purges raw payloads, result bodies, URLs, headers, prompt content, credentials, and exception text.
- Migration tests apply from an empty database and upgrade the Phase 22 schema; constraints/indexes prevent invalid duration/retry values and protect parent trace relationships.
- Trace reads are tenant-scoped and case-read protected. Foreign run/child/source IDs, archived/missing runs, unreadable sources, and role violations reveal no resource details.
- Trace DTOs and response sanitizers reject or omit nested/case-insensitive secret sentinels, credentials, cookies, authorization headers, token/password values, prompts, raw case/document/source content, provider bodies, storage values, SQL, stack traces, and IP/user-agent data, including deliberately unsafe legacy JSON rows.
- Existing graph runtime/node persistence, deterministic model usage, Phase 18 source provenance, Phase 20 draft protection, Phase 21 risk data, and Phase 22 pause/resume behavior remain unchanged.

### Audit service and API tests

- Audit list filtering covers the implicit current organization, case, resource type, event type, UTC after/before bounds, deterministic pagination/order, empty results, malformed IDs/timestamps, inverted ranges, and boundary timestamps.
- `GET /api/cases/{case_id}/audit` returns only that readable current-tenant case’s events and cannot be widened with client filter fields.
- Audit list access permits Admin, Compliance Reviewer, and Read-only Auditor, while unauthenticated users, Case Workers, Managers, and foreign/invalid principals are denied appropriately. Case-read trace access follows its separate explicit matrix.
- Audit APIs remain read-only and append-only: no update/delete/mutation route is registered, and responses exclude IP/user-agent, raw unsafe event data, credentials, and unrelated tenant events.
- OpenAPI/router registry tests cover the implemented audit and workflow-trace paths, cookie security, response envelopes, strict schemas, and safe expected error models.

### Web and focused browser tests

- Zod/API-client tests reject malformed trace and audit payloads, including secret-bearing nested summaries. Query hooks use stable keys and do not persist results in browser storage.
- Component tests cover Bokmål/English trace sections, safe empty/unavailable states, retry/error labels, null-versus-zero accounting, localized formatting, source-link keyboard behavior, audit filters, paging, loading/error/empty states, semantic labels, and non-color-only states.
- Browser coverage with deterministic synthetic data verifies: an authorized user opens a trace from Case Detail; sees nodes/model/source metadata but no secret/raw-content sentinel; a Read-only Auditor filters the Audit page by case/event/resource/time; and an unauthorized role cannot reach tenant-wide audit browsing or a foreign trace.

## Validation steps

Focused checks are required. Run the focused browser E2E last, after the focused API, orchestration, and web tests pass. Do not run broad suites by default.

```bash
# Required focused tests and affected static checks
uv run pytest services/agent_orchestrator/tests/test_tool_trace.py
uv run pytest apps/api/tests/api/test_audit.py apps/api/tests/api/test_workflow_trace.py
uv run pytest apps/api/tests/integration/test_audit_service.py apps/api/tests/integration/test_workflow_trace.py
pnpm test:web -- audit workflow-trace
uv run ruff check apps/api services/agent_orchestrator
uv run mypy apps/api services/agent_orchestrator
pnpm lint:web
pnpm typecheck:web

# Required final focused browser check, after the commands above pass
pnpm dev:up
docker compose --env-file .env.example exec api uv run alembic upgrade head
docker compose --env-file .env.example exec api uv run alembic current
pnpm verify:local-stack
pnpm --filter @nordic-regulated-ai-agent-platform/web exec playwright test e2e/audit-trace.spec.ts
pnpm dev:down
git diff --check
```

If the focused browser test fails, diagnose and fix the current Phase 23 issue, then rerun it once. If it fails again, stop; use the manual fallback only as described below.

### Manual fallback validation checklist

Run this checklist only if the focused browser E2E fails twice, or if the user explicitly requests manual validation. It is not required after a passing focused browser E2E.

1. With synthetic data, open a Case Detail trace and verify safe node/model/tool/source metadata appears without a secret or raw-content sentinel.
2. As a Read-only Auditor, filter `http://127.0.0.1:3000/nb/audit` by case, event/resource type, and time; confirm it remains tenant-scoped and read-only.
3. Confirm a Case Worker/Manager cannot browse tenant-wide audit events and a foreign workflow ID reveals nothing. Check `/en/audit` only when localization is part of the suspected failure.

## Validation Plan

### Focused validation

- Required: tool-recorder, trace/redaction, audit-filter/API, and Audit/Trace component tests using deterministic synthetic records.
- Required last step: start the local stack, apply the migration, and run only `e2e/audit-trace.spec.ts` after focused checks pass.

### Broader validation

- Conditional, affected-only: run `uv run pytest services/agent_orchestrator/tests` when changing shared runtime/ports; run the affected API/integration directories when shared repositories, schemas, migrations, or authorization policy changed beyond the focused paths; run `pnpm test:web` when shared client/layout contracts changed.
- Run the matching static/workspace checks when the affected change crosses those boundaries. Do not run full API, full integration, or full browser suites by default.

### Full validation

- Not required for normal Phase 23 completion. Reserve full Playwright, full API/integration suites, and extended manual checks for an explicit user request, CI/release validation, or an unresolved risk that focused and affected-only checks cannot cover.

## Completion criteria

- An authorized current-tenant user can retrieve a complete, deterministic safe trace for a readable workflow run, covering its lifecycle/final state, nodes/retries/errors, actual tool calls, model metadata/accounting, and currently authorized source references without fabricating unavailable data.
- Tool invocation metadata is durably recorded through a server-owned, bounded interface; it contains no raw payload/result content or secrets, and existing direct-service graphs truthfully show no tool calls.
- Audit users can filter immutable audit events by the required dimensions within their own organization, and case-scoped audit reads honor case authorization. No API can add, update, delete, or cross tenant-browse audit events.
- Trace/audit DTOs and UI defensively exclude secrets, raw credentials, prompts, cookies/tokens, provider bodies, raw case/document/source text, storage information, exception traces, IP addresses, and user agents even when unsafe historical JSON is seeded.
- The Workflow Trace and Audit Trail are accessible, localized in Bokmål and English, link safely from Case Detail/source context, have truthful loading/empty/error states, and do not use browser storage for protected data.
- Required focused tests, affected static checks, migration/local-stack verification, and the focused final browser E2E pass. Conditional broader/full checks run only when their stated trigger applies. Only then may a later implementation turn mark Phase 23 `(DONE)` in `specs/roadmap.md` and update `specs/progress.md` if present.

## Risks, dependencies, and notes for the implementation agent

- Phase 23 depends on the persisted safe-record guarantees from Phases 16–22. Treat `state_snapshot`, node summaries, and existing audit metadata as untrusted at the read boundary anyway; a second allowlist is mandatory.
- The trace must be useful without becoming a data-exfiltration route. Do not return an ORM `.model_dump()`, raw JSONB, an `AgentMessage`, prompt content, source excerpt, or model/tool payload merely because the data is already in PostgreSQL.
- Tool invocation persistence is a real gap in the current baseline. Keep its schema and core port minimal, metadata-only, and graph-context-bound. Do not use this as justification for shipping real integrations, generic tools, LangChain agents, or a new telemetry service.
- Make the two read policies explicit and test them separately: tenant-wide audit inspection is audit-role limited, while a safe per-run trace preserves case-read explainability. Neither policy may grant a mutation or bypass document/source governance.
- Historical rows may lack optional accounting, node data, model records, or tool calls. The UI/API must represent unavailable/not-recorded values honestly and must not backfill or infer them from raw content.
- Filtering can become a large-table hot path later. Add only evidence-based composite indexes and bounded pagination now; aggregation/retention/metrics work belongs to Phase 27.
- Preserve the dirty Phase 22 worktree changes and do not alter approval behavior to add prettier traces. Use synthetic fixtures and deterministic/local providers only; never write secrets or real personal data to tests, docs, logs, screenshots, or trace records.
