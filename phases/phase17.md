# Phase 17 — Intake Graph

## Phase objective

Implement the first real LangGraph business workflow: Intake. Starting from a
tenant-scoped case, it must validate the input, detect Norwegian Bokmål or
English, classify case type and domain, detect PII and prompt-injection
signals, produce a preliminary risk estimate, choose a suggested next
workflow, and persist an inspectable intake result.

The workflow must run through the Phase 16 orchestrator runtime, persist its
node/run lifecycle and model accounting, log safe audit decisions, and give an
authorized user a truthful way to correct a low-confidence classification
before later workflows consume it. The graph must be deterministic under test
and must never automatically dispatch a later Evidence, Extraction, Drafting,
Risk, or Approval workflow.

```text
case submission
      |
      v
validated Intake graph
  validate -> detect language -> classify -> PII/injection signals
      -> preliminary risk -> suggest workflow -> persist result
      |
      +-- low confidence --> user correction --> audited corrected result
      |
      +-- high confidence --> persisted recommendation only
```

## How this phase fits the final product

FR-AGENT-001 requires deterministic, typed, inspectable workflows with
persisted state and logged runs. FR-AGENT-002 specifically requires intake
classification to determine language, case type, domain, priority/risk, PII,
suggested workflow, and human-approval requirement, with low-confidence
results flagged for correction. FR-AGENT-006 requires risk signals before
final output, while FR-AUDIT-001 requires workflow and risk decisions to be
traceable without exposing sensitive inputs.

Architecture §7.2 defines the required Intake nodes. Phase 17 implements that
graph and the minimal executable/API/UI path needed to make the roadmap's
user-correction requirement real. It consumes the Phase 16 runtime rather
than embedding orchestration logic in FastAPI or Celery. It produces a
**preliminary intake assessment**, not the final compliance/risk decision
owned by Phase 21.

| Dependency | What Phase 17 uses | What remains later |
| --- | --- | --- |
| Phase 8/9 cases | Tenant-safe case records, lifecycle policy, Case Detail, localized client/API patterns | General case workflow redesign or unrelated Case Inbox work. |
| Phase 10–15 documents/retrieval/RAG | Existing case/document identifiers and source-safe persistence conventions only | Reading documents, retrieval/evidence, RAG answering changes, citation work. |
| Phase 16 foundation | Typed state, LangGraph runtime, model/prompt/tool/persistence ports, deterministic provider, safe snapshots | Changes to the generic runtime or a second graph framework. |
| Phase 21/22 | Future final risk/approval record models and statuses | Final risk policy, approval queue, interrupts, reviewer decisions, final-output edits. |

## Relevant constraints and decisions

- The Intake graph is the only business graph in this phase. Implement it as a
  dedicated `agent_orchestrator.graphs.intake_graph` plus narrow graph-owned
  node modules. Do not add dormant evidence, extraction, drafting, risk,
  approval, LangMem, or evaluation graph code.
- Start the graph through a closed, authenticated API operation and execute it
  as a Celery background task. The HTTP request persists/queues a workflow run
  and passes only the run UUID to the broker; the worker reloads all case/user/
  prompt state tenant-safely. Long-running model work must not occupy the API
  request lifecycle.
- The first supported workflow request is exactly `intake`. Do not expose a
  caller-selected graph name, arbitrary provider/model/prompt/tool, raw graph
  state, node name, retry setting, or queue payload. Keep the architecture's
  future workflow route shape honest by rejecting any unsupported workflow
  value.
- Input comes from the active case owned by the run's organization, not from a
  browser-provided duplicate title/description, attachment text, source
  excerpts, or model prompt. Validate again at worker execution time so a
  deleted/archived/cross-tenant/stale run fails safely.
- Reuse the existing deterministic `detect_language` helper for only `nb`,
  `en`, or `unknown`, with a deterministic seed and configured
  minimum-character/confidence values. Do not translate input or claim a
  language detection result is perfect.
- `domain` is a closed product-domain choice (`public_sector`,
  `banking_compliance`, `energy_operations`, `internal_policy`). The
  classifier may recommend a domain, but the submitted domain remains available
  as input context and the graph must not write arbitrary model text into the
  database.
