# Phase 26 — AI Quality Evaluation Dashboard

## Phase objective

Replace the authenticated Evaluation placeholder with a Norwegian Bokmål-first dashboard for the safe, tenant-scoped evaluation data delivered in Phase 25. It must show the latest run and recent history, make deterministic score/failure information understandable, link failures to a safe result-detail view, and export a bounded Markdown report for portfolio/review use without exposing corpus questions, source text, prompts, model payloads, or cross-tenant data.

## Relevant context and constraints

- The roadmap requires latest-run status, retrieval, citation, faithfulness, refusal, latency, cost, regression failures, failure-result links, and an evaluation report export. It explicitly requires frontend, API, and integration coverage for run listing, detail, failures, and dashboard metrics.
- Phase 25 already provides protected Admin-only `/api/evaluations` operations for canonical datasets, current-tenant run listing, and a safe run-with-results projection. Reuse this storage, service, authorization policy, and worker output; do not create another evaluation history or execute evaluations from the browser.
- The Phase 25 evaluator reports a **deterministic structural-faithfulness** signal, not a hosted semantic faithfulness judgment. Label it accurately in the UI and exported report. It also does not yet collect observability-quality latency/cost telemetry: use only persisted `EvalResult.latency_ms` and `cost_estimate` when present, otherwise render an explicit localized “not recorded” state. Do not turn missing values into zero or add p95/telemetry/OpenTelemetry work from Phase 27.
- Existing `EvalResult` rows already contain bounded per-case scores, pass/fail, closed failure codes, optional latency, and optional cost. The API currently omits latency/cost and exposes `summary` as an unstructured dictionary; Phase 26 must add a strict, allowlisted dashboard/read-model projection rather than passing arbitrary JSONB to the web client.
- Keep backend RBAC and organization scoping authoritative. The dashboard may present a helpful insufficient-permission state, but it must never rely on client role checks for access control. Evaluation reads, starts, details, and exports remain Admin-only unless the existing policy is deliberately and consistently changed (no new role in this phase).
- Frontend conventions are Next.js App Router, `next-intl`, TanStack Query, Zod API validation, `ProtectedPage`, Tailwind, accessible semantic controls, and `data-testid` only where a critical workflow needs a stable test selector. Bokmål is the default and English must have matching complete translations.
- This is a user-visible workflow. Run focused browser E2E only after API, component, lint, and type checks pass. Do not run the full Playwright suite by default.

## In scope

1. A protected `/[locale]/evaluations` dashboard showing the latest available current-organization run, a paginated/recent run history, safe aggregate score cards, status/pass-fail states, regression failure counts, and an Admin-only “run evaluation” action.
2. Run and result detail screens, with accessible links from failed cases to a safe per-case record that shows only case key, bounded score values, optional measured latency/cost, pass/fail, and closed failure codes.
3. A strict backend read-model/API extension that exposes only allowlisted aggregate metrics and safe optional per-result latency/cost values. It must distinguish an absent measurement from a zero measurement.
4. A protected Markdown evaluation report export for one current-organization run, generated server-side from the same safe projection, downloaded by the UI, and logged as an audit event. It is a review/portfolio report, not the generic export framework of Phase 28.
5. Norwegian Bokmål and English copy, localized numbers/timestamps, meaningful loading/empty/error/forbidden states, keyboard-accessible tables/links/buttons, and focused API, integration, component, and one dashboard E2E test.

## Out of scope

- Changes to the deterministic corpus, runner policy, worker routing, dataset editor/import, threshold configuration, hosted judging, real model execution, semantic faithfulness, or evaluation scheduling (Phase 25 and later AI-quality work).
- Cross-run trends, p95 calculations, metrics pipelines, structured logging expansion, OpenTelemetry, cost/latency instrumentation, or new provider accounting (Phase 27).
- Generic JSON/CSV/PDF output export, approved-case export, mock integrations, or a reusable export job system (Phase 28). The only new export is the bounded evaluation Markdown report.
- Changes to global navigation authorization, case/workflow behavior, database schema migrations, roles, or Phase 30 accessibility-polish work beyond the controls introduced here.
- Raw corpus questions, expected sources, prompts, generated answers, source excerpts, model/provider payloads, exception text, tenant identifiers, or other unsafe JSONB in browser responses, downloads, tests, or UI logs.

