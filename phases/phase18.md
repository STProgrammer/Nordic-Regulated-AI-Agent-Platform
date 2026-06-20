# Phase 18 — Evidence Graph

## Phase objective

Deliver the first source-gathering LangGraph workflow: a tenant-safe, asynchronous Evidence Graph that turns a server-owned case question/context into a persisted, ranked evidence package. It must compose the existing hybrid retrieval service, evaluate sufficiency and contradictions, route weak or contradictory results to `needs_more_evidence`, and give an authorized user a truthful Evidence section on Case Detail.

This phase makes sources inspectable before any later extraction or drafting work. It does **not** produce an answer, draft, final risk assessment, approval, or workflow trace.

## Relevant context and constraints

- The roadmap requires these explicit nodes: `rewrite_query`, vector and keyword candidate retrieval, merge, rerank, permission filtering, source-status checks, evidence sufficiency, contradiction detection, and persistence. Weak or contradictory evidence must route to Needs More Evidence.
- Phase 13 already supplies tenant-scoped hybrid retrieval, deterministic query rewriting, candidate merging, source governance, and access controls. Phase 15 already has narrow evidence/citation utilities for direct RAG answers. Reuse or carefully extract these server-owned primitives; do not fork their ranking, permissions, or source-status policies.
- Phase 16 supplies the typed LangGraph runtime, finite retry behavior, default-deny snapshots/node summaries, provider/prompt ports, model-usage persistence, and the UUID-only workflow execution pattern. Phase 17 supplies the only current workflow start/status/worker/UI path. Extend its closed contracts deliberately rather than introducing a generic graph console.
- The architecture assigns `retrieved_sources` to a workflow run and requires all workflow state to be typed. The safe workflow projection must contain only status, bounded counts, boolean/closed reason indicators, citation labels, and explicitly designed presentation data. It must not contain raw case text, prompt/model payloads, unrestricted scores, provider errors, credentials, or a raw node trace.
- The PRD requires sources to be visible before final output approval, including governed-source warnings and source context. Norwegian Bokmål remains the default UI language; English remains available; authorization is enforced by the API, never by UI visibility alone.
- A dirty worktree may contain Phase 16–17 implementation changes. Preserve unrelated work. This plan does not mark roadmap/progress entries complete.

## In scope

1. A compiled, typed Evidence Graph with the ten roadmap nodes and explicit terminal outcomes: `completed`, `needs_more_evidence`, and controlled `failed`.
2. Server-owned query construction/rewrite, hybrid retrieval, merge/rerank, tenant and readable-case filtering, source-governance filtering, sufficiency and contradiction policy.
3. Durable, tenant-scoped Evidence runs, node lifecycle records, retrieved-source provenance, safe evidence-package state, model usage when a provider is actually used, and content-free workflow audit events.
4. Closed API/worker operations to start and read the Evidence workflow for an authorized case, including a safe result response that contains only the designed evidence package.
5. A localized, accessible Case Detail Evidence Graph section that shows its truthful run state, evidence result/reasons, governed source warnings, citation labels, and existing safe source-context access.
6. Deterministic fixtures, graph/unit/integration/API/web coverage, configuration documentation, and full local validation.

## Out of scope

- Extraction fields and field editing (Phase 19).
- Draft text, citation validation for a generated answer, unsupported-claim review, human text edits, final output, or approvals (Phases 20–22).
- Final risk/approval policy, a generic workflow router, automatic successor-graph execution, cancellation, resumption, streaming/WebSockets, or the Phase 23 trace endpoint/UI.
- Changing Phase 15's direct `/api/retrieval/answer` semantics, weakening its approved-source rules, or exposing a browser-controlled retrieval provider, prompt, query, score, source status, or document-id filter.
- Prompt-management/model-administration surfaces, LangMem, evaluation, exports, observability dashboards, and production hardening.

## Likely files and ownership

| Area | Likely files/folders | Phase-18 responsibility |
| --- | --- | --- |
| Evidence graph core | `services/agent_orchestrator/src/agent_orchestrator/graphs/evidence_*.py`, `state/**`, `prompts/**` | Typed state/result/contracts and ten pure-orchestrated nodes; no FastAPI, SQLAlchemy, or Celery imports. |
| Retrieval adapter boundary | `services/agent_orchestrator/.../persistence/ports.py`; narrow adapters beside `app.services.workflows` and `app.services.retrieval` | Adapt existing trusted hybrid retrieval and persistence behind typed ports; keep tenant scoping at the API edge. |
| Workflow/domain services | `apps/api/src/app/services/workflows/{service,dispatch,orchestrator}.py`, a focused `evidence.py`; workflow/retrieval repositories as required | Closed start/read policy, claim/idempotence, terminal persistence, case-state transition, and audit records. |
| API/worker | `apps/api/src/app/api/routes/workflows.py`, `schemas/workflows.py`, `workers/tasks.py`, `workers/celery_app.py` | Closed `evidence` operation, safe discriminated status/result response, UUID-only task dispatch, bounded retry/disposal. |
| Persistence | Existing workflow models/repositories; Alembic only if the existing columns cannot represent required provenance safely | Reuse `WorkflowRun`, `WorkflowNodeRun`, and `RetrievedSource`; do not migrate merely to store raw graph state. |
| Web | `apps/web/src/components/evidence/**`, `components/cases/case-detail.tsx`, `lib/api/{workflows,contracts}.ts`, messages and tests | Replace only the Evidence placeholder/on-demand surface needed for the truthful graph result; retain safe source context. |
| Tests/docs | Agent/API/web tests, `.env.example`, README/development/API docs | Offline deterministic coverage and accurate operational instructions. |