- Define a closed case-type taxonomy suitable for the listed product use
  cases—at minimum `case_support`, `compliance_review`,
  `operational_incident`, `policy_question`, `document_intelligence`, and
  `unknown`—rather than accepting a free-form model string. Document any
  final labels in the API/UI copy and tests.
- Use a typed structured classifier output validated after the model boundary:
  `case_type`, recommended domain, classification confidence in `[0, 1]`, and
  a bounded closed rationale/reason-code list. Do not persist model chain of
  thought, raw rationale prose, input text, prompt, or provider body.
- PII and prompt-injection detection are conservative **signals**, not proof
  or final policy verdicts. Implement transparent deterministic, bounded rules
  for the safe synthetic test corpus (for example email/contact, Norwegian
  national-identifier-like, and direct instruction-override patterns). Return
  only boolean presence and closed category/signal codes; never store matched
  text, spans, or personal values in logs/audit/snapshots.
- Preliminary intake risk is a pure policy based only on Phase-17 signals:
  submitted priority, language/classification confidence, PII signal,
  prompt-injection signal, and the closed selected/recommended domain/case
  type. It must return only `low`, `medium`, `high`, or `critical` plus closed
  reason codes. Label it preliminary everywhere. It must not assess evidence,
  contradictions, policy conflicts, high-impact final action, required
  sources, or final approval eligibility; those belong to Phase 21.
- Workflow selection produces a closed recommendation for a later workflow
  (for example `evidence`, `extraction`, `evidence_then_draft`, or
  `manual_review`) and a reason code. It must **not** invoke, enqueue, or
  pretend to have implemented that later workflow.
- The graph sets an `approval_required` **preliminary intake flag** from the
  intake policy, only to inform subsequent routing. It neither adds an
  approval row nor changes case status to `waiting_for_human_review`; Phase 21
  and Phase 22 own final approval requirements and state transitions.
- Do not alter a case lifecycle status simply because Intake has completed.
  The current lifecycle has no dedicated classification-review state, and
  premature automatic status changes would silently add later workflow
  semantics. A later orchestrator phase may use the persisted recommendation
  to choose explicit state transitions.

## Existing repository baseline to verify before implementation

- Phase 16 must be complete and its tests passing. Reuse its runtime,
  safe-snapshot serializer, persistence adapter, prompt loader, provider
  factory, and deterministic test provider; do not fork equivalent helpers in
  `apps/api`.
- `apps/api/src/app/db/models/case.py` already has mutable `case_type`,
  `domain`, and `risk_level` fields. It has no durable PII, injection,
  suggested-workflow, confidence, or classification-source columns.
- `workflow_runs.state_snapshot` and `workflow_node_runs` are the intended
  bounded run-owned persistence for Intake-specific signals/recommendation;
  `WorkflowRun` itself already carries the protected organization/case/actor
  relationship. Do not add raw input fields or an unscoped intake table.
- `apps/api/src/app/services/documents/parsers/language.py` supplies a narrow,
  deterministic `nb`/`en`/`unknown` detector. Reuse it through a small port or
  API adapter rather than importing FastAPI/SQLAlchemy concerns into the graph
  core.
- Existing `CaseUpdateRequest` intentionally does not expose arbitrary
  `case_type`/risk changes. A narrowly scoped intake-correction command is
  therefore required; do not weaken general Case PATCH to accept engine-owned
  risk fields or free-form classification values.
- `apps/api/src/app/workers/tasks.py` already demonstrates the established
  Celery pattern: UUID-only payload, short-lived async session, explicit async
  engine disposal after `asyncio.run`, bounded retry, and content-free logs.
  Follow that pattern for the Intake task rather than adding a second worker
  process.
- The Case Detail UI has truthful workflow/risk placeholders from Phase 9.
  Replace only the necessary intake portion with real data/action/correction
  controls; keep unrelated future panels clearly unavailable.

## In scope

### 1. Intake graph and typed node contracts

Implement a compiled LangGraph Intake graph with these explicit nodes in the
defined order and typed state transitions:

