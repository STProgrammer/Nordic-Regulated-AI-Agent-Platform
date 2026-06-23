# Phase 14 — Evidence Panel and Document UI

## Phase objective

Turn the secure document and retrieval capabilities completed in Phases 10–13
into a usable, localized Case Detail experience. An authorized user must be
able to:

1. see the documents attached to a case and open their safe metadata detail;
2. understand parsing, indexing, source-governance, and confidentiality state;
3. change only the document source status when their backend-enforced role
   permits it;
4. request a permitted re-index when the existing Phase 12 lifecycle allows it;
5. search the Phase 13 governed retrieval service from the case; and
6. inspect a bounded, authorized source context from an evidence result.

The Evidence Panel renders returned sources—not AI answers. It shows a source
title, file type, page or section, deterministic rank signal, bounded excerpt,
source-status warning, and a display-only source label. It must never present a
rank as confidence, imply that an AI answer was verified, expose a raw document,
or bypass backend authorization.

```text
Phase 10–12                        Phase 13                 Phase 14
private document → parsed/indexed  governed source search →  document UI +
metadata/chunks                    (no UI, no answer)        Evidence Panel/context
```

## How this phase fits the final product

The PRD requires document metadata/status visibility and an Evidence Panel so a
case worker or reviewer can understand the source material behind future AI
work. The current Case Detail correctly contains honest placeholders for
Documents and Evidence. This phase replaces those two placeholders with real
data from the completed document and retrieval boundaries; Extracted Fields,
Workflow, Risk, Approval, and Audit Timeline remain visibly unavailable until
their owning phases.

Phase 14 is deliberately the last user-interface layer before RAG answering:

| Completed input | Phase 14 consumes | Later phase still owns |
| --- | --- | --- |
| Phase 10 upload/storage | Safe document metadata and source/confidentiality labels | Browser upload form, download, preview, deletion, and object-storage access |
| Phase 11 parsing | Parsing status, language, page count, safe error and reprocess state | New parsing behaviour or parser controls |
| Phase 12 indexing | Indexing status/error/time and existing re-index operation | Chunking, embeddings, index policy, or worker behaviour |
| Phase 13 retrieval | Ranked, bounded, governed source results and warnings | Answering, verified answer citations, refusal, evidence sufficiency, reranking, and stored AI evidence |
| Phase 15 RAG | None in this phase | Model prompts/answers, citation validation, unsupported-claim checks, model usage and costs |
| Phase 18 Evidence Graph | None in this phase | Query planning, reranking, contradictions, evidence package persistence, and workflow routing |

## Relevant context and architectural constraints

- Roadmap Phase 14 requires document list/detail, parsing-status display,
  source-status controls, confidentiality display, re-indexing controls, an
  Evidence Panel, safe source-context opening, and frontend/API tests for
  display, governance actions, rendering, and access restrictions.
- PRD `FR-DOC-002` requires safe parsing metadata; `FR-DOC-003` requires
  re-indexing; `FR-DOC-004` requires approved/draft/deprecated/restricted/
  archived source governance. `FR-UI-002` and `FR-UI-003` require users to
  inspect documents and cited-source context. `FR-RAG-001`–`003` reserve answer
  citation verification and refusal behaviour for later work.
- Architecture §§4.1, 6.1–6.5, 9, 10.2, 11, 13, and 17 require Next.js,
  TypeScript, next-intl, TanStack Query, Zod, FastAPI/Pydantic/OpenAPI,
  backend RBAC and tenant scoping, PostgreSQL/pgvector, safe document handling,
  and unit/API/integration/frontend/E2E tests.
- The web app uses the Phase 7 same-origin `/api/...` rewrite and opaque
  HTTP-only `nordic_session` cookie with `credentials: 'include'`. Browser
  code must never read/store a session token, organization id, entitlement, or
  authorization decision. The API remains authoritative.
