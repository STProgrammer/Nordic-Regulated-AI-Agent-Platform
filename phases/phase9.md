# Phase 9 — Case Management UI

## Phase objective

Replace the authenticated Case Inbox placeholder with a production-quality,
localized Case Management interface. An authorized user must be able to submit
a case, find cases through a server-backed inbox, open a case detail view, and
understand the current case metadata and lifecycle state. The UI must use the
existing protected Phase 8 Case API through the Phase 7 typed same-origin
client, preserve opaque-cookie session handling, and remain usable with a
keyboard in Norwegian Bokmål by default.

This phase delivers the first real end-user workflow: **log in → submit a
synthetic case → find it in the inbox → open its detail page**. It deliberately
does not pretend that documents, AI workflow results, evidence, risk decisions,
approvals, or audit-read data exist before their owning phases.

## How this phase fits the final product

Cases are the durable business records to which later document ingestion,
retrieval, LangGraph workflow runs, extraction results, risk assessments,
human approvals, audit traces, and evaluations attach. Phases 6–8 established
the authorization boundary, localized web shell, and tenant-safe Case API.
This phase makes that completed backend capability usable without moving
business policy, tenant checks, or session handling into the browser.

The Case Detail layout is intentionally introduced now because it is the
stable future home for the document UI (Phase 14), evidence results (Phases
14/18), extracted fields (Phase 19), drafts (Phase 20), risk findings (Phase
21), approvals (Phase 22), and trace/audit data (Phase 23). Each unavailable
area must be labelled as unavailable rather than represented with fabricated
data.

## Relevant specification context and constraints

- Roadmap Phase 9 requires a Case Inbox with filters for status, risk level,
  assignee, domain, and priority; a Case Detail view with the specified
  metadata and future-data placeholders; accessible forms, errors, loading,
  and empty states in Bokmål; and frontend plus Playwright coverage for login,
  submission, list, and detail navigation.
- PRD `FR-CASE-001` requires title, description, domain pack, priority,
  language, optional due date, optional external reference, validation,
  Norwegian date presentation, a unique server-owned case number, and inbox
  visibility. File attachments start in Phase 10, not in this form.
- PRD `FR-CASE-002` requires the inbox to show case number, title, status,
  risk level, priority, assigned user, due date, last update time, and workflow
  state; it also requires text search and the listed filters. The current
  backend has no workflow result yet, so the workflow column must truthfully
  state that workflow processing has not started/is unavailable in this phase.
- PRD `FR-UI-001`, `FR-UI-002`, and `FR-UI-005` require Bokmål by default,
  English as an option, localized date/number display, semantic HTML, labels,
  keyboard navigation, readable contrast, clear errors, and non-colour-only
  state communication.
- Architecture §§4.1, 6.1, 11.1–11.2, 13, 17.4–17.5, and 18.2 require a
  strict-TypeScript Next.js frontend using TanStack Query, React Hook Form,
  Zod, next-intl, Vitest/Testing Library, and Playwright; the browser may not
  own business-critical authorization or tenant enforcement.
- Architecture §10.2 defines a case as tenant-scoped and identifies the
  persisted fields that are currently available. It does not yet contain
  workflow output, documents, evidence, extraction, risk-assessment, approval,
  or audit-read relationships for this page to consume.
- All case reads and writes stay behind the Phase 6 opaque HTTP-only session
  cookie. The web app must use relative `/api/...` requests with
  `credentials: 'include'`; it must never read, store, decode, or manufacture a
  session ID.
- The API continues to enforce authorization and organization isolation. UI
  affordances may improve clarity for the current role but are never an
  authorization mechanism.
- Only synthetic, public, anonymized, or otherwise safe demo text is allowed
  in tests, screenshots, fixtures, manual verification, and documentation.

## Existing baseline to extend

Build on the current Phase 7/8 implementation. Do not create a parallel web
application, a second API client, or frontend-only case state.