1. `validate_case_input`
2. `detect_language`
3. `classify_case_type`
4. `detect_pii`
5. `detect_prompt_injection`
6. `estimate_risk`
7. `choose_workflow`
8. `persist_intake_result`

The graph start/end routing must be visible in code and graph tests. Nodes have
one responsibility, return only validated state updates, and report a
controlled node failure through the Phase 16 runtime. The graph must not hide
node sequencing inside a broad service function.

Define closed Pydantic domain types for:

- detected-language result and confidence/unknown state;
- case-type/domain classification and low-confidence marker;
- PII categories and prompt-injection signal categories;
- preliminary risk level/reason codes and preliminary approval flag;
- suggested workflow/reason code; and
- persisted intake result / correction source (`model` or `human_corrected`).

Keep raw case title/description as transient server-loaded node input only.
Never put it in graph snapshots, node summaries, audit rows, queue arguments,
API response fields beyond the existing protected case detail, or normal test
fixtures/log output.

### 2. Deterministic input, classification, PII, injection, and risk policy

- Validate that the run references a current, non-archived case and initiating
  user in the run organization. Recheck title/description bounds after safe
  normalization and reject corrupted/unusable persisted input with a
  controlled `invalid_case_input` result.
- Adapt the existing language detector behind a graph port. Store language
  result/confidence as an intake output; retain the submitted case language as
  a distinct declared value and flag—not overwrite silently—when it disagrees
  with a sufficiently confident detected language.
- Load a server-owned active `intake_classification` prompt through the Phase
  16 loader. Call the Phase 16 provider with a typed, bounded classifier
  schema. The selected provider/model and prompt metadata stay server-owned.
  If an active prompt is unavailable or the classifier result is invalid,
  finalise the run safely; never use a generic answer, a free-form fallback, or
  outside knowledge.
- Implement pure rule modules for PII and injection signals. Use clearly named
  regex/normalization limits, test them with safe synthetic strings, and report
  only closed signal category codes/counts. A potential match should favor a
  safe signal/low-confidence route; it must not remove or rewrite the case
  body and must not expose the match.
- Implement a pure, table-driven preliminary risk policy. Its inputs/outputs
  must be explicit and unit-tested for every branch. Include `low_confidence`,
  `pii_detected`, `prompt_injection_detected`, and high/urgent priority in the
  reason-code policy where applicable. Do not add a model call for risk
  scoring.
- Implement a pure deterministic suggested-workflow mapping. It should include
  a safe `manual_review`/`unknown` outcome for unclear or potentially unsafe
  classifications. It must not call retrieval or enqueue a successor graph.

### 3. Durable results, audit trail, and low-confidence correction

On a successful run, persist the result through the Phase 16 ports/adapters:

- Write the allowed Intake result to the `WorkflowRun` safe state snapshot:
  state-schema/version, terminal status, declared/detected language labels,
  classification case type/recommended domain, low-confidence boolean,
  signal booleans/category codes, preliminary risk/reason codes,
  preliminary-approval boolean, suggested-workflow/reason codes, and whether
  the final classification source is model or human correction. Do not store
  confidence numeric values, text excerpts, match content, model request/
  response, or raw error.
- Persist safe node summaries and timing/retry data via `WorkflowNodeRun` so
  Phase 23 can later expose an honest trace. A model invocation also persists
  `ModelUsageRecord` with provider/model/prompt version/accounting metadata
  through the Phase 16 contract; no provider body or prompt content is stored.
- Update the case's `case_type`, `domain`, and preliminary `risk_level` only
  after a completed, valid **high-confidence** classification according to the
  server threshold. For a low-confidence model result, retain submitted case
  values as the current case fields and store the recommendation in the Intake
  result for human correction. Never update these fields from unvalidated
  model output.
- Append content-free audit events for workflow queued/started/completed/failed
  and correction recorded. Use event type names such as
  `workflow.intake_queued`, `workflow.intake_started`,
  `workflow.intake_completed`, `workflow.intake_failed`, and
  `workflow.intake_classification_corrected`; use the run as resource and
  case/actor references where appropriate. Event metadata may contain only
  workflow name, terminal status, boolean signals, low-confidence flag, closed
  labels/reason codes, and count/availability indicators—never raw input,
  confidence/score, PII values, prompts, source ids, tokens/cost values, model
  payloads, exceptions, or credentials.