- Keep Norwegian Bokmål as the default and add complete English equivalents.
  Use the existing locale-safe formatting helpers and semantic, keyboard-safe
  components. No important condition may be conveyed by colour alone.
- Use only synthetic, public, anonymized, or otherwise safe test/manual data.
  Do not commit raw document content, object keys, checksums, vectors, cookies,
  credentials, browser traces, screenshots, or service/provider error details.

## Existing baseline to extend

| Existing component | Phase 14 use |
| --- | --- |
| `apps/web/src/components/cases/case-detail.tsx` | Replace only Documents and Evidence placeholders with focused real feature sections; preserve Case metadata and all other future-phase placeholders. |
| `apps/web/src/lib/api/contracts.ts` and `apiRequest` | Extend the existing Zod-safe same-origin client boundary; retain cookie handling, error envelopes, and safe `ApiFailure` mapping. |
| `apps/web/src/lib/cases/query.ts` | Follow its TanStack Query query-key, retry, invalidation, and detail-route patterns; put document/retrieval queries in focused feature modules. |
| `apps/web/messages/nb.json`, `apps/web/messages/en.json` | Replace stale Phase 14 placeholders and add equivalent document/evidence/context/action/error copy. |
| `apps/api/src/app/api/routes/documents.py` and `schemas/documents.py` | Extend the protected metadata surface with case-scoped listing, source-status mutation, and bounded context—not raw download or generic chunk APIs. |
| `apps/api/src/app/services/documents/service.py`, `db/repositories/document.py` | Keep routes thin; service owns policy, tenant/case/document relation checks, state transitions and audit coordination; repository owns parameterized persistence queries. |
| `apps/api/src/app/services/auth/policy.py` | Add the smallest explicit document governance/context actions and role matrices. Preserve all existing Phase 10–13 policies. |
| `apps/api/src/app/api/routes/retrieval.py`, `schemas/retrieval.py`, `services/retrieval/` | Consume the existing `POST /api/retrieval/search` contract unchanged. Do not add an answer endpoint or duplicate hybrid-search policy in the browser. |
| `apps/api/src/app/db/models/document.py` and existing migration | Reuse current document, document-text, and document-chunk state. No migration is expected. |

## In scope

### Document API and governance

- Add a protected, case-scoped document list operation:

  ```text
  GET /api/documents?case_id={uuid}&limit={1..100}&offset={>=0}
  ```

  It returns the standard envelope with stable pagination and safe document
  metadata only. The service must validate the readable current-tenant case,
  then return only active current-tenant documents attached to that exact case.
  It must not become an organization-wide document directory.
- Reuse `GET /api/documents/{document_id}` as the safe document-detail source.
  The UI may fetch it on selection/expansion but must not assume list metadata
  is current after a mutation.
- Add one narrow governance operation:

  ```text
  PATCH /api/documents/{document_id}/source-status
  ```

  Its sole writable field is a closed `source_status` enum. It must not accept
  title, filename, case/user/organization IDs, parsing/indexing lifecycle,
  confidentiality, archive timestamp, storage data, checksum, text, chunks,
  embeddings, or arbitrary metadata.
- Define `DocumentAction.UPDATE_SOURCE_STATUS` for Admin and Compliance
  Reviewer only. A source-status change is an operational governance action;
  Case Worker, Manager, and Read-only Auditor must receive `403`. Browser role
  affordances may hide/disable the control but never enforce the rule.
- Preserve the important distinction between source status `archived` and
  physical document archival. Setting `source_status=archived` changes only the
  retrieval-governance label; it must not set `documents.archived_at`, delete a
  blob/text/chunk, or make a physically archived document readable.
- Append one minimal `document.source_status_updated` audit event only after a
  successful update in the same transaction. It may contain the previous and
  new status, actor/organization/case/document references, and no title,
  filename, content, chunk id, checksum, storage key, vector, credentials, or
  raw exception text.
