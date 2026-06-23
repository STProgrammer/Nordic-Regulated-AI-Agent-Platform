# Phase 25 — Evaluation Dataset and Deterministic Evaluation Runner

## Phase objective

Deliver a synthetic, versioned Nordic evaluation corpus and a deterministic evaluation service that can run it without a model, embedding provider, or network dependency. The service must score and persist retrieval-source expectations, citation expectations, refusal behavior, risk labels, and closed workflow-routing outcomes so protected API consumers—and the Phase 26 dashboard—can inspect truthful pass/fail results.

## Relevant context and constraints

- The roadmap requires synthetic Norwegian and English datasets for public-sector, banking, energy, and internal-policy scenarios; a deterministic runner for retrieval, citation, refusal, risk, and LangGraph routing; and persisted datasets, runs, and per-case results that are locally inspectable without an external model where possible.
- PRD `FR-EVAL-001` requires questions, expected source references, answer criteria, and risk labels, with no real personal data. `FR-EVAL-002` requires locally runnable/CI-suitable evaluation, stored results, and deterministic quality thresholds that can later gate releases. `FR-EVAL-003` requires fixed regression scenarios.
- Architecture §6.6 and §7.8 assign dataset execution, retrieval/citation/faithfulness/refusal scoring, persistence, and pass/fail marking to the evaluation service. Architecture §10 already defines `eval_datasets`, `eval_cases`, `eval_runs`, and `eval_results`; §11 reserves the evaluations API routes; §17.6 names the required deterministic behaviors.
- The repository has those base SQLAlchemy models and a reserved `/api/evaluations` router and `services/evaluation` workspace, but no evaluation contracts, runner, repository/service, worker task, datasets, API operations, or test coverage. Reuse them; do not add a second evaluation store or route group.
- Existing workflow/retrieval code already exposes closed policy seams: source filtering and evidence sufficiency, citation validation, Intake routing, and final-risk policy. The runner must exercise or adapt those same deterministic policy contracts instead of duplicating decision rules or invoking a hosted judge.
- Cookie authentication, backend RBAC, organization scoping, strict Pydantic response envelopes, UUID-only worker task messages, metadata-safe auditing/logging, synthetic data only, and deterministic local providers remain mandatory. Never put prompts, model payloads, raw case text, secrets, or caller-controlled provider configuration in an evaluation task, run record, result, or API response.

## In scope

1. A checked-in, versioned, Pydantic-validated synthetic evaluation corpus with Norwegian Bokmål and English cases across public-sector, banking, energy, and internal-policy domains.
2. Closed dataset/case schemas containing logical fixture/source keys, questions, expected answer-criterion identifiers, citations, refusal behavior, risk level, and routing outcome—never database UUIDs or production data.
3. A deterministic runner that composes existing policy/citation/risk/routing seams through server-owned fixture adapters and produces reproducible per-case metrics and closed failure codes without network/model/embedding calls.
4. Idempotent loading of the canonical global dataset; tenant-scoped persisted execution runs and per-case results with an immutable dataset/version/hash association and safe run summaries.
5. A UUID-only background evaluation task plus an authenticated, typed API to list canonical datasets, start a run, list current-tenant runs, and inspect one current-tenant run/result projection.
6. A small local/CI-friendly `scripts/run_evals.py` entry point that validates and executes the checked-in corpus deterministically, emits a safe summary, and fails non-zero when fixed thresholds fail.
7. Focused unit, service, API, worker, migration (if the existing schema needs reinforcement), and integration coverage.

## Out of scope

- Evaluation Dashboard UI, charts, trend views, web API client, frontend tests, browser E2E, result export, or portfolio reports (Phase 26).
- Hosted-model judging, DeepEval/Ragas, external embeddings/rerankers, real provider credentials, semantic similarity claims, prompt authoring/version management, and any non-deterministic quality gate.
- A generic dataset editor, tenant-supplied dataset upload/import, arbitrary JSON evaluation payloads, arbitrary metric expressions, or public/unauthenticated evaluation endpoints.
- Cost/latency aggregation/telemetry infrastructure, p95 calculations, OpenTelemetry, CI workflow wiring, or release blocking configuration (Phases 27 and 31).
- Changes to case status, source governance, document indexing, retrieval ranking, draft text, risk/approval decisions, graph behavior, or the controlled-memory policy. The runner observes tested policy contracts; it does not become a production workflow path.
- Real personal data, copied customer/case/document content, raw workflow snapshots, prompts, provider outputs, or secrets in fixtures, database records, logs, API responses, or test artifacts.