| Existing component | Phase 9 use |
| --- | --- |
| `apps/web/src/app/[locale]/cases/page.tsx` | Replace the honest Phase 7 placeholder with the protected Case Inbox route. |
| `apps/web/src/components/auth/protected-page.tsx` | Continue to resolve the session, redirect only 401/403 responses safely, and render the shared shell. |
| `apps/web/src/components/layout/application-shell.tsx` | Keep the app landmarks, skip link, navigation, account display, language switcher, and logout behavior. Make the Cases navigation item active for `/cases`, `/cases/new`, and `/cases/[caseId]`. |
| `apps/web/src/lib/api/contracts.ts` | Extend the shared Zod contract boundary with Case API schemas and typed safe API failures. Preserve the success/error envelope parser. |
| `apps/web/src/lib/api/auth.ts` and `apps/web/src/lib/auth/query.ts` | Preserve the established same-origin API and TanStack Query patterns; add a focused Case API/query module rather than mixing Case calls into auth. |
| `apps/web/src/lib/formatting/index.ts` | Reuse locale-safe formatting; add carefully typed helpers only where ISO API dates/timestamps need parsing before formatting. Do not parse date-only values through a timezone-shifting `Date` constructor. |
| `apps/web/messages/nb.json`, `apps/web/messages/en.json` | Add complete Case Management copy. Bokmål is the default, but all new visible text must be translated in both catalogues. |
| `apps/api/src/app/api/routes/cases.py` and `schemas/cases.py` | These already expose the protected Phase 8 Case surface. Frontend contracts must match this source of truth exactly. |
| `apps/api/src/app/services/auth/policy.py` | Remains the authority for who may submit, read, edit, archive, or move case lifecycle states. Do not duplicate this matrix in the UI. |

### Existing Case API contract

Consume only typed representations of the existing standard success envelope:

| Operation | Current purpose in Phase 9 |
| --- | --- |
| `GET /api/cases` | Server-side paginated inbox. Supports `status`, `risk_level`, `assigned_user_id`, `domain`, `priority`, `q`, `limit`, `offset`, allowlisted `sort`, and `direction`. The normal read excludes archived cases. |
| `POST /api/cases` | Submit a new case. Client input is limited to title, description, domain, priority, language, due date, and external reference. The server owns organization, submitter, case number, and initial `new` status. |
| `GET /api/cases/{case_id}` | Read the full safe Case Detail representation. |
| `PATCH /api/cases/{case_id}` | Exists from Phase 8 but is not a Phase 9 end-user operation unless a narrow requirement below explicitly requires it. |
| `POST /api/cases/{case_id}/archive` | Exists from Phase 8 but must not be surfaced as a Phase 9 archive control. |

Case enums are closed and must be mirrored as Zod schemas, not free-form
strings:

- status: `new`, `processing`, `waiting_for_human_review`,
  `needs_more_evidence`, `approved`, `rejected`, `completed`, `failed`,
  `archived`;
- priority: `low`, `normal`, `high`, `urgent`;
- domain: `public_sector`, `banking_compliance`, `energy_operations`,
  `internal_policy`;
- language: `nb`, `en`;
- risk level when supplied: `low`, `medium`, `high`, `critical`.

The list response intentionally omits case description and external reference;
the detail response contains them for an authorized case reader. UI code must
not work around that privacy boundary by caching form inputs, logging them, or
embedding them in URLs.

### Assignee presentation and filter dependency

Phase 8 stores and returns only `assigned_user_id`; `/api/users` is deliberately
Admin-only. A Case Worker or Read-only Auditor must not be forced to enter,
guess, or inspect opaque UUIDs merely to filter the inbox. Before implementing
the selector, make this narrow, phase-scoped API decision:

1. Add a Case-read-authorized, tenant-scoped read model only if the existing
   Case API cannot supply accessible, human-readable assignee choices. Its
   response may contain **only** `user_id` and `display_name` for distinct
   users assigned to visible, non-archived cases in the current organization.
   It must not expose email addresses, roles, passwords, inactive users, or a
   general-purpose user directory.
2. Expose it beneath the Cases boundary (for example,
   `GET /api/cases/assignees`) with the same Case `READ` policy and safe
   tenant-not-found behavior. Keep the query/repository/service separation,
   typed Pydantic/Zod schemas, pagination/bounds if needed, and API tests.
3. Enrich Case summary/detail views with the corresponding display name only
   when it can be resolved through the same tenant-scoped read model. Do not
   add client-side joins to `/api/users`, relax the Admin-only Users API, or
   expose identifiers of users who have no visible assigned case.