- Add a narrow intake-correction command that an authorized case user can use
  only for the current tenant's latest completed low-confidence Intake run. It
  accepts only a closed case type and closed domain plus an optional bounded
  non-sensitive reason code (not free text), validates authority and workflow
  status, updates `cases.case_type`/`domain`, marks the Intake snapshot's
  classification source `human_corrected`, and emits the correction audit
  event. It does not let a user set risk level, PII/injection flags,
  provider/prompt, suggested workflow, or approval result.
- A correction must be transactionally consistent with its audit event and run
  snapshot update. It must never mutate a foreign-tenant, archived, non-Intake,
  failed, or high-confidence run; return the established tenant-safe not-found
  or neutral conflict/error response as appropriate.

### 4. Closed API and background-worker path

Add the smallest honest operational surface necessary to start/poll/correct the
first graph. Keep contracts closed and documented in OpenAPI:

| Operation | Required behavior |
| --- | --- |
| `POST /api/cases/{case_id}/workflows/run` | Cookie-authenticated, current-tenant case operation accepting exactly `{ "workflow": "intake" }`. It authorizes a user allowed to read/operate on the case, adds a queued run, records a safe queue audit event, and dispatches only its UUID. It rejects unsupported future workflow values and never accepts state, provider, prompt, model, tool, or queue controls. |
| `GET /api/workflows/{workflow_run_id}` | Cookie-authenticated, tenant-scoped, safe status/result view for the current user's readable case. It returns run id/name/status/timestamps plus the allowlisted Intake result needed for a real Case Detail, never raw state snapshot, node inputs/outputs, model data, or error internals. Full trace remains Phase 23. |
| `POST /api/workflows/{workflow_run_id}/intake/correction` | Cookie-authenticated, closed correction request for the latest low-confidence completed Intake result as described above. No generic workflow mutation endpoint. |

Use a narrowly named dispatcher and Celery task, accepting a UUID string only.
The worker must claim/reload the queued run, make duplicate delivery harmless,
run the graph, and use the Phase 16 persistence runtime. Follow the existing
document-task error/retry/engine-disposal pattern and bounded retry settings.
If publish fails after run persistence, record a safe failure/dispatch outcome
or return a neutral availability error; do not leave a successful HTTP response
claiming a workflow is running when it cannot be dispatched. Add a bounded
reconciliation path only if needed to guarantee recovery of queued Intake runs;
do not build a generic scheduler.

Do not add cancel, arbitrary rerun, trace, generic graph-inspection, approval,
or evaluation endpoints.

### 5. Minimal truthful Case Detail intake UI

Implement only the UI required for a real authorized user to observe and
correct low-confidence Intake output:

- Add typed same-origin API-client contracts for the closed run/status and
  correction endpoints. Cookies remain HTTP-only; the browser must neither
  read/store a token nor retain case/graph data in local storage.
- Add a localized Bokmål-first/English Intake section on the existing Case
  Detail page. It may offer the intake start action only to roles permitted by
  the backend, display queued/running/complete/failed safely, and show
  allowlisted language, case-type/domain recommendation, preliminary risk,
  low-confidence indicator, PII/injection signal presence, suggested next
  workflow, and human-correction state. Do not render raw node output,
  prompts, matched PII/injection content, provider errors, or confidence
  numeric values.
- When an Intake result is low confidence, show an accessible correction form
  using closed case-type/domain selects and a bounded reason-code select. On
  success, refresh truthful data and show the recorded human correction. For a
  high-confidence result, do not expose an edit control that pretends to
  override final risk/approval decisions.
- Provide semantic headings, labels, descriptions, keyboard operation,
  non-color-only state, loading/queued/error/empty states, and localized safe
  error messages. Keep future Evidence, Extraction, Drafting, Approval, and
  Trace placeholders explicitly unavailable.
- A simple polling/refetch strategy is allowed only while an owned Intake run
  is queued/running, with bounded interval/cleanup and no streaming/WebSocket
  addition. Browser testing must be deterministic using API mocking or the
  deterministic worker/model path.