- Reuse the existing `POST /api/documents/{document_id}/reindex` endpoint and
  Phase 12 state guards. The UI must offer it only as an intent/action for
  documents parsed and not already pending/indexing; the API decides validity
  and retains its existing Admin/Case Worker/Manager policy. Do not alter worker
  dispatch, embeddings, queues, chunking, or index lifecycle semantics.

### Safe source-context API

- Add a purpose-specific, read-only source-context operation, for example:

  ```text
  GET /api/documents/{document_id}/context?chunk_id={uuid}
  ```

  The exact path may use the Documents route convention, but it must remain a
  bounded context endpoint rather than a document/chunk dump.
- Require the context document and chunk to belong to the current tenant and to
  each other. Enforce `RetrievalAction.SEARCH` plus the same source-status and
  restricted-confidentiality entitlement rules as Phase 13 before any context
  text is loaded. Consequently, Read-only Auditor cannot use document metadata
  read access to obtain source content; restricted/archived source context is
  allowed only under the explicit Phase 13 policy conditions.
- Return only a fixed server-bounded window for the selected permitted chunk
  (and, if genuinely needed for readable context, a fixed bounded adjacent
  window from the same document). Include document/chunk identity, title/file
  type, source status, page/section, display context text, and a truncation
  indicator. Do not return raw blobs, `DocumentText`, a full document, all
  chunks, offsets, parser metadata, embeddings, checksums, object keys,
  storage URLs, provider data, task ids, or a client-configurable byte range.
- If a context-view audit is added, write a successful, content-free
  `document.source_context_viewed` event linked to the document/case with no
  chunk id or text in event data. List/detail metadata reads remain non-audited
  as established by Phase 11. Do not add `retrieved_sources`, workflow,
  agent-message, model-usage, evaluation, risk, or approval rows.

### Frontend document and evidence experience

- Add a localized Documents section to Case Detail with loading, empty, safe
  unavailable/error, and paginated states. Each row/card shows title, file type,
  safe filename where permitted by the API, size, language/page count when
  known, parsing status/error summary, indexing status/error summary/indexed
  time, source status, confidentiality level, and update time. Use text labels
  and semantic badges in addition to colour.
- Add a document metadata detail view (an accessible expandable region, dialog,
  or a focused nested route selected by implementation) that uses the existing
  safe detail endpoint. It must disclose metadata and lifecycle state only, not
  offer blob download, browser preview, text extraction, checksum, or storage
  details.
- Add a source-status control for authorized governance roles. It must have a
  visible label/help text, confirm the selected status, report in-progress and
  safe failure states, invalidate document queries on success, and explain that
  `archived` is a source-governance label rather than physical deletion.
- Add a re-index control for the existing policy/state contract. It should be
  unavailable with a localized explanation when parsing is not complete or
  indexing is active, prevent duplicate submission, invalidate/refetch metadata
  after a successful `202`, and show only the safe returned lifecycle state.
- Add a localized Evidence Panel to Case Detail. It contains a bounded query
  form and calls the existing `POST /api/retrieval/search` with the current
  case id, approved-only scope by default, and a bounded result limit. It never
  calls a model or displays an answer.
- Let an operational user deliberately narrow an Evidence Panel search to one
  currently listed document. When selected, derive that document's source
  status from the safe API metadata and pass both the document id and status to
  the existing retrieval API. Restricted/archived source selection may be
  offered only to the known eligible role affordance, but the backend must still
  recheck all Phase 13 policy. This small opt-in path makes governed warning
  rendering usable without adding a broad client-owned entitlement system.
- Render each returned evidence card with the exact typed Phase 13 fields:
  source title, document type, page/section when present, one-based rank,
  rank-score explanation (ranking signal, **not** confidence), retrieval
  methods, bounded excerpt, source status, and warning codes. Map warnings to
  clear Bokmål/English text and never infer a warning from a client-side status
  guess.
- Construct a deterministic **display-only source label** from the already safe
  title/type/page/section fields (for example, document title plus page/section)
  and show it beside the result. It is a navigation/reference label for this
  panel, not a persisted citation and not evidence that an answer claim has
  been verified. Phase 15 remains the owner of answer citation formatting and
  validation.