This is a deliberately minimal supporting read contract, not user management,
team modelling, assignment editing, or a new directory feature. If a current
Case API response already provides the safe choice/display data when the plan
is implemented, reuse it and do not add a redundant endpoint. The filter must
also retain an explicit **All assignees** option; an unassigned-case filter is
out of scope because Phase 8 has no typed unassigned-list filter.

## In scope

- A protected localized Case Inbox at `/{locale}/cases` backed by the Phase 8
  API, with server-backed text search, status/risk/assignee/domain/priority
  filters, deterministic pagination, and a clear-filters path.
- An accessible Case submission form at `/{locale}/cases/new`, or an
  equivalently routable focused page. It must create a case, preserve only safe
  field input until submission completes, invalidate/update relevant queries,
  and navigate to the returned Case Detail page.
- A protected dynamic Case Detail route at `/{locale}/cases/{caseId}` that
  displays real Phase 8 metadata/status and clearly labelled placeholders for
  unavailable future data.
- Typed Case API contracts, Case API calls, TanStack Query keys/hooks, and
  localized safe error mapping consistent with the existing auth client.
- Responsive, semantic, keyboard-operable UI with loading, empty, and failure
  states; Norwegian Bokmål default and complete English alternative.
- Focused reusable Case feature components and the smallest shared UI
  primitives necessary for a professional, consistent interface.
- Vitest/Testing Library coverage and a configured Playwright smoke test for
  the documented login → submit → inbox → detail path.
- The narrow assignee display/filter API read-model described above only if it
  is necessary to meet the roadmap without exposing a user directory.
- Truthful updates to user-facing Phase 7/8 documentation only where it says
  the Cases screen is still a placeholder or fails to explain how to run the
  new browser smoke test.

## Out of scope

- File selection, attachment persistence, upload, download, storage keys,
  document list/detail, parsing status, checksums, document classification, or
  source governance (Phases 10–14).
- Workflow execution, workflow progress, case classification, PII detection,
  prompt-injection handling, case-type mutation, model calls, or a real
  workflow-state result (Phases 16–17).
- Retrieval, citations, evidence rendering, source context, contradiction
  handling, or evidence actions (Phases 14, 15, and 18).
- Extracted fields, AI drafts, risk reasons/assessment results, approval queue
  operations, human edit tracking, workflow interruptions, trace viewers, and
  audit-event reads (Phases 19–23).
- Frontend controls for the Phase 8 PATCH lifecycle transitions, assignment,
  editing, archiving, approval/rejection, or self-approval rules. Those need a
  distinct interaction and review design; existence of an API route is not
  permission to expose it early.
- A manager/team data model, workload aggregation, broad user-directory
  access, arbitrary user search, or changes to the Admin-only Users API.
- Real personal data, browser persistence of case descriptions/references,
  session storage/token handling, frontend-only authorization, raw API error
  payload display, unbounded client filtering, or artificial case data.
- Future-phase document, retrieval, workflow, approval, audit, evaluation,
  security-hardening, CI, cloud, and deployment implementation.
- Marking Phase 9 as done in `specs/roadmap.md` or `specs/progress.md` during
  planning. The implementation agent may do so only after every required
  validation check has passed.

## Likely files, folders, modules, and services affected