### 6. Configuration, seed/test fixtures, and documentation

- Add validated Intake-specific non-secret settings through the Phase 16 agent
  configuration: classifier operation/prompt name (server-owned constant),
  low-confidence threshold, language detector bounds, PII/injection input
  bounds, worker dispatch/retry/lease values, and bounded UI polling values if
  configuration is actually necessary. Preserve provider secrets as
  `SecretStr`; do not add actual secrets to `.env.example`.
- Add only safe synthetic test fixtures. Include Norwegian and English case
  examples, clear low-confidence/unknown classifications, non-sensitive
  email/phone/national-identifier-like strings, and injection-like strings.
  No real national IDs, personal data, screenshots, or provider outputs belong
  in source control.
- Update README/development/API notes only after endpoint names, worker
  behavior, deterministic setup, and correction semantics are verified. State
  accurately that this is preliminary intake routing and not final risk,
  approval, or full workflow trace capability.

## Out of scope

- Evidence Graph implementation, retrieval invocation, query rewriting,
  reranking, source filtering, evidence sufficiency, contradiction checks, or
  `needs_more_evidence` routing (Phase 18).
- Extraction, source-linked fields, drafting, citations, unsupported-claim
  checks, human final-text edits, final risk assessment, approvals,
  interrupts/resume, or workflow reassignments (Phases 19–23).
- Prompt management UI/API, model administration, changing provider factory
  design, generic tool calls, document parsing/PII scanning, LangMem, external
  integrations, evaluation framework/dataset, cost dashboard, or trace UI.
- Automatic run of a selected future workflow; the recommendation is data only.
- General Case PATCH changes that expose engine-owned risk/classification
  fields, arbitrary free-text corrections, status automation, generic workflow
  execution, raw-state download, cancellation, streaming, or WebSockets.
- Replacing direct RAG answering, altering approved-source governance, or
  changing the Phase 15 API behavior.
- Roadmap/progress completion edits while generating this plan.

## Likely files and ownership

| Area | Likely files | Responsibility in this phase |
| --- | --- | --- |
| Intake graph core | `services/agent_orchestrator/src/agent_orchestrator/graphs/intake_graph.py`, `nodes/intake/**`, `state/**`, `prompts/**` | Typed graph, pure policies/detectors, graph-owned contracts, no HTTP/ORM/Celery imports. |
| Phase 16 core extension | `config.py`, `types.py`, `graphs/runtime.py`, `persistence/ports.py`, provider/prompt contracts | Intake settings/composition hooks only; preserve Phase 16 generic boundaries. |
| API adapters/services | `apps/api/src/app/services/workflows/**`, narrow case/workflow/prompt repository additions | Tenant-safe input loading, persistence, dispatch, correction command, API composition. |
| API routes/schemas | `apps/api/src/app/api/routes/workflows.py`, a new focused workflow schema module and route registration if needed | Closed start/status/correction contracts and OpenAPI cookie security. |
| Worker | `apps/api/src/app/workers/tasks.py`, focused dispatch helper | UUID-only Intake task, bounded retry/claim/reconciliation where required, loop-safe disposal. |
| Web | `apps/web/src/lib/api/**`, `apps/web/src/app/[locale]/cases/[caseId]/**`, focused components/messages/tests | Localized, accessible truthful Intake display/start/correction; no broad workflow console. |
| Tests/fixtures | agent unit/graph tests; API unit/integration/API tests; web component/Playwright tests; safe sample fixtures | Offline deterministic behavior, tenant/RBAC/audit/persistence, UI accessibility and correction flow. |
| Config/docs | `.env.example`, relevant API/development/testing docs, `uv.lock` only if new direct deps are required | Secret-safe configurability and accurate operational instructions. |

## Implementation tasks

1. Verify Phase 16 completion and read its actual public contracts before
   editing. Inspect current Case service/policy, workflow repository, worker
   task patterns, Case Detail API client, and translations to avoid duplicate
   ownership or accidental route semantics.
2. Define the Intake result taxonomy, closed classifier schema, signal/reason
   enums, low-confidence threshold, and pure policies. Write table-driven unit
   tests for classification validation, PII/injection signal detection,
   preliminary risk, and suggested-workflow mapping before graph wiring.