## Likely files, folders, modules, and services affected

| Area | Likely files/folders | Phase-25 responsibility |
| --- | --- | --- |
| Corpus and contracts | `sample-data/evaluation/`, `services/evaluation/src/evaluation/datasets/`, `services/evaluation/src/evaluation/contracts.py` | Store one canonical versioned JSON corpus and validate a closed schema, source-key namespace, coverage, and content safety before execution or persistence. |
| Metrics and runner | `services/evaluation/src/evaluation/metrics/`, `runners/`, `reports/`, `services/evaluation/tests/` | Implement pure deterministic execution, scoring, thresholding, failure-code generation, and compact safe reporting. |
| Persistence | `apps/api/src/app/db/models/evaluation.py`, new `db/repositories/evaluation.py`, `services/evaluation/` adapters, `apps/api/migrations/versions/` only if needed | Make canonical dataset loading idempotent; bind tenant-owned runs/results to a dataset version; enforce status, uniqueness, and readable indexes. |
| API and authorization | `apps/api/src/app/api/routes/evaluations.py`, `api/schemas/evaluations.py`, `api/dependencies.py`, `services/evaluation/` API-facing service, router/OpenAPI tests | Add protected dataset/run/read operations using existing response envelopes and explicit roles; callers never choose a provider, source corpus, organization, or arbitrary test payload. |
| Background execution | `apps/api/src/app/services/evaluation/`, `workers/tasks.py`, `workers/celery_app.py`, `docker-compose.yml` | Queue only an evaluation-run UUID, reload and authorize server-side state, execute deterministically, persist a terminal safe result, and route the task to an `evaluation` queue. |
| Local tooling and docs | `scripts/run_evals.py`, `scripts/seed_local.py` only if canonical dataset registration belongs there, `docs/ai-evaluation.md` or `docs/development.md` | Provide a synthetic-only, provider-free command and concise explanation of the metrics, fixed thresholds, and its scope. |
| Tests | `services/evaluation/tests/`, `apps/api/tests/unit/`, `apps/api/tests/api/`, `apps/api/tests/integration/`, worker/router/OpenAPI tests | Prove deterministic correctness, persistence, isolation, authorization, and safe failure handling. |

Use current naming conventions and existing SQLAlchemy repository/service boundaries. Do not add a web page or a new top-level API prefix.

## Execution plan

### 0. Run the worktree baseline gate

1. Run `git status --short`.
2. If there are unclear uncommitted changes from earlier phases, stop and report them.
3. Continue only if the current dirty worktree is explicitly accepted as the baseline.

### 1. Define the immutable evaluation contract and synthetic corpus

1. Inspect the existing evaluation SQL models, shared response envelopes, current source/citation/risk/routing policy APIs, and deterministic test fixtures before designing new types.
2. Add strict Pydantic dataset contracts in `services/evaluation` for metadata, stable dataset/case/source keys, locale, domain, query, expected answer-criterion IDs, expected source/citation keys, refusal expectation, expected risk level, and expected routing outcome. Reject extra keys, duplicate keys, unknown enums, blank/overlong values, unstable DB IDs, and unchecked free-form result fields.
3. Add one versioned corpus under `sample-data/evaluation/` with at least one Norwegian Bokmål and one English case and coverage of all four required domains. Use harmless invented facts and logical source keys; include both ordinary grounded cases and at least one weak-evidence/refusal case, a PII/high-risk case, and a routing-sensitive case.
4. Add corpus validation for version/hash stability, domain/language coverage, expected-source/citation consistency, deterministic ordering, and conservative synthetic-data screening. It must fail closed on contact details, national identifiers, secrets, URLs/storage identifiers, or copied real-looking case content.
5. Add focused corpus/contract tests before adding persistence.

   - Tests: `services/evaluation/tests/test_dataset_contract.py`, including valid corpus loading, all required coverage, duplicate/unknown/extra-field rejection, safety rejection, and source/citation-reference invariants.
   - Focused validation: `uv run pytest services/evaluation/tests/test_dataset_contract.py`
   - Expected result: the corpus is accepted only when it is complete, synthetic, versioned, and deterministic.