| Area | Expected changes |
| --- | --- |
| `apps/web/src/app/[locale]/cases/page.tsx` | Replace the placeholder with the protected Case Inbox composition. |
| `apps/web/src/app/[locale]/cases/new/page.tsx` | Add a routable protected Case submission page with localized metadata. |
| `apps/web/src/app/[locale]/cases/[caseId]/page.tsx` | Add the protected Case Detail route and localized metadata. |
| `apps/web/src/components/cases/` | Add focused inbox, filter form, results table/list, pagination, submission form, metadata, status/risk badges, future-section placeholder, and safe-error components. Keep feature code out of layout/auth folders. |
| `apps/web/src/components/layout/application-shell.tsx` | Make Cases navigation active for nested Case routes; retain all existing landmarks and auth behavior. |
| `apps/web/src/components/ui/` | Extend only with small generic primitives genuinely reused by Case components (for example, labelled form field/error and badge). Do not introduce a second design system. |
| `apps/web/src/lib/api/contracts.ts` | Add exact Zod Case request, list, summary, detail, and optional assignee-option schemas/types. |
| `apps/web/src/lib/api/cases.ts` | Add a typed Case HTTP client using `apiRequest`, credentialed relative paths, URLSearchParams, and no unsafe string interpolation. |
| `apps/web/src/lib/cases/` or `apps/web/src/lib/case-query.ts` | Add typed enum labels, URL-filter parsing/serialization, query-key factories, and view-only formatting helpers. |
| `apps/web/src/lib/formatting/index.ts` | Add ISO calendar-date/timestamp formatting helpers if current helpers cannot safely distinguish date-only values from instants. |
| `apps/web/messages/nb.json`, `apps/web/messages/en.json` | Add fully equivalent Case, status, priority, domain, validation, loading, error, pagination, and future-placeholder translations. |
| `apps/web/src/tests/unit/` and `apps/web/src/tests/` | Add deterministic API-client, filter/query, inbox, submission, detail, localization, loading/error/empty, and navigation tests. |
| `apps/web/playwright.config.ts`, `apps/web/e2e/`, package manifests/scripts | Add the Playwright configuration and one smoke suite only as required by the roadmap; document/install its browser dependency through project scripts. |
| `apps/api/src/app/api/routes/cases.py`, schemas, services, repositories, and tests | Touch only if the narrow Case-assignee read model is required. Keep it protected, typed, tenant-safe, and thoroughly tested. |
| `README.md`, `apps/web/README.md`, `docs/development.md` | Update only stale Case-placeholder wording and add accurate local browser-smoke prerequisites/commands after implementation. |

## Implementation tasks

1. **Define the browser-side Case contract and query vocabulary.**

   - Translate the Phase 8 Pydantic response shapes into strict Zod schemas:
     `CaseSummary`, `CaseDetail`, `CaseList`, create input/result, and any
     approved assignee-option view. Validate UUIDs, nullable values, enum
     values, ISO calendar-date strings, and ISO timestamps before components
     receive data.
   - Define one typed filter object containing only API-supported values:
     `status`, `riskLevel`, `assignedUserId`, `domain`, `priority`, `query`,
     `limit`, `offset`, `sort`, and `direction`. Normalize blank search text to
     absence, enforce the backend page limits, and never send `undefined`, a
     malformed UUID, or a client-owned organization ID.
   - Build URLs with `URLSearchParams`; omit empty filters, keep query ordering
     deterministic for tests, and use the API's snake_case wire names only at
     the HTTP boundary.
   - Add Case-specific TanStack Query keys. Include the complete normalized
     query in list keys, use a case-ID key for detail, invalidate list queries
     after successful creation, and seed/invalidate the returned detail safely.
   - Preserve the current `ApiFailure` contract. Components receive typed
     failures and localized messages, never unvalidated `unknown` response
     data or a raw backend error message.

2. **Resolve the minimum assignee data needed for a professional filter.**

   - First inspect the live Phase 8 Case response and existing identities to
     confirm whether human-readable, tenant-safe assignee data already exists.
   - If it does not, implement only the small Case-scoped read model documented
     in the dependency section. It must use the existing request principal,
     Case `READ` authorization, tenant predicates, safe response envelope, and
     no audit write for reads.
   - The frontend selector uses the safe returned display names and IDs; it
     does not call `/api/users` as a non-admin, decode IDs, or show an opaque
     UUID to an end user. Keep **All assignees** as the reset state.
   - Test tenant isolation, role protection, archive exclusion, response
     minimization, Zod validation, and selected filter serialization. Do not
     add assignment mutation controls merely because the list can filter it.