## Likely files, folders, modules, and services affected

| Area | Likely files/folders | Phase-26 responsibility |
| --- | --- | --- |
| Evaluation read model | `apps/api/src/app/services/evaluation/service.py`, `apps/api/src/app/db/repositories/evaluation.py`, a small reporting/projection module if warranted | Aggregate persisted, current-tenant run/result values into an allowlisted dashboard projection; fetch one result only through its parent run and organization boundary. |
| API contracts and routes | `apps/api/src/app/api/schemas/evaluations.py`, `apps/api/src/app/api/routes/evaluations.py`, `apps/api/src/app/api/dependencies.py` only if needed | Extend list/detail safely, add the result-detail and Markdown-report operations, preserve response envelopes for JSON endpoints, document auth/error responses in OpenAPI. |
| Audit | `apps/api/src/app/services/audit/service.py`, evaluation service tests | Record a compact `evaluation.report_exported` event with run/dataset identity and format only; no report body or evaluation content in metadata. |
| Web API/query layer | `apps/web/src/lib/api/contracts.ts`, new `lib/api/evaluations.ts`, new `lib/evaluations/query.ts` | Add strict Zod schemas, typed API functions, query keys/retry behavior, run-start invalidation/polling, and authenticated Markdown download handling. |
| Web UI and routes | `apps/web/src/app/[locale]/evaluations/page.tsx`, new `components/evaluation/`, new `app/[locale]/evaluations/runs/[evaluationRunId]/...` pages | Implement dashboard, run detail, result detail, metric/status UI, report control, and stable navigation between failure records. |
| Localization and formatting | `apps/web/messages/nb.json`, `apps/web/messages/en.json`, `apps/web/src/lib/formatting/index.ts` if a small duration formatter is needed | Replace the Phase-26 placeholder text and format timestamp, scores, nullable duration, and numeric cost consistently for `nb-NO` and English. |
| Tests | `apps/api/tests/unit/`, `apps/api/tests/integration/test_evaluation_service.py`, `apps/api/tests/api/test_evaluations.py`, `apps/web/src/tests/unit/`, `apps/web/e2e/` | Cover safe metric projection, organization/RBAC boundaries, report content/headers/audit, web API parsing, UI states, locale text, and the primary Admin dashboard path. |

## Execution plan

### 0. Run the worktree baseline gate

1. Run `git status --short` before implementation.
2. The current `AGENTS.md` modification is user-owned. Preserve it. Stop if any further unclear changes are present unless the user explicitly accepts them as the Phase 26 baseline.
3. Inspect the Phase 25 evaluation route, schemas, service/repository, models, audit policy, and existing web API/query/component test patterns. Confirm the canonical run/detail APIs and their safe data contract before editing.

### 1. Define and test the strict dashboard/read-report projection

1. Add a small typed projection/aggregation boundary around existing `EvalRun` and `EvalResult` records. It must include: run identity/version/status/timestamps/pass-fail; case totals and failure count; mean available retrieval, citation, structural-faithfulness, refusal, risk, and routing scores; optional aggregate measured latency and cost; and a bounded failure-code count/list suitable for display. Define calculation/rounding and all-null behavior explicitly.
2. Extend the safe per-result projection with nullable `latency_ms` and `cost_estimate` fields. Expose a result only under a parent run owned by the current organization; retain case key, scores, pass/fail, and closed failure codes, and omit all corpus/prompt/source/generative content.
3. Keep the API contract strict: replace/contain the arbitrary `summary: dict[str, object]` behind typed allowlisted fields needed by the dashboard, or retain it only if it is validated server-side against a closed allowlist. Do not make frontend schemas accept arbitrary `summary_metrics` JSONB.
4. Add a pure server-side Markdown report renderer that uses the exact safe projection. Include report title, dataset version/hash, run timestamps/status, pass/fail, safe metric summary, and failure records (case key, scores, closed codes). Give unavailable latency/cost a clear textual marker. It must not interpolate question text, source keys, outputs, raw exceptions, or user-controlled filenames.
5. Add focused unit tests before route/UI work.

   - Likely tests: new `apps/api/tests/unit/test_evaluation_reporting.py` plus focused additions to `apps/api/tests/integration/test_evaluation_service.py`.
   - Cover mixed/null metric aggregation, no false zeroes, rounding, no results, deterministic report ordering, Markdown safety, safe failure-only content, and a two-organization result lookup denial.
   - Focused validation:
     ```bash
     uv run pytest apps/api/tests/unit/test_evaluation_reporting.py apps/api/tests/integration/test_evaluation_service.py
     ```
   - Expected result: existing persisted evaluation records produce stable, bounded dashboard/report data and no unapproved JSON/text can enter either projection.