### 2. Build a pure deterministic evaluator around existing policy seams

1. Define a narrow `EvaluationScenarioExecutor` port and a server-owned deterministic implementation. It must accept only a validated evaluation case and produce an allowlisted observation: logical retrieved-source keys, citation keys, answer-criterion coverage, refusal outcome/reason code, final risk label, and routing outcome.
2. Compose existing closed retrieval/evidence, citation, Intake routing, and risk-policy behavior where their inputs are already deterministic. Where a fixture adapter is required, pass only logical synthetic keys and bounded signals. Do not copy production policy code into `services/evaluation`, run a real worker graph, or construct a model/embedding/retrieval provider.
3. Implement explicit metrics: retrieval precision/recall against expected logical source keys, citation correctness/coverage, deterministic answer-criterion support (the Phase-25 structural faithfulness proxy), refusal correctness, risk-label correctness, and routing correctness. Record only bounded numeric values, booleans, expected/actual logical keys where safe, and closed failure codes.
4. Define a versioned, all-deterministic threshold policy. Core regression cases must require exact expected behavior; a case or run with any required mismatch fails. Include a stable summary with totals and per-metric pass counts. Do not claim semantic model faithfulness or language-quality scoring from these checks.
5. Add `scripts/run_evals.py --dataset nordic-regulated-core-v1 --check` as a pure local command. It loads the checked-in corpus, runs the deterministic executor, prints a compact safe summary, and returns non-zero on a failed threshold. It must neither need a database nor read external credentials.
6. Add focused runner/metric/script tests before connecting the API or database.

   - Tests: `services/evaluation/tests/test_deterministic_runner.py`, `test_metrics.py`, and `test_run_evals_script.py`; include a deliberately mismatched fixture, stable ordering/hash behavior, and an assertion that network/model/embedding provider constructors are never called.
   - Focused validation:
     ```bash
     uv run pytest services/evaluation/tests/test_deterministic_runner.py services/evaluation/tests/test_metrics.py services/evaluation/tests/test_run_evals_script.py
     uv run python scripts/run_evals.py --dataset nordic-regulated-core-v1 --check
     ```
   - Expected result: the canonical corpus passes reproducibly; one controlled mismatch produces only the documented failure code(s) and a failing exit status.

### 3. Persist canonical datasets and tenant-owned execution history

1. Add a repository and application service that load the validated canonical corpus idempotently. Canonical datasets remain global/read-only (`organization_id` is null); every execution run belongs to the requesting organization. Do not add tenant-authored datasets in this phase.
2. Review the Phase 4 evaluation tables against these invariants. Add a minimal Alembic migration only if required to enforce durable case keys, dataset version/content hash, terminal/active run state, one result per `(run, case)`, useful tenant/run indexes, and safe uniqueness/idempotency. Backfill safely and retain the architecture table names and relationships.
3. Persist a queued run before dispatch, then its terminal status, timestamps, compact summary metrics, pass/fail, and one result per case. Results may contain the supported numeric scores, pass boolean, case key, and closed failure codes/reason metadata; they must not retain question text, complete generated text, prompts, raw evidence, provider exceptions, or workflow snapshots.
4. Prevent duplicate active executions of the same canonical dataset/version for one organization; allow a later completed run to be started deliberately. Make repeated worker delivery idempotent and leave an unexpected executor failure as a safe failed terminal run with no partial duplicate results.
5. Add a read projection suitable for Phase 26: dataset/run identity/version, safe timestamps/status, metric summary, pass/fail, and per-case metric/failure detail. Keep global dataset source material and tenant run records correctly separated.
6. Add persistence and migration tests before adding HTTP operations.

   - Tests: `apps/api/tests/integration/test_evaluation_service.py` plus migration coverage in `test_database_foundation.py` or a new focused migration test. Cover canonical-load idempotency, constraint/index behavior, transaction rollback, repeated task delivery, terminal-state immutability, two-tenant isolation, and safe result projection.
   - Focused validation: `uv run pytest apps/api/tests/integration/test_evaluation_service.py apps/api/tests/integration/test_database_foundation.py`
   - Expected result: deterministic dataset data loads once, a tenant run persists exactly once per case, and no other tenant can resolve its history.