3. **Implement Case Inbox list/search/filter behavior.**

   - Render the Case Inbox inside `ProtectedPage`, retaining the shared shell
     landmarks and the existing skip-link target. Use a single visible page
     heading and describe the result count/status to assistive technology.
   - Provide a primary **New case** action only for roles that may submit under
     current UI knowledge (Admin, Case Worker, Manager). For the Read-only
     Auditor and Compliance Reviewer, omit or disable the affordance with
     clear explanatory copy; the backend remains authoritative if a role
     changes between render and request.
   - Use a labelled search form for case number/title/description search and
     labelled controls for status, risk level, assignee, domain, and priority.
     Support Enter/submit, a visible apply action where needed, clear filters,
     and a no-results explanation that distinguishes an empty inbox from an
     active filter producing no results.
   - Reflect the normalized filter state and page offset in locale-preserving
     route search parameters so refresh, Back/Forward, copied internal links,
     and language switching retain the current inbox context. Do not put case
     content, error details, passwords, or session values in the URL.
   - Request each page from the server. Do not filter only the currently loaded
     page in memory, and do not claim a client-side count is the tenant-wide
     count. Use the returned `total`/`has_more` for accessible previous/next
     pagination, reset offset whenever filters/search change, and preserve a
     deterministic default sort supplied by the API.
   - Render responsive semantic data: a table with caption/headers on wide
     screens and an equivalent labelled list/card representation on narrow
     screens if needed. Each result must link by trusted `case_id` to its
     detail route and show real case number, title, status text, priority,
     risk (`not assessed` when null), assignee (`unassigned` when null), due
     date (`no due date` when null), last update, domain, and an explicit
     unavailable workflow-state label.
   - Status, priority, and risk indicators need textual labels in addition to
     any colour. Use the existing neutral visual language; do not imply a risk
     assessment where the API returns `null`.
   - Render a polite loading state during initial and filter changes, a safe
     retryable unavailable/error state for network/5xx/malformed responses,
     and safe role/not-found handling. A 401/403 must continue through the
     existing protected-route redirect rather than becoming a misleading
     empty-state message.

4. **Implement the accessible Case submission page.**

   - Add a dedicated `/{locale}/cases/new` route, retain the parent Cases
     navigation state, and include a breadcrumb/back link to the inbox.
   - Use React Hook Form with a client-side Zod form schema aligned to—not a
     replacement for—the Phase 8 request contract. Include title, description,
     domain, priority, language, optional due date, and optional external
     reference. Do not render attachments, case number, organization,
     submitter, risk, case type, workflow state, or any hidden system-owned
     field.
   - Use native labels and appropriate controls: text input for title,
     textarea for description, select/radio controls for closed enum values,
     `type="date"` for due date, and a clearly optional external-reference
     input. Associate hint/error text with controls using IDs and
     `aria-describedby`; focus the first invalid field after submit.
   - Use localized domain/priority/language labels. Default the form language
     to the active UI locale where it is a supported Case language, otherwise
     Bokmål; keep it a deliberate user-editable case property.
   - Trim/validate only for immediate UX feedback, submit the exact typed API
     shape, disable duplicate submission while pending, and offer a visible
     cancel action that never loses a submitted result. Do not persist draft
     descriptions in storage or URLs.
   - Map safe validation field locations to the corresponding localized input
     errors. Map safe API codes/statuses to localized general feedback and
     show a request ID only as a support reference when provided. Never render
     raw error bodies, request data, stack traces, or server messages.
   - On success, invalidate relevant Case lists and navigate to the returned
     `/{locale}/cases/{caseId}`. Announce success appropriately without
     exposing a hidden session or unsafe payload.

5. **Implement Case Detail and honest future capability placeholders.**

   - Add a dynamic `/{locale}/cases/{caseId}` protected route. Validate that
     route parameters are UUIDs before a request; malformed IDs should show a
     localized not-found/invalid-link state without calling a broad endpoint.
   - Fetch `GET /api/cases/{case_id}` through a dedicated query and render an
     accessible heading containing the case number/title. Include a back-to-
     inbox link that preserves safe filter query parameters when practical.
   - Display actual Phase 8 metadata with a definition list or equivalent
     semantic structure: case number, title, full description, status, domain,
     priority, case language, risk state, assignee, submitter identifier only
     when it has a safe product label, due date, external reference, created,
     and last-updated time. Do not make unknown IDs look like user names; use a
     neutral localized unavailable label until the narrow read model resolves a
     display name.
   - Use locale-safe date-only presentation for `due_date` and locale/timezone
     aware timestamp presentation for `inserted_at`/`updated_at`. Preserve ISO
     values only in machine-readable `time dateTime` attributes where useful;
     never silently shift a calendar due date by timezone.
   - Include visibly separate, semantic sections labelled Documents, Extracted
     fields, Evidence, Workflow, Risk/compliance, Approval, and Audit timeline.
     Each must say it is unavailable in the current product phase and name its
     owning future phase where that helps users. No fake documents, source
     citations, workflow runs, risk flags, approval controls, or audit events.
   - A current API `404` must render localized Case-not-found copy, including
     the safe fact that the case may be unavailable; it must not distinguish a
     foreign tenant, archived case, or non-existent UUID. Network/5xx/malformed
     response states need retry behavior consistent with the inbox.
   - Do not add edit, status-change, archive, or approval controls in this
     phase. Existing server-side lifecycle authorization stays intact for later
     dedicated interaction phases.