### 2. Extend protected evaluation API operations and audit export

1. Reuse the existing `/api/evaluations` router and Admin authorization policy. Extend run list/detail responses with the typed metric projection; preserve current pagination, safe unknown-resource behavior, and response envelope conventions.
2. Add `GET /api/evaluations/runs/{evaluation_run_id}/results/{evaluation_result_id}` (or the repository’s equivalent documented nested route) for one safe result-detail projection. Verify the run ID and current organization first; an unknown, mismatched, or foreign result must return the existing safe not-found response.
3. Add a single protected report-export operation for one run, preferably `POST /api/evaluations/runs/{evaluation_run_id}/report` with an empty strict body. Return UTF-8 Markdown with a fixed server-generated filename and `Content-Disposition: attachment`; do not accept format, filename, or template input. Record a compact `evaluation.report_exported` audit event only after access is authorized.
4. Keep the existing start endpoint server-owned. Its web consumer may request only the dataset key and empty body; it must not choose organization, threshold, provider, corpus, or metric controls. Return the queued run and have the frontend invalidate/poll it instead of optimistically claiming completion.
5. Add API/OpenAPI and integration tests before starting frontend work.

   - Tests: update `apps/api/tests/api/test_evaluations.py`, `test_openapi.py`, `test_router_registry.py`, and `apps/api/tests/integration/test_evaluation_service.py`.
   - Cover Admin success; non-Admin denial; unauthenticated requests; cross-organization/mismatched result IDs; strict start/export bodies; typed nullable latency/cost and score aggregates; no raw `summary_metrics`; Markdown response headers/body safety; report-export audit metadata; queued/running/completed/failed/empty results; and no route regression.
   - Focused validation:
     ```bash
     uv run pytest apps/api/tests/api/test_evaluations.py apps/api/tests/api/test_openapi.py apps/api/tests/api/test_router_registry.py
     uv run pytest apps/api/tests/integration/test_evaluation_service.py apps/api/tests/api/test_audit.py
     ```
   - Expected result: all evaluation reads/exports remain Admin-only and tenant-scoped, while the documented safe data and Markdown report are available through OpenAPI-backed routes.

### 3. Build the typed web client and query behavior

1. Add exact Zod contracts mirroring the allowlisted backend run metrics, run detail, result detail, and error envelopes in `apps/web/src/lib/api/contracts.ts`. Do not use `z.unknown()`, a catch-all record, or a client reinterpretation of `summary_metrics`.
2. Add `apps/web/src/lib/api/evaluations.ts` for dataset listing, run start, runs, run detail, result detail, and report download. URL-encode path IDs, send only `{}` for a start/export body, and parse the Markdown download only after checking the response headers/status.
3. Add `apps/web/src/lib/evaluations/query.ts` with stable query keys and the existing retry discipline. Poll only queued/running run data at a bounded interval; stop polling on terminal state/unmount. On a successful start, invalidate datasets/runs and follow the queued run rather than fabricating metrics.
4. Add focused API client/query tests for strict parsing, invalid/unsafe payload rejection, query keys, non-retryable auth/validation failures, terminal polling stop, mutation invalidation, and report download failure handling.

   - Tests: new `apps/web/src/tests/unit/evaluation-api.test.ts` and focused query tests if query behavior is separated.
   - Focused validation:
     ```bash
     pnpm --filter @nordic-regulated-ai-agent-platform/web test -- evaluation-api
     pnpm --filter @nordic-regulated-ai-agent-platform/web typecheck
     ```
   - Expected result: the browser handles only typed, safe contracts and displays API failures without leaking or fabricating evaluation values.

### 4. Implement the localized dashboard, run/result detail, and report action