### 4. Add the protected API and UUID-only worker path

1. Add strict request/response schemas and operations to the existing `/api/evaluations` router:
   - list canonical datasets;
   - start a canonical dataset run using a server-owned dataset identifier only;
   - list current-organization runs with bounded pagination/filtering; and
   - read one current-organization run with its safe per-case result projection.
2. Require an authenticated Admin to start a run. Permit only the role(s) already authorized by the existing policy for evaluation inspection; choose and document the narrowest existing role combination rather than adding a new role. Enforce organization scoping in the service/repository, not the client or route alone. Foreign and unknown resources must have the current safe not-found behavior.
3. Register the evaluation service dependency and retain the existing router registry/OpenAPI conventions. Keep operations JSON-only and prohibit client-supplied organization IDs, fixture data, model/provider settings, threshold overrides, source identifiers, or arbitrary filters.
4. Add an `evaluation` Celery queue and a UUID-only `run_evaluation_task`. The worker must reload the persisted run/dataset, ignore malformed/unknown/terminal IDs, execute the pure deterministic runner, commit one safe terminal outcome, and use bounded retry/error handling. Add the queue to local worker consumption without changing unrelated task routes.
5. Record compact audit events for run requested, completed, and failed with dataset/run IDs, version, status, pass/fail, counts, and closed error code only. Do not log corpus content, per-case question/source text, model data, or raw exceptions.
6. Add API, authorization, OpenAPI/router, and worker tests before broader checks.

   - Tests: `apps/api/tests/api/test_evaluations.py`, `test_openapi.py`, `test_router_registry.py`, and focused worker tests. Cover cookie auth, start-role denial, strict body validation, no caller organization/provider controls, cross-tenant read denial, active-run conflict, safe unknown ID behavior, UUID-only task payload, duplicate delivery, and safe failure persistence.
   - Focused validation:
     ```bash
     uv run pytest apps/api/tests/api/test_evaluations.py apps/api/tests/api/test_openapi.py apps/api/tests/api/test_router_registry.py
     uv run pytest apps/api/tests/unit/test_evaluation_tasks.py
     ```
   - Expected result: only authorized users can start/read their allowed evaluation data; the worker receives and resolves only a run UUID and no protected execution content leaks.

### 5. Finish documentation and phase validation in the required order

1. Add a concise evaluation guide covering corpus location/versioning, synthetic-data rules, each deterministic metric and its limits, the local command, persisted API inspection, and the distinction between Phase 25 structural checks and future hosted/semantic evaluation. Do not document a dashboard that does not exist yet.
2. Run the focused checks from Steps 1–4. Fix their smallest failures before proceeding.
3. Run the affected broader static/API/integration checks only after focused checks pass.
4. Because this phase changes persistent state, API routing, Celery queue configuration, and local worker consumption, run the local-stack migration/health check and a provider-free queued evaluation smoke check last. No browser E2E is required: this phase has no user-visible web workflow.
5. Review the final diff against this plan, ensure the Phase 26 dashboard and Phase 27 observability work remain absent, run `git diff --check`, and only then let a later implementation turn mark Phase 25 `(DONE)` and update `specs/progress.md`.

## Required tests

- Dataset schema/corpus tests: exact language/domain coverage, schema strictness, source/citation/criterion consistency, synthetic-content screening, stable hash/version, and deterministic ordering.
- Runner/metric tests: expected source/citation/refusal/risk/routing outcomes, threshold aggregation, controlled failures, no external model/embedding/network construction, and reproducible output.
- Persistence tests: idempotent global dataset loading, per-tenant run ownership, one result per case, active/terminal state transitions, transaction rollback, duplicate worker delivery, migrations, and safe projections.
- API tests: cookie auth, narrow role enforcement, strict request schemas, server-owned controls, pagination/filter validation, organization isolation, unknown/foreign behavior, and response/OpenAPI/router contracts.
- Worker tests: UUID validation, task route/queue registration, durable reload, idempotent execution, and content-free safe failures/audit metadata.
- Tooling tests: `scripts/run_evals.py --check` passes for the canonical corpus and exits non-zero for a controlled failing fixture.

## Validation Plan

### Focused validation — required