## Implementation tasks

1. **Confirm the prerequisite contracts.** Read the final Phase 16–17 runtime, workflow status response, dispatcher/task, Case policy, retrieval service/types/policies, direct-RAG evidence helpers, persisted-source model, Evidence Panel, translations, and test conventions. Record any final names that differ from this plan; preserve the contracts below.
2. **Define closed Evidence contracts first.** Add typed state/result models for rewritten-query metadata, candidate counts, ranked source references, citation labels, sufficiency outcome/reason codes, contradiction signal/reason codes, and terminal routing. State and snapshots must be allowlisted and bounded. Input case text/question is transient server-loaded input, never durable graph state. Use a server-owned Evidence query strategy based on allowed case context; do not accept client prompt/query/retrieval controls.
3. **Implement the ten explicit nodes.**
   - `rewrite_query` uses the existing deterministic/provider abstraction through a fixed operation and active prompt, with a safe fallback and bounded output.
   - `retrieve_vector_candidates` and `retrieve_keyword_candidates` call trusted retrieval ports under the run's organization/case/principal context.
   - `merge_candidates` reuses the current deterministic merge rules; `rerank_sources` uses a deterministic, server-owned bounded policy or a structured provider only through the Phase-16 port.
   - `filter_by_permissions` and `check_source_status` must be defense in depth: retrieval adapters enforce them before candidate exposure, and the graph rejects any non-readable/non-approved candidate. Explicitly decide and test whether deprecated sources are excluded or retained as warnings; restricted/archived and foreign sources must never become evidence.
   - `evaluate_evidence_sufficiency` uses deterministic configured source/count/content bounds. `detect_contradictions` uses a documented bounded, deterministic or structured schema policy whose output is only closed flags/reason codes—not free-form rationale. `persist_evidence` is the sole node that writes the completed package.
4. **Persist atomically and route safely.** Create one `workflow_name="evidence"` run with a version and a safe queued snapshot; use the generic runtime/node lifecycle. At completion persist ranked approved `RetrievedSource` records with stable run-local citation labels and bounded excerpts, plus an allowlisted Evidence result. A sufficient non-contradictory package completes. Weak or contradictory evidence finalizes the run with an explicit safe outcome and transitions the case to `needs_more_evidence` only through the existing Case transition policy and an atomic audit write. Do not overwrite an independent human case outcome or launch a later graph. Failed execution must not look completed or alter case status.
5. **Add the narrow execution/API path.** Extend the existing case workflow start request with exactly the closed `"evidence"` option (or an equally closed dedicated command if final Phase-17 design makes that safer). It must authorize an appropriate current-tenant case user, validate that the case is eligible, prevent conflicting active Evidence runs, create/dispatch only a UUID, and return a safe run projection. Extend `GET /api/workflows/{id}` with a discriminated allowlisted Evidence result; it must never expose raw state, rewritten query, node bodies, source query, model details, scores, exceptions, or foreign runs. Keep the existing Intake correction endpoint Intake-only.
6. **Add the dedicated worker execution.** Build a named Evidence task that reloads a run and all transient inputs after claiming it. It must be idempotent on duplicate delivery, honor bounded configured retries, dispose loop-bound engines, and record a neutral safe terminal failure if queue/model/persistence work fails. No task accepts state, retrieval parameters, source IDs, or a provider configuration from the queue.
7. **Make Case Detail truthful.** Add typed client contracts and a localized Bokmål/English Evidence Graph panel. A permitted user can start the closed Evidence run, see queued/running/completed/needs-more-evidence/failed states, and inspect only persisted sources/labels, status warnings, sufficiency/contradiction presence, and a safe reason category. Reuse the existing accessible source-context dialog. Do not render provider rationale, raw rewritten query, numeric score/confidence, raw errors, a user-adjustable retrieval form, or false downstream Draft/Approval controls. Poll only while an owned run is active, with cleanup and a bounded interval.
8. **Document only verified behavior.** Add non-secret bounds/settings only where needed; deterministic local/test execution must remain the supported validation path. Update developer/API docs after route, state, and case-transition behavior are proven.

## Required tests

### Graph and policy tests