1. Replace the evaluation placeholder at `apps/web/src/app/[locale]/evaluations/page.tsx` with an `EvaluationDashboard` wrapped in `ProtectedPage`. Use the existing authenticated user query to show a localized, non-destructive forbidden state for non-Admins; backend enforcement remains the security boundary.
2. Implement an accessible dashboard with:
   - latest-run status/pass-fail and timestamp;
   - metric cards for retrieval, citation, **deterministic structural faithfulness**, refusal behavior, measured latency, and estimated cost;
   - explicit “not recorded” treatment for absent latency/cost and a short deterministic-metric limitation note;
   - recent run table/list with status, totals, failures, timestamp, and links to run detail; and
   - Admin-only canonical dataset selection plus a disabled/pending “run evaluation” action with a clear active-run conflict/error state.
3. Add run detail and result detail routes/components. The run view shows safe summary metrics and a result table; failed rows link to their result-detail page. The result view shows case key, pass/fail, individual score labels, nullable measured latency/cost, and closed regression failure codes—never the underlying fixture/question/source material.
4. Add a visible report action on terminal run detail only. It must have an accessible pending/error state and download the server-produced Markdown rather than composing an unreviewed client-side report.
5. Replace placeholder message keys in both locale files with complete dashboard/run/result/report/error/empty/permission/status text. Reuse locale-aware timestamp/number formatting; add a small duration formatter only if it can be tested without locale ambiguity. Do not label unqualified numeric cost as Norwegian currency.
6. Write component tests alongside each UI slice before moving to the next one.

   - Tests: new `evaluation-dashboard.test.tsx`, `evaluation-run-detail.test.tsx`, and `evaluation-result-detail.test.tsx` under `apps/web/src/tests/unit/`.
   - Cover Bokmål default/English translation, loading/error/empty/forbidden states, queued polling presentation, nullable metrics, accurate structural-faithfulness wording, run/result links, failure-code rendering, keyboard-reachable controls, start invalidation, and report action success/failure.
   - Focused validation:
     ```bash
     pnpm --filter @nordic-regulated-ai-agent-platform/web test -- evaluation-dashboard evaluation-run-detail evaluation-result-detail
     pnpm --filter @nordic-regulated-ai-agent-platform/web lint
     pnpm --filter @nordic-regulated-ai-agent-platform/web typecheck
     ```
   - Expected result: an Admin can understand safe current-tenant evaluation quality/results in both locales; unavailable telemetry is honest and every failure link reaches a safe detail record.

### 5. Perform final scope review, focused E2E, and required validation

1. Before expensive validation, review the implementation against this plan: dashboard, detail routes, safe API metrics/result/export, translations, and focused tests must be complete; no Phase 27 telemetry or Phase 28 generic export work may be present.
2. Add one focused Playwright scenario using synthetic seeded Admin data: open `/nb/evaluations`, start or inspect a terminal canonical run, open its detail, follow a failed result link when a seeded failing run is used, and download/verify the bounded report. Add a non-Admin assertion that the UI does not expose evaluation data. Use stable test IDs only for the dashboard/run/result/report workflow.
3. Run the focused checks first; repair the smallest failure before continuing. Then run affected frontend/backend static checks and the focused browser test. This phase changes an authenticated user-visible flow and API route, so run the local stack check last after the scope review.
4. Review `git diff --check`, verify no unsafe evaluation material is emitted in API/report/E2E fixtures, and only then let a later implementation turn mark the roadmap phase `(DONE)` and update `specs/progress.md`.

## Required tests

- Projection/report unit tests: safe aggregation, empty/null handling, deterministic ordering/rounding, unavailable versus zero metrics, Markdown escaping/content bounds, and no corpus/prompt/source/raw-error leakage.
- Evaluation service/integration tests: current-tenant run/result lookup, aggregate result query behavior, terminal/active state handling, and compact report-export audit event.
- API/OpenAPI tests: cookie authentication, Admin enforcement, cross-tenant/mismatched nested IDs, response schema strictness, nullable telemetry, safe not-found behavior, report headers/body, strict empty export/start body, and no untyped `summary_metrics` exposure.
- Frontend API/query tests: Zod schema rejection, URL handling, non-retryable failures, bounded polling, cache invalidation, and Markdown download error handling.
- Component tests: Bokmål/English copy, loading/empty/error/forbidden/active-run states, metric cards, deterministic faithfulness disclosure, result links, failure codes, report control, and keyboard-accessible semantics.
- Focused Playwright test: seeded Admin evaluation dashboard to safe run/result/report path plus non-Admin denial. No full E2E suite unless the user asks.