6. **Localize, format, and preserve accessibility throughout.**

   - Add coherent message namespaces for Case titles, fields, enum labels,
     filters, submit feedback, pagination, statuses, errors, empty/loading
     states, and future placeholders in both `nb.json` and `en.json`.
     Bokmål wording should be clear, public-sector/enterprise appropriate, and
     free of unexplained English technical jargon.
   - Make English messages equivalent in meaning, not merely partial fallback
     strings. Retain the route-preserving language switcher; when it changes
     locale on a Case route, preserve the case ID and safe inbox query string.
   - Extend date/time helpers with explicit ISO date-only versus instant input
     types. Test Norwegian and English output rather than relying on a machine
     locale default.
   - Preserve the skip link, `main` landmark, one top-level page heading,
     proper table/list semantics, form labels, visible focus indicators,
     keyboard-operable buttons/selects/links, logical tab order, and live
     status/error announcements. Do not use colour as the only status/risk
     signal or introduce auto-focusing that steals focus during ordinary data
     refreshes.

7. **Add deterministic frontend and browser verification.**

   - Extend Vitest/Testing Library tests using the established mocked auth,
     fetch, router, and `renderWithProviders` seams. The client tests must
     prove relative credentialed requests, valid contract parsing, malformed
     response rejection, safe error metadata, and query serialization without
     including a cookie or password literal.
   - Add component tests for Norwegian default labels, English rendering,
     current route navigation state, search/filter apply/reset, pagination,
     loading, empty, API failure/retry, safe 404, real metadata formatting,
     and honest future-section placeholders.
   - Add form tests for required fields, localized validation, keyboard submit,
     optional field handling, duplicate-submit prevention, field/general API
     errors, successful invalidation/navigation, and the absence of document
     upload or system-owned inputs.
   - Add the smallest practical Playwright setup at the web workspace/root
     convention. The smoke test must use a running local Compose stack and
     environment-provided synthetic credentials, log in through the UI, submit
     a uniquely named synthetic case, find it in the inbox, and open its detail
     route. Assertions must check visible Bokmål labels and safe user-facing
     data only.
   - Do not hard-code a password, session ID, access token, private URL, or
     personal data in a Playwright spec, snapshot, trace, video, or report.
     Accept an explicitly named local-only password environment variable and
     fail clearly without printing its value if setup is missing. Configure
     browser reports/traces to avoid retaining sensitive form content in normal
     runs; use synthetic case text only.
   - Add a discoverable script such as `pnpm test:e2e` and document its browser
     installation/setup prerequisites. Keep it separate from deterministic
     `pnpm test:web` so unit tests do not require Docker or a browser.

8. **Keep documentation, scope, and project status truthful.**

   - Update `README.md`, `apps/web/README.md`, and `docs/development.md` only
     after implementation to say that Case Inbox, submission, and Case Detail
     are available, while clearly retaining the future-phase limits on
     documents, workflow data, evidence, extraction, risk, approval, and audit
     data.
   - Document the local browser-smoke flow using the existing synthetic
     password environment-variable procedure. Never add a credential to text,
     examples, or shell history.
   - Do not change unrelated route placeholders, invent backend endpoints for
     later phases, edit Phase 8 behavior except for the narrowly necessary
     assignee read model, or mark roadmap/progress complete until validation is
     successful.

## Required tests

### Frontend unit and component tests

- Zod Case schemas accept complete valid list/detail/create responses and
  reject malformed UUIDs, enum values, dates, timestamps, envelopes, and
  unexpected response shapes without exposing raw body data.
- Case client builds credentialed relative requests, omits blank filters,
  serializes valid filters/search/pagination correctly, and retains safe API
  failure/request-ID behavior.
- Inbox shows required real columns/data, status/risk text alternatives,
  Norwegian date formatting, locale-aware English rendering, loading, empty,
  filter-empty, 404/error, and retry states.
- Search/filter controls are labelled and keyboard-operable; apply/reset and
  pagination produce expected query state and API calls. The assignee selector
  uses human-readable allowed values and never exposes a UUID as user-facing
  copy.