- Node ordering is exactly the ten roadmap nodes; typed state rejects unknown fields, malformed/oversized rewrite/rerank/contradiction output, and raw-content snapshot additions.
- Synthetic Norwegian and English cases produce stable bounded server-owned queries without a network call in deterministic mode.
- Vector and keyword candidate paths, merge de-duplication, stable tie-breaking, rerank bounds, source-status behavior, permission filtering, and foreign-tenant denial are separately tested.
- Empty, too-short, insufficient-count, and contradictory evidence route to the correct `needs_more_evidence` outcome/reason; sufficient mutually compatible approved evidence completes.
- Injection-like document text remains untrusted reference content; it cannot alter graph controls, provider/tool selection, or persisted reason taxonomy.
- Controlled provider/retrieval/persistence failures retry only within policy, finalize safely, and never leak input, prompt, source excerpt, model payload, credentials, or exception text into state/node summaries/logs.

### Persistence, API, worker, and audit tests

- An authorized tenant user can start Evidence only through its closed contract. Missing/foreign/archived/ineligible case, anonymous/unauthorized principal, extra fields, and unsupported workflow values receive the established safe response.
- Queue payload contains exactly a run UUID. Duplicate delivery produces no duplicate sources/terminal records; dispatch failure and exhaustion do not claim a running run.
- Persisted `RetrievedSource` rows link the right organization/case/run/document/chunk, use deterministic citation labels, exclude unreadable/governance-blocked sources, and cannot be read cross-tenant.
- Only the intended weak/contradictory outcome transitions an eligible case to `needs_more_evidence`; sufficient/failed runs leave unrelated status handling untouched. Terminal write, source persistence, transition, and audit records are transactionally consistent.
- Status responses expose only the designed Evidence DTO. Regression tests must prove absence of raw snapshot, node inputs/outputs, query text, prompt/provider data, numeric scores, exception text, and Phase-23 trace fields.
- Audit events such as `workflow.evidence_queued`, `workflow.evidence_started`, `workflow.evidence_completed`, `workflow.evidence_needs_more_evidence`, and `workflow.evidence_failed` contain only workflow/status/count/boolean/closed-reason metadata.
- Existing direct-RAG, document/retrieval, Intake, auth/RBAC, Case transition, and workflow-runtime suites remain green.

### Web and end-to-end tests

- Bokmål default and English messages cover start, active, insufficient/contradictory, complete, failed, source status, and safe error states.
- The Evidence panel is keyboard-operable with semantic headings, labelled controls, visible focus, non-color-only outcome indicators, loading/empty/error states, and accessible source-context behavior.
- Mocked/ deterministic API tests prove active polling cleanup, result refresh, safe source rendering, and no local storage/token or raw workflow payload retention.
- Playwright covers synthetic login, Case Detail, a deterministic sufficient Evidence run, safe source inspection, and a weak/contradictory fixture yielding Needs More Evidence. It uses no live provider credential or real personal data.

## Validation steps

Run the applicable focused suites plus the full repository checks after implementation:

```bash
uv run pytest services/agent_orchestrator/tests
uv run pytest apps/api/tests
pnpm test:web
pnpm test:e2e
pnpm format:check
pnpm lint
pnpm typecheck
pnpm check:workspace
pnpm dev:up
docker compose --env-file .env.example exec api uv run alembic current
pnpm verify:local-stack
pnpm dev:down
git diff --check
```

Manual synthetic-only check: sign in at `http://127.0.0.1:3000/nb/cases`, run Evidence for a seeded readable case, confirm safe queued/terminal presentation and source-context access, then use a weak/contradictory fixture to confirm Needs More Evidence. Inspect the cookie-secured closed contracts at `http://127.0.0.1:8000/docs`; do not print passwords, cookies, case text, prompts, or provider values.

## Completion criteria

- The ten-node Evidence Graph runs asynchronously with typed/default-deny state and explicit safe outcomes.
- Ranked, tenant-readable, source-governed evidence is durably linked to its Evidence run with stable citation labels; weak/contradictory evidence safely routes to `needs_more_evidence`.
- Case Detail exposes only the safe Evidence package and source-context path, in accessible Bokmål/English UI; no automatic downstream workflow, drafting, approval, or trace exists.
- Graph, retrieval, persistence, worker, API, audit, web, and E2E tests pass through deterministic fixtures; full static and local-stack validation passes.

## Risks, dependencies, and notes for the implementation agent

- Treat Phase 17 as a hard dependency and adapt to its actual final APIs. Do not assume its currently dirty files are validated or overwrite them.
- Retrieval is security-sensitive. Preserve tenant/case authorization and source governance at every layer; graph-level filtering supplements, never replaces, repository/service policy.
- Contradiction detection is an uncertainty signal, not a final legal/compliance decision. Keep it bounded and explainable through closed reason codes; Phase 21 owns final risk.
- `needs_more_evidence` is a truthful case outcome, but it must not erase human decisions or disguise execution failure. Use the existing transition rules and document any required narrow extension.
- Preserve Phase 15 direct-RAG behavior. Shared utilities may be extracted only with regression coverage proving both workflows retain their distinct contracts.
- Do not mark Phase 18 `(DONE)` or update `specs/progress.md` while generating this plan; that happens only after implementation and validation.