```bash
uv run pytest services/evaluation/tests/test_dataset_contract.py services/evaluation/tests/test_deterministic_runner.py services/evaluation/tests/test_metrics.py services/evaluation/tests/test_run_evals_script.py
uv run python scripts/run_evals.py --dataset nordic-regulated-core-v1 --check
uv run pytest apps/api/tests/integration/test_evaluation_service.py
uv run pytest apps/api/tests/api/test_evaluations.py apps/api/tests/unit/test_evaluation_tasks.py
uv run ruff check apps/api services/evaluation scripts
uv run mypy apps/api services/evaluation scripts
```

### Broader validation — required when shared seams are touched

```bash
uv run pytest services/evaluation/tests
uv run pytest apps/api/tests/api/test_openapi.py apps/api/tests/api/test_router_registry.py apps/api/tests/api/test_audit.py
uv run pytest apps/api/tests/integration/test_database_foundation.py apps/api/tests/integration/test_workflow_trace.py
pnpm format:check
```

- Also run the focused existing retrieval/citation, Intake-routing, and risk-policy tests whose pure interfaces the runner reuses. Do not run the full API, integration, web, or Playwright suites by default.

### Expensive validation — required for this phase

```bash
pnpm dev:up
docker compose --env-file .env.example exec api uv run alembic -c apps/api/alembic.ini upgrade head
docker compose --env-file .env.example exec api uv run alembic -c apps/api/alembic.ini current
docker compose --env-file .env.example exec api uv run alembic current
docker compose --env-file .env.example exec api uv run python scripts/run_evals.py --dataset nordic-regulated-core-v1 --check
pnpm verify:local-stack
pnpm dev:down
git diff --check
```

- Add one API/worker smoke check to the stack validation that queues a canonical run with synthetic seeded Admin credentials and verifies its stored terminal pass result through the protected API. Keep it script/API based; browser E2E and a manual browser fallback are not needed for this backend/worker-only phase.
- If a local-stack check fails, fix the current Phase 25 cause and rerun it once. If it fails again, stop and report the exact blocker rather than broadening to full suites.

## Completion criteria

- A versioned, synthetic, strict corpus covers Norwegian Bokmål and English plus public-sector, banking, energy, and internal-policy scenarios, including expected source/citation/answer criteria, refusal, risk, and routing outcomes.
- The deterministic runner produces repeatable source, citation, structural-faithfulness, refusal, risk, and routing scores with closed failure reasons and no model, embedding, or network dependency. The canonical CLI check passes; a deliberate mismatch fails predictably.
- Canonical datasets load idempotently, while evaluation runs/results are durable, current-tenant scoped, version/hash-associated, safe to retry, and inspectable through a protected bounded API.
- Starting and executing a run uses only server-owned controls and a UUID-only task; role checks, tenant isolation, strict schemas, audit metadata, and safe failure handling are covered by tests.
- Required focused checks, applicable broader checks, local-stack migration/queued-run validation, and `git diff --check` pass. No Phase 26 dashboard, hosted evaluation, cost/latency observability, CI workflow, or unrelated feature work is added.

## Risks, dependencies, and notes for the implementation agent

- The base evaluation schema exists, but its JSONB fields are not permission for arbitrary payloads. Use closed typed contracts at the loader, runner, service, and response boundaries; add only the smallest database constraints/columns needed for durable identity and idempotency.
- Do not portray deterministic fixture checking as semantic evaluation. Clearly label the structural faithfulness and language-related checks as deterministic regression signals; hosted judging and richer quality metrics come later.
- Logical source keys must be stable across environments. Do not store or expect database UUIDs, object keys, document URLs, excerpts, raw queries, or workflow snapshots in the corpus/results.
- The runner must call the same closed policy logic production paths rely on wherever feasible. A parallel implementation of risk/routing/citation rules will drift and make the quality signal misleading.
- Evaluation execution is asynchronous by architecture, but the core runner must remain pure and independently executable for tests/CI. Keep Celery payloads UUID-only and make duplicate delivery/terminal-run handling deterministic.
- Preserve the existing user-owned `AGENTS.md` worktree modification. This is plan-only work: do not mark the roadmap/progress complete or modify source code. At a later `I 25` turn, run the worktree baseline gate before implementing.