- Role-dependent create affordance is clear but no test treats it as the
  authorization boundary; API failures remain safe when roles change.
- Submission form validates, has all labels/hints/error associations, sends
  only the permitted payload, disables double submit, handles safe field and
  general errors, invalidates lists, and navigates after success.
- Detail validates its route parameter, renders actual metadata, formats
  date-only and timestamp values safely, handles safe not-found/unavailable
  states, and labels every future data section as unavailable rather than
  inventing a record.
- Shell navigation stays active for all nested Case routes; existing login,
  session redirect, logout, language-switcher, and other placeholder tests
  remain green.

### Backend tests only if the assignee read model is necessary

- The endpoint/schema returns only the approved minimal assignee fields, is
  cookie-authenticated, and enforces the current Case `READ` role policy.
- Results are limited to the current organization and eligible visible active
  cases; foreign tenant data, email, roles, credential fields, inactive-only
  users, and archived-only assignments never leak.
- Repository/service integration tests prove tenant scoping, deterministic
  ordering/bounds, empty results, and no audit event for a read.
- Existing Phase 8 Case and Phase 6 user-management protections remain green;
  `/api/users` stays Admin-only.

### Playwright smoke test

- With a running local stack, explicit migrations, and synthetic local account
  credentials supplied through environment variables, the test logs in using
  the visible form, submits one safe synthetic case, verifies it appears in the
  Bokmål inbox, follows the case link, and verifies the Case Detail heading and
  future-section placeholder.
- The test does not depend on a pre-known case ID, a browser-readable session
  value, a personal account, or a case created by a previous test run.

## Validation steps

Run the following from the repository root after implementation and before
marking the phase complete:

```bash
pnpm format:check
pnpm lint
pnpm typecheck
pnpm check:workspace
pnpm test:web
pnpm test:api
pnpm --filter @nordic-regulated-ai-agent-platform/web build
```

Run the focused frontend work while iterating, then its full deterministic
suite:

```bash
pnpm --filter @nordic-regulated-ai-agent-platform/web test
pnpm --filter @nordic-regulated-ai-agent-platform/web lint
pnpm --filter @nordic-regulated-ai-agent-platform/web typecheck
```

If the narrow assignee endpoint is added, also run the full API suite and the
standard Python quality checks because it changes a protected server boundary:

```bash
uv run ruff format --check apps services packages scripts
uv run ruff check apps services packages scripts
uv run mypy apps services packages scripts
uv run pytest apps/api/tests -q
```

Install the project-managed Playwright browser once in the local development or
CI environment; do not commit the browser cache. Then perform the browser smoke
check against the Compose stack:

```bash
pnpm dev:up
docker compose --env-file .env.example exec api alembic -c apps/api/alembic.ini upgrade head
docker compose --env-file .env.example exec api python scripts/check_migrations.py
read -r -s NORDIC_LOCAL_SEED_PASSWORD
export NORDIC_LOCAL_SEED_PASSWORD
docker compose --env-file .env.example exec -e NORDIC_LOCAL_SEED_PASSWORD api \
  python scripts/seed_local.py --password-env NORDIC_LOCAL_SEED_PASSWORD
pnpm test:e2e
unset NORDIC_LOCAL_SEED_PASSWORD
pnpm verify:local-stack
pnpm dev:down
```

The final implementation documentation must name the actual Playwright browser
installation command and the exact local-only environment variables selected by
the implementation. Never echo the password, cookie, or test session value.
Run the manual equivalent in both Bokmål and English: log in, submit a safe
case, apply/clear filters, open detail, verify date formatting/keyboard flow,
and confirm all future cards are explicitly unavailable. Shut the local stack
down normally after verification.

## Completion criteria

Phase 9 is complete only when all of the following are true:

- The `/cases` placeholder has been replaced by a protected, localized,
  server-backed Case Inbox that supports text search plus status, risk,
  assignee, domain, and priority filters, accessible pagination, and accurate
  required case summary data.
- Users permitted by the backend can submit a validated case through an
  accessible UI; server-owned case number, organization, submitter, and initial
  lifecycle state are never accepted or controlled by the browser.
- A submitted/listed case can be opened through a locale-preserving Case Detail
  route that displays actual Phase 8 metadata/status and only honest
  placeholders for future capabilities.