3. Implement the eight graph nodes and compiled routing through the Phase 16
   runtime. Bind server-loaded case input and active prompt/provider ports;
   ensure every node emits only a safe typed update/summary.
4. Implement durable completion/failure writes, model-usage linkage, and safe
   audit events. Add scoped case update and low-confidence correction services
   with one transaction per logical mutation.
5. Add the closed API schemas/routes and UUID-only worker dispatch/task. Test
   authorization, tenant isolation, double delivery/idempotence, broker
   failure, persistence failure, and safe worker lifecycle without a real
   provider call.
6. Add the narrow Case Detail Intake panel and correction form with Bokmål and
   English messages, accessible states, and typed API client behavior. Keep all
   unrelated product placeholders honest.
7. Add integration/API/browser coverage, update configuration/docs after exact
   behavior is established, then run full static, automated, and local-stack
   validation.

## Required tests

### Intake policy and graph tests

- Norwegian Bokmål and English synthetic cases return deterministic detected
  language results; short/ambiguous input produces `unknown`/low-confidence
  behavior without translation.
- The classifier accepts only the declared structured taxonomy, rejects blank,
  out-of-range, unknown-domain/type, extra-field, and malformed deterministic
  provider output, and never persists a free-form response.
- PII fixtures detect supported safe categories without retaining matched text;
  clean text remains unflagged. Injection-like fixtures add the expected
  signal codes without treating source text as executable instruction.
- Every preliminary risk-policy branch and suggested-workflow mapping is
  table-tested, including priority, PII, injection, unknown language, low
  confidence, and safe manual-review fallback.
- Graph ordering is exactly the documented eight nodes. A valid run persists
  typed result/safe node summaries; a prompt/model/input/node failure finalizes
  safely with a controlled code, bounded retry behavior, and no raw content.
- Deterministic provider runs are stable and offline. Tests explicitly verify
  no evidence/retrieval/drafting/approval graph is invoked or queued.

### API, persistence, worker, and audit tests

- Start endpoint requires a valid cookie/session and permitted role; unauthenticated
  requests get 401, unauthorized roles get 403, foreign/missing/archived cases
  remain tenant-safe 404, and unsupported workflow values/extra fields get
  closed validation errors.
- Queue dispatch receives only the run UUID. The worker reloads tenant-scoped
  data, handles duplicate delivery without duplicate terminal records, uses
  bounded retries, disposes loop-bound engines, and records a safe failure when
  dispatch/model/persistence fails.
- A completed high-confidence run updates only the allowed Case fields and
  preserves submitted case values for a low-confidence run. No Intake path
  changes case status, adds an approval, or launches a successor graph.
- Result/status endpoint exposes only allowlisted values. It never returns raw
  state snapshot, node summary contents beyond designed result fields, case
  input, prompt, provider payload, confidence score, token/cost, or raw error.
- Correction accepts only the closed values, is allowed only for the latest
  current-tenant low-confidence completed Intake run, is atomic with case/run/
  audit writes, and rejects foreign/stale/high-confidence/failed/non-Intake
  runs without information leakage.
- Audit rows exist for queued/started/completed/failed/corrected outcomes,
  link the correct tenant/case/actor/run, contain only approved metadata keys,
  and reject attempts to insert raw case text, PII, confidence, prompts,
  provider output, tokens/cost, or exceptions.
- Existing direct RAG retrieval/answer tests, Case tests, auth/RBAC tests, and
  the Phase 16 runtime test suite remain green.

### Frontend and end-to-end tests

- Bokmål is the default and English translations cover Intake start, queued,
  running, completed, failed, low confidence, PII/injection signal presence,
  suggested workflow, and correction labels/errors.
- Case Detail renders only safe Intake result data with semantic headings,
  labelled form controls, keyboard operation, visible focus, non-color-only
  indicators, and loading/empty/error states.
- A low-confidence response enables only the closed correction form; successful
  correction refreshes display and an inaccessible/high-confidence result does
  not show the control.