- Provide an “open source context” action on every returned evidence result.
  Fetch the bounded context endpoint only after the user invokes it; render it
  in an accessible dialog or named detail region with focus management, close
  control, loading/error states, and a visible truncation notice. Do not fetch
  all context eagerly or cache raw context indefinitely in browser storage.
- Preserve the Case Detail route's UUID validation, protected-page behavior,
  locale-preserving navigation, standard safe error mapping, and remaining
  placeholders for Fields, Workflow, Risk, Approval, and Audit.

## Out of scope

- A browser document-upload form, drag-and-drop, download, preview, public/SAS
  links, raw blob delivery, deletion, physical archival, retention cleanup,
  document editing, checksum display, or generic text/chunk browser.
- New document parsing/reprocessing UX, parser changes, malware scanning,
  storage-provider changes, worker/queue/reconciliation changes, chunking,
  embeddings, re-index implementation, pgvector/GIN changes, or migrations
  unless a concrete existing-schema defect makes the scoped contract impossible.
- Changing source confidentiality, introducing per-document ACLs, a client
  source-status policy, an organization-wide document search/directory, or any
  way for document metadata read access to bypass retrieval/content policy.
- RAG/model answers, answer citation verification, claim validation, refusal,
  evidence sufficiency, contradiction detection, reranking, query rewriting
  changes, stored `retrieved_sources`, workflow runs, LangGraph, prompt/model
  provider work, model usage/cost, extraction, risk, approval, trace, audit
  viewer, or evaluation features.
- Replacing the existing Phase 13 retrieval contract, persisting a UI search as
  workflow evidence, accepting browser-controlled organization ids/vectors/
  scores/SQL, or displaying a rank score as a confidence score.
- Changes to `specs/roadmap.md` or `specs/progress.md` during planning. The
  implementation agent may update them only after all validation passes.

## API and authorization contract

### Document list and detail

The list request accepts only `case_id`, bounded `limit`, and non-negative
`offset`; use the established stable pagination shape. Every returned document
is attached to the readable active case in the authenticated organization. A
foreign, archived, or missing case/document remains tenant-safe `404`. The
response reuses a deliberate safe summary/detail type with no ORM serialization
or storage/raw-content fields.

`DocumentAction.READ` continues to allow Admin, Compliance Reviewer, Case
Worker, Manager, and Read-only Auditor to inspect metadata. That permission
does not imply source-text/retrieval access.

### Source-status mutation

The request is exactly:

| Field | Rule |
| --- | --- |
| `source_status` | Required closed enum: `approved`, `draft`, `deprecated`, `restricted`, or `archived`. |

The server derives the current tenant, actor, document/case, previous value,
and audit references. It should be idempotent for a no-op update or reject it
with the project’s established validation convention; choose one documented
behaviour and test it. A successful mutation must be fully durable with its
audit event or not reported as successful. It must not enqueue parsing/indexing
or alter physical archival.

### Context policy

The context endpoint takes only the selected `chunk_id`; no limits, offsets,
document ids beyond the path, lifecycle values, status filters, or raw queries
come from the browser. The service must load the trusted document and resolve
the equivalent explicit Phase 13 source scope for its persisted source status
and document id. It must also enforce active physical-document, parsed/indexed
current-evidence and restricted-confidentiality checks. Missing, foreign,
mismatched, archived, not-ready, or unauthorized document/chunk combinations
must not disclose which predicate failed.

Expected safe outcomes are `401` for no session, `403` for a role/source
entitlement denial, tenant-safe `404` for unavailable case/document/chunk,
`422` for malformed input, `409` only for an existing documented conflicting
mutation state, and neutral `503` for operational storage/database failures.
An empty Evidence Panel search remains a valid `200` result, not an error.

## Likely files, folders, modules, and services affected