- The UI is complete in Bokmål and English, uses locale-safe calendar-date and
  timestamp formatting, and meets the specified semantic/keyboard/error/focus
  expectations without relying on colour alone.
- Case data is parsed at the Zod boundary, fetched through credentialed
  same-origin calls, and protected by the existing session/RBAC layer; no
  browser session storage, frontend tenant logic, raw response display, or
  client-only authorization has been introduced.
- The assignee filter is professional and tenant-safe. If a supporting
  Case-read endpoint was needed, it is minimal, typed, protected, tested, and
  does not weaken the Admin-only Users API or create a general user directory.
- Vitest/Testing Library coverage and the new Playwright smoke scenario pass,
  along with formatting, lint, strict type checking, workspace, web build, API
  regression (when touched), and local-stack checks.
- Documentation accurately describes the implemented Case screens and their
  remaining future-phase limits. No real data, credentials, cookies, tokens, or
  unsafe test artifacts were added.
- Only after every listed validation passes may the implementation agent mark
  Phase 9 `(DONE)` in `specs/roadmap.md` and update `specs/progress.md`
  consistently.

## Risks, dependencies, and explicit assumptions

- **Phase 6 authentication/RBAC is a hard dependency.** The UI assumes the
  existing opaque session and protected-route behavior. It must never introduce
  a bearer-token alternative or infer authorization from navigation alone.
- **Phase 7 is the frontend baseline.** Preserve the existing Next.js,
  next-intl, TanStack Query, React Hook Form, Zod, Tailwind, and Vitest
  conventions rather than adding a competing framework or state library.
- **Phase 8 is the Case source of truth.** Do not redesign fields, lifecycle
  transitions, pagination, archive behavior, or audit policy. Phase 9 consumes
  the API and intentionally leaves mutation controls for a later scoped
  interaction design.
- **Assignee data is the only known read-contract gap.** The current Case
  response carries an ID while the user directory is Admin-only. The narrowly
  scoped supporting read model is allowed only if verified necessary to make
  the mandated filter accessible; it must not expand into a directory/team
  feature.
- **No workflow data exists.** A workflow column/card must use honest
  unavailable copy; do not turn a `new` Case status into a claim that a graph
  has run.
- **No documents or attachments exist.** The submission form must not offer a
  non-functional file chooser. Phase 10 owns secure upload and storage.
- **No display name for all related identities may be available.** Do not show
  opaque UUIDs as a substitute for a person. Use a neutral fallback or the
  verified minimal Case read model; do not expose email addresses merely for
  UI convenience.
- **Date-only values need special handling.** `due_date` is a calendar day,
  not a UTC instant. Parsing it as midnight UTC can display the preceding day
  in some environments, so a dedicated formatter is required if native parsing
  cannot guarantee calendar preservation.
- **Playwright needs external runtime preparation.** Browser binaries and the
  Compose stack are not part of a deterministic unit-test run. Keep setup
  explicit, local-only credentials secret, and test data synthetic/unique.
- **Existing worktree changes are user-owned.** This plan is created beside
  pre-existing Phase 7/8 and other edits. The implementation agent must inspect
  status before editing, preserve unrelated changes, and avoid broad rewrites.

## Notes for the implementation agent

- Start with this plan, then re-read the current Phase 7 web shell/auth client
  and Phase 8 Case schemas/routes before making any change. The API contract,
  not a remembered field name, is authoritative.
- Keep feature code cohesive: Case API/schema/query helpers and Case UI
  components should have clear ownership. Avoid a monolithic page component and
  avoid importing ORM/API-server code into the web app.
- Build the responsive and accessible semantic structure first; visual polish
  should not replace labels, headings, error associations, text statuses, or
  correct focus behavior.
- Prefer clear, safe localized messages over exact backend error text. Retain a
  request ID only as a support reference when the typed client provides it.
- Treat placeholder content as a product promise boundary. A labelled empty
  future section is correct; mocked documents, risk flags, citations, or audit
  events are not.
- If the assignee read-model decision is needed, document why the existing
  response was insufficient, keep the server diff small, and validate it like
  any protected API change. Do not relax `/api/users` permissions to save a
  frontend request.
- Do not mark Phase 9 complete until every required test and manual/local stack
  validation has passed. At handoff, report exact files changed, commands and
  results, the assignee-contract decision, assumptions, and any remaining
  future-phase limitations.