- Playwright covers synthetic login, opening a case, starting the deterministic
  Intake workflow, observing final/polling state, recording a correction, and
  confirming the updated truthful Case Detail. It must use no real provider
  credential and must not persist browser tokens or emit sensitive artifacts.

## Validation steps

Run the commands that exist after implementation, including focused suites and
the full repository checks:

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
```

Perform one manual synthetic-only local flow after the stack is running:

1. Open `http://127.0.0.1:3000/nb/cases` and sign in with a locally provisioned
   synthetic authorized user; do not paste/display its password or session.
2. Open a synthetic Case Detail and run Intake. Confirm it shows a queued then
   terminal truthful Intake state without exposing raw case/prompt/model data.
3. Use a low-confidence fixture/case, record a closed case-type/domain
   correction, reload the page, and confirm the correction is visible.
4. In `http://127.0.0.1:8000/docs`, inspect the cookie-secured closed workflow
   contracts. Confirm there is no generic graph control, trace payload, or
   approval action.
5. Query only safe metadata through the local database if needed, then exit
   `psql` with `\q`; do not print case descriptions, PII test strings, prompts,
   cookies, or provider configuration.

Run `git diff --check` before reporting completion. If a real model credential
is unavailable, the deterministic test/manual path is required and sufficient
for this phase's functional validation; report that no live-provider quality
claim was made.

## Completion criteria

- The only implemented business graph is Intake, with eight explicit typed
  nodes and Phase 16 runtime/persistence integration.
- A permitted user can start Intake asynchronously for a readable current-
  tenant case, observe a safe terminal result, and correct a low-confidence
  classification using closed values; all browser authentication remains
  HTTP-only-cookie based.
- Valid results persist safely; high-confidence results update only allowed case
  classification fields, while low-confidence recommendations await human
  correction. No automatic case-status change, successor graph, final risk,
  or approval is added.
- PII/injection and preliminary risk outputs are conservative, typed, audited
  signals with no raw sensitive content stored in state, logs, queue payloads,
  audit records, responses, or test artifacts.
- Worker, API, persistence, audit, graph, component, and Playwright tests pass
  offline through deterministic model support; all full static/local-stack
  checks pass.
- Documentation accurately calls the result preliminary and lists no
  unimplemented graph/risk/approval capability as complete. Only then may a
  later implementation turn mark Phase 17 `(DONE)` in the roadmap and progress
  file.

## Risks, dependencies, and implementation notes

- **Phase-16 dependency:** do not start against an assumed orchestrator API.
  Verify its final port/type names and adapt the plan's ownership, not its
  safety constraints, to the completed foundation.
- **Classifier reliability:** structured output is not certainty. Use the
  threshold and closed schemas, surface low confidence, preserve original case
  data until correction, and never use a model's free-text rationale as durable
  truth.
- **PII/privacy risk:** pattern matching can over/under-detect. Treat output as
  a conservative signal, use only synthetic fixtures, store category flags not
  values, and leave final policy to Phase 21.
- **Prompt-injection risk:** detector matches are also signals. Never execute
  instructions inside case text; no tool/retrieval/model configuration is ever
  selected by input text.
- **Worker reliability:** broker publish and duplicate delivery need bounded,
  observable behavior. Reuse established UUID-only and engine-disposal patterns
  instead of building an untested generic workflow queue.
- **UI scope:** only the Intake portion of Case Detail becomes real. Do not let
  a useful correction form turn into an unplanned generic workflow console.
- **Status semantics:** current Case statuses do not express intake review.
  Preserve them until a later phase explicitly owns orchestration routing.

## Notes for the implementation agent

- Treat this plan as the authoritative Phase 17 scope after confirming Phase
  16's delivered contracts. Keep core graph nodes pure/testable and place SQL,
  HTTP, Celery, and React adaptation at the edges.
- Use the existing safe audit/error/tenant patterns; never solve a workflow
  observability need by dumping graph state or exceptions into JSON.
- Prefer explicit closed enums and mapping tables over clever model prompts or
  hidden heuristics. A deterministic test model proves integration, not model
  quality.
- Do not mark the phase complete until automated tests, the synthetic local
  flow, migration/status check, and local-stack verification have passed.