| Area | Expected change |
| --- | --- |
| `apps/api/src/app/api/schemas/documents.py` | Add strict list/page, source-status-update, and bounded source-context schemas; preserve safe metadata enums. |
| `apps/api/src/app/api/routes/documents.py` | Add only protected list, narrow status mutation, and bounded context operations; update truthful OpenAPI descriptions/errors. |
| `apps/api/src/app/services/auth/policy.py` | Add explicit governance/context policy actions and tested least-privilege role matrices. |
| `apps/api/src/app/services/documents/service.py` | Add principal-aware case listing, status-update transaction/audit, and context coordination; retain thin routes. |
| `apps/api/src/app/db/repositories/document.py` | Add tenant/case-scoped pagination and a minimal document/chunk context projection with mandatory predicates and parameter binding. |
| `apps/api/src/app/services/audit/service.py` | Reuse the established allowlisted event API; add no separate audit system. |
| `apps/api/tests/unit/test_auth_policy.py`, document tests | Cover role, lifecycle, serializer/redaction, source-status and context-policy behaviour. |
| `apps/api/tests/integration/` | Cover tenant/case/document/chunk joins, transaction/audit, source/confidentiality/lifecycle filters, and pagination against PostgreSQL. |
| `apps/api/tests/api/test_documents.py`, `test_openapi.py`, `test_router_registry.py` | Cover cookie auth, safe contract/error behaviour, redaction, role restrictions, and exact OpenAPI surface. |
| `apps/web/src/lib/api/contracts.ts` | Add Zod document, document-page, source-context, retrieval-result/request, and narrow mutation schemas/types. |
| `apps/web/src/lib/api/documents.ts`, `lib/documents/query.ts` | Add credentialed typed client functions, query-key factories, retry rules, and mutations without a second HTTP client/state store. |
| `apps/web/src/lib/api/retrieval.ts`, `lib/retrieval/query.ts` | Add a focused typed consumer of the already implemented search endpoint; do not change backend retrieval semantics. |
| `apps/web/src/components/documents/` | Add document list/detail, lifecycle/governance controls, safe action feedback, and source-context presentation components. |
| `apps/web/src/components/evidence/` | Add evidence search/form, result card, warning, display-label, and context-opening components. |
| `apps/web/src/components/cases/case-detail.tsx` | Compose the two completed sections into Case Detail and retain remaining future placeholders. |
| `apps/web/messages/nb.json`, `apps/web/messages/en.json` | Add complete equivalent UI copy, warning/error/status/action/help text. |
| `apps/web/src/tests/unit/`, `apps/web/e2e/` | Add focused API/client/component and browser coverage for this phase. |
| `README.md`, `apps/web/README.md`, `docs/development.md` | Update only verified, user-facing document/evidence status and synthetic local validation instructions after implementation. |

## Implementation tasks

1. **Freeze the safe document/evidence contracts.**

   - Inspect the live Phase 10–13 models, policies, routes, standard envelopes,
     async transaction convention, and web-client patterns before editing.
   - Define Pydantic/Zod schemas from the API source of truth. Mark every model
     `extra="forbid"` or otherwise reject system-owned fields at the API
     boundary. Keep page values bounded and stable.
   - Write OpenAPI descriptions that make metadata-only, bounded context, and
     no-answer/no-download constraints unambiguous.

2. **Implement document list and detail composition without exposing storage.**

   - Add a case-scoped repository query with organization, exact case,
     non-physical-archive, allowed sorting, deterministic tie-breaking, and
     stable pagination. The service validates the case after `CaseAction.READ`
     and `DocumentAction.READ` before querying.
   - Reuse the existing document-detail operation and explicit safe serializer.
     Do not return `DocumentText`, object/storage values, checksum, raw chunks,
     parser metadata, or worker/provider values in either list/detail response.
   - Build a responsive document list/detail UI with semantic headings, status
     text, locale-safe timestamps/sizes, labels, loading/empty/failure states,
     and no fabricated document content.