## Validation Plan

### Focused validation — required

```bash
uv run pytest apps/api/tests/unit/test_evaluation_reporting.py apps/api/tests/integration/test_evaluation_service.py
uv run pytest apps/api/tests/api/test_evaluations.py apps/api/tests/api/test_openapi.py apps/api/tests/api/test_router_registry.py apps/api/tests/api/test_audit.py
pnpm --filter @nordic-regulated-ai-agent-platform/web test -- evaluation-api evaluation-dashboard evaluation-run-detail evaluation-result-detail
pnpm --filter @nordic-regulated-ai-agent-platform/web lint
pnpm --filter @nordic-regulated-ai-agent-platform/web typecheck
```

### Broader validation — required when shared contracts/routes are touched

```bash
uv run ruff check apps/api services/evaluation
uv run mypy apps/api services/evaluation
pnpm format:check
pnpm --filter @nordic-regulated-ai-agent-platform/web test
pnpm --filter @nordic-regulated-ai-agent-platform/web test:e2e -- evaluation-dashboard
```

- Keep browser scope to the Phase 26 dashboard journey. If this focused E2E fails, diagnose/fix the Phase 26 cause and rerun it once. If it fails a second time, stop and provide the exact blocker and manual browser fallback rather than repeatedly looping.

### Expensive validation — required for this user-visible authenticated/API phase

Run only after the final scope/read-model/API-contract review and passing focused checks:

```bash
pnpm dev:up
docker compose --env-file .env.example exec api uv run alembic -c apps/api/alembic.ini upgrade head
pnpm verify:local-stack
pnpm --filter @nordic-regulated-ai-agent-platform/web test:e2e -- evaluation-dashboard
pnpm dev:down
git diff --check
```

- Add the smallest seeded local-stack smoke path needed to prove an Admin sees a terminal evaluation run, a failed-result detail (when the seed supplies one), and the safe Markdown export. Do not need a real model provider, external network, or generic export job.
- If code changes after this gate, rerun affected focused tests and this final local-stack/browser check.

## Completion criteria

- `/nb/evaluations` and `/en/evaluations` are protected, localized, accessible dashboards that show safe latest/recent current-tenant evaluation state, scores, failure information, and honest absent latency/cost states.
- Existing evaluation APIs have a strict allowlisted dashboard/read-model extension, safe nested result detail, and a protected Markdown report export; all remain Admin-only and organization-scoped with no raw corpus/model/source data leakage.
- Failed evaluation cases link to safe detail records; terminal runs offer a server-generated report whose content and audit metadata are bounded and tested.
- Structural faithfulness is accurately described as a deterministic evaluation signal. No synthetic zero cost/latency, hosted evaluation, p95 metrics, observability system, generic export framework, or other future-phase work is introduced.
- Required focused checks, applicable broader checks, the focused evaluation browser E2E/local-stack validation, and `git diff --check` pass. The phase is only then eligible to be marked `(DONE)` and recorded in progress.

## Risks, dependencies, and notes for the implementation agent

- Phase 25 must have a canonical dataset and inspectable safe run/result records before UI work begins. Keep its current contracts compatible unless a small additive typed projection is essential; update API/OpenAPI tests whenever an exposed contract changes.
- Do not use model-evaluation terminology more strongly than the deterministic runner supports. The card/export must say “structural faithfulness” (with local explanation), not imply a semantic or human-quality judgment.
- `latency_ms` and `cost_estimate` are optional existing storage fields, not authorization to invent timing/cost tracking. Display missing values explicitly and avoid locale currency formatting unless the API later supplies an authoritative currency.
- Report download must be generated from the same service projection used by the screen. A client-generated report, raw JSONB serialization, query/body-controlled templates, or a filename from user input would weaken the safety boundary.
- API error handling and routes must preserve current safe 401/403/404 behavior. The web page must not redirect an authenticated non-Admin user to login merely because the evaluation resource is forbidden.
- Preserve the user-owned `AGENTS.md` worktree modification. This is plan-only work: do not update roadmap/progress or source code, and do not mark Phase 26 complete.