3. **Add source-status governance and re-index intent.**

   - Add the narrow status-update command, Admin/Compliance Reviewer policy,
     repository update, and atomic content-free audit event. Keep status change
     separate from physical archive and re-index lifecycle.
   - Add a controlled UI mutation with current value, explicit status label,
     pending/disabled state, safe response/error handling, and query
     invalidation. Use role data only to improve affordance; rely on API `403`
     for enforcement.
   - Consume the existing re-index endpoint from an authorized control and
     render Phase 12 lifecycle status precisely. Do not duplicate re-index
     state transitions or dispatch work from the browser.

4. **Implement bounded, governed source context.**

   - Add a repository projection that joins only the selected document/chunk
     under tenant, document relationship, physical archive, parsing/indexing,
     source-status, confidentiality, and chunk-identity predicates. Use bound
     parameters and a server-configured hard context limit.
   - Add service-level retrieval/source policy reuse before loading text. Make
     all denied/missing/mismatched states tenant-safe and never fall back to an
     unfiltered document/chunk query.
   - Return a small typed context view and, if auditing the content-view action,
     append only an allowlisted, content-free audit event after successful
     access. Document exactly what is bounded and deliberately absent.

5. **Build the Evidence Panel on Phase 13, not beside it.**

   - Add a bounded search form associated with the current case and typed
     retrieval client/query mutation. Default to approved sources; make the
     selected-document opt-in explicit and derive status/id from API-read
     metadata, not user-typed identifiers.
   - Show a truthful evidence result card and source warnings from server output.
     Explain ranks and retrieval methods in user language without calling them
     confidence, risk, verification, or an answer.
   - Generate only a presentational source label, then add the lazy safe-context
     interaction with keyboard/focus/error/truncation handling. Do not persist
     query/context state in local/session storage or prefetch all text.

6. **Localize, document, and test the complete phase.**

   - Complete both language catalogues; remove only the now-stale Documents and
     Evidence placeholder copy. Retain all other phase-owned placeholders.
   - Update documentation only after implementation and verification prove the
     endpoints/screens/commands. Clearly state that source context is bounded
     and that answer generation/citation verification has not started.
   - Add the required backend, frontend and browser tests below. Keep all
     fixtures synthetic and stop/repair any failing check before marking the
     phase complete.

## Required tests

### Backend unit tests

- Document policy matrix: metadata list/detail roles; Admin/Compliance Reviewer
  source-status update allowed; Case Worker/Manager/Read-only Auditor denied;
  context requires the Phase 13 retrieval role and restricted entitlement.
- Schema validation: malformed IDs, invalid/extra source-status payload fields,
  page bounds, no caller-owned tenant/case/user/archive/indexing/storage/raw
  fields, and closed enum coverage.
- Status-update service: no-op convention, every allowed status transition,
  physical archive preservation, no parser/indexer dispatch, atomic
  success-only audit shape, and safe operational failure.
- Context policy/result shaping: same-document chunk relation, current
  parse/index requirement, all five source statuses, restricted confidentiality,
  physical archive, fixed text bound/truncation, and absence of forbidden raw
  document, metadata, storage, vector, offset, task, provider, and secret data.
- UI-independent source display-label/warning helpers: page/section fallbacks,
  rank wording not-confidence, and complete warning mapping.

### Backend integration and API/OpenAPI tests

- PostgreSQL list pagination/filtering proves current-tenant, exact-case,
  physically active document-only behaviour, stable order, safe page metadata,
  and tenant-safe foreign/missing/archived case/document responses.
- Source-status update proves the correct document only changes, `archived_at`
  remains unchanged, retrieval visibility follows the persisted status, and one
  minimal audit row is committed only with the update.
- Context tests prove a permitted same-tenant indexed chunk returns only bounded
  context; foreign/mismatched chunk ids, stale/not-ready state, physical archive,
  unsupported role, restricted confidentiality, and restricted/archived source
  policy never leak text or predicate detail.
- API tests cover cookie authentication, all role outcomes, validation errors,
  list/detail/state responses, re-index regression, neutral failures, standard
  envelopes, and redaction. Verify `GET /api/documents/{id}/chunks`, download,
  preview, answer, and unrestricted-context operations do not appear.
- Router/OpenAPI tests assert the new operations, cookie security, request and
  safe error schemas/descriptions, and no accidental generic `PATCH` surface.

### Frontend unit/component tests

- Zod/API-client tests validate document list/detail, status mutation, bounded
  context, retrieval request/results, malformed envelopes, relative paths, and
  credentials inclusion without exposing unsafe values.
- Document UI tests cover Bokmål default and English copy, loading/empty/error,
  lifecycle/status/confidentiality display, selected detail, audit-governed
  status-action affordances, re-index pending/success/conflict/error, and cache
  invalidation/refetch.
- Evidence tests cover bounded query validation, approved default, selected
  document scope, result fields, no-result state, rank explanation, all warning
  copy, display-label fallbacks, and confirmation that no answer/citation-
  verification language is rendered.
- Context interaction tests cover lazy request, metadata/text redaction,
  truncation notice, dialog/region semantics, Escape/close/focus return,
  loading/safe failure, and forbidden-role response handling.
- Case Detail regression tests confirm Documents/Evidence are no longer
  placeholders while Fields/Workflow/Risk/Approval/Audit remain honest
  placeholders; existing login, shell, locale and Case workflow tests remain
  green.

### Browser and manual tests

- Extend the existing Playwright local-stack scenario using a synthetic
  authenticated setup that adds/uses one case and one indexed safe document
  through existing API/setup boundaries (not a new browser upload feature).
  Verify the Bokmål Case Detail document display, permitted re-index intent,
  approved-source evidence search, card rendering, and bounded context opening.
- Add one authorization scenario proving an Auditor can see only permitted
  metadata but cannot search evidence/open context/change source status, and a
  non-privileged operational user cannot change source status or inspect a
  restricted source. Do not record trace/video/screenshot artifacts containing
  source text in normal runs.
- Manually repeat the important path in Bokmål and English: use only a synthetic
  case/document, inspect metadata, change source status as an authorized user,
  request re-index where eligible, search approved evidence, open/close bounded
  context, and confirm safe rejection for restricted roles. Do not print a
  cookie, password, object key, raw document body, or provider credential.

## Validation steps

Run from repository root after implementation. Do not mark the phase complete
if any required check fails.

1. Verify locked dependencies and configuration without displaying environment
   values:

   ```bash
   pnpm install --frozen-lockfile
   uv sync --all-packages --locked
   uv lock --check
   docker compose --env-file .env.example config --quiet
   ```

2. Run focused tests, then all backend and web regressions:

   ```bash
   uv run pytest apps/api/tests/unit -k 'document or retrieval or policy'
   uv run pytest apps/api/tests/integration -k 'document or retrieval'
   uv run pytest apps/api/tests/api -k 'document or retrieval or openapi'
   pnpm test:api
   pnpm test:web
   ```

3. Run workspace quality gates and a production web build:

   ```bash
   pnpm check:workspace
   pnpm format:check
   pnpm lint
   pnpm typecheck
   pnpm --filter @nordic-regulated-ai-agent-platform/web build
   ```

4. Run the local stack and migration/health proof. Use an ephemeral synthetic
   local password only through the existing documented environment mechanism:

   ```bash
   pnpm dev:up
   docker compose --env-file .env.example exec -T api uv run alembic -c apps/api/alembic.ini upgrade head
   pnpm verify:local-stack
   pnpm test:e2e
   ```

5. Perform the manual role and localization checks above. Confirm the API docs
   expose only safe document metadata, status mutation, bounded context, and
   retrieval search; no answer/download/raw chunk API is present.

6. Stop the stack and inspect the worktree:

   ```bash
   pnpm dev:down
   git diff --check
   git status --short
   ```

## Completion criteria

- Case Detail contains accessible, localized real Document and Evidence sections
  backed by typed, credentialed same-origin APIs; all other future capability
  placeholders remain truthful.
- A document list/detail exposes only safe current-tenant case metadata and
  lifecycle/source/confidentiality state, with stable pagination and no storage
  or raw-content leakage.
- Only Admin and Compliance Reviewer can change a document’s closed source
  status, every success is audited safely, and source-status `archived` never
  causes physical archival/deletion. Re-index uses the existing Phase 12 API
  state/policy exactly.
- Evidence search is delegated entirely to Phase 13’s governed retrieval
  endpoint, defaulting to approved sources; it renders truthful results/warnings
  and never produces an answer or calls a model.
- Opening source context is explicit, bounded, tenant/status/confidentiality/
  lifecycle governed, role-restricted like retrieval, and never exposes raw
  files, full text, storage metadata, vectors, or provider data.
- API, integration, unit, frontend, E2E, localization, OpenAPI, format, lint,
  type, build, local-stack, manual role, and manual locale checks pass using
  synthetic data only.
- Documentation accurately describes what is present and what remains for
  Phases 15–23. Only then may the implementation agent mark Phase 14 `(DONE)`
  in `specs/roadmap.md` and update `specs/progress.md` consistently.

## Risks, dependencies, and assumptions

| Risk, dependency, or assumption | Required mitigation |
| --- | --- |
| Phase 13 results deliberately lack a final citation label | Build only a clearly labelled presentational source reference from returned safe fields; defer answer citation semantics/validation to Phase 15. |
| Document metadata read is broader than retrieval access | Context must reuse retrieval/source-entitlement checks; Auditor metadata access must never become text access. |
| `source_status=archived` could be confused with `archived_at` | Keep mutation narrow, document the distinction in UI/API, and test both states independently. |
| Existing chunks can be stale during re-indexing | Context must require the same current parsed/indexed lifecycle boundary as retrieval; chunk presence alone is insufficient. |
| A context feature can turn into raw document browsing | Fixed server limits, selected chunk only, no client range, lazy fetch, and a redaction test suite prevent scope drift. |
| Frontend role data can be stale or manipulated | Treat it only as an affordance; every read/mutation/content operation is enforced by backend policy. |
| Retrieval scores may be mistaken for truth/confidence | Explain score/rank as deterministic ordering only and do not display confidence, sufficiency, risk, or answer-verification claims. |
| Current worktree has uncommitted earlier-phase changes | Preserve every existing change, avoid destructive Git operations, and modify only `phases/phase14.md` in G mode. |
| Existing Phase 12/13 configuration is a prerequisite for real local evidence search | Reuse it exactly; do not add a hidden fallback provider or weaken query/source governance to make the UI demo work. |

## Notes for the implementation agent

- Read this plan first, then inspect the actual Phase 10–13 document/retrieval
  schemas, policies, repository/service transaction patterns, web API client,
  Case Detail, i18n catalogues, and tests before editing.
- Keep FastAPI routes transport-only; repositories own bound persistence
  queries; services own principal/case/source policy, state/audit coordination;
  Pydantic/Zod own contract validation; components own presentation and safe
  interaction. Never move authorization or organization scoping into React.
- Reuse `POST /api/retrieval/search` verbatim for Evidence Panel search. Do not
  fork its rewriter, candidate SQL, source status policy, audit semantics, or
  rank fusion merely for a UI convenience.
- The UI has no upload flow in this phase. Use existing synthetic setup/API
  paths for browser tests and manual validation; do not add an attractive but
  out-of-scope file chooser.
- Treat source context as sensitive content. Keep it bounded, on-demand,
  non-persistent in the browser, and absent from console output, normal test
  artifacts, audit payloads, logging, and documentation examples.
- Do not alter the roadmap/progress during planning. Do not declare the phase
  complete until every required validation and manual check passes.
