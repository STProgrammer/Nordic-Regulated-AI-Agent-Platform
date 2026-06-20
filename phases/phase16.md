# Phase 16 — Agent Orchestrator Foundation

## Phase objective

Establish the production-quality foundation on which the later LangGraph
workflows will run. Deliver a typed `agent_orchestrator` workspace package,
LangGraph execution/runtime primitives, a provider-neutral model boundary,
tenant-aware prompt-version loading, a server-owned tool registry, and durable
workflow/node persistence through the existing API data layer.

The foundation must make a graph run inspectable and safe before the project
adds a first real business graph in Phase 17. It must persist a bounded,
redacted state snapshot; record node timing, retry count, and controlled error
summaries; and provide a deterministic local/test model implementation so
automated tests never depend on a provider network call.

This phase deliberately establishes infrastructure, contracts, and a minimal
non-business runtime proof. It does **not** implement the Intake Graph or any
other product workflow.

```text
Phase 15                         Phase 16                         Phase 17
direct RAG answer     ->         orchestration foundation  ->     Intake Graph
one narrow generator             typed graph/runtime,               first real nodes,
and durable RAG records          persistence, model/tool/prompt     classification and
                                 seams, deterministic tests          intake results
```

## How this phase fits the final product

The PRD requires deterministic, inspectable LangGraph workflows with typed
state, explicit transitions, persisted execution, safe model/tool logs, and
human-approval support later (FR-AGENT-001 through FR-AGENT-007,
FR-HITL-002, FR-AUDIT-001/002, and FR-EVAL-003/004). The architecture assigns
those responsibilities to the Agent Orchestrator and defines the durable
`workflow_runs`, `workflow_node_runs`, `agent_messages`,
`model_usage_records`, and `prompt_versions` records already introduced in
Phase 4.

Phase 15 intentionally used a small, RAG-only completion seam and a bounded
`rag_answer` execution record. It is not a LangGraph implementation and must
continue to work unchanged. Phase 16 introduces the reusable provider/runtime
boundary for future graph-owned model calls without migrating or generalizing
the existing direct RAG answer path.

| Existing result | Reuse in this phase | Do not change in this phase |
| --- | --- | --- |
| Phase 4 database foundation | Existing workflow, prompt, model-usage, audit, case, user, and organization tables; tenant composite foreign keys | Schema semantics, migrations, or tenant constraints unless a confirmed blocking defect requires a separately justified migration. |
| Phase 5 service/repository layer | Tenant-safe `WorkflowRunRepository`, `WorkflowRunService`, `AuditService`, transaction/savepoint conventions, and safe error model | Put SQL or business policy in routes or in the standalone agent core. |
| Phase 6 auth/RBAC | Current principal and backend authorization conventions for future entry points | Add workflow endpoints or change role policy before Phase 17. |
| Phase 12–15 ingestion/retrieval/RAG | Existing source records and direct-RAG model generator remain independent consumers/producers of durable records | Rebuild retrieval, change RAG prompts, or route direct answers through LangGraph. |

## Relevant architecture constraints

- Use the existing Python 3.12 uv workspace and the reserved
  `services/agent_orchestrator` package. The package must become a real,
  importable, strictly typed workspace member rather than putting graph code in
  FastAPI route modules or Celery task functions.
- Add LangGraph only to the agent-orchestrator package dependency boundary.
  Add only the directly required supporting runtime dependencies (for example,
  Pydantic settings and the already chosen official OpenAI SDK) with bounded
  compatible versions. Regenerate and commit `uv.lock` through the normal
  workspace workflow; do not introduce LangChain, LangMem, Ragas/DeepEval,
  Presidio, a vector store, or a second queue framework.
- The agent core must depend on typed ports/value objects, never FastAPI
  request objects, route handlers, SQLAlchemy ORM models, Celery task context,
  or browser data. API-side adapters may depend on the core and on the existing
  database services to compose a production runtime.
- Every persisted operation is organization-scoped. The API persistence adapter
  must verify the case, actor, and workflow run through existing tenant-safe
  repositories before writes. A foreign-tenant identifier is indistinguishable
  from missing data.
- Durable state is not a raw `model_dump()` of a graph state. Case text,
  document content, prompts, provider request/response bodies, model output
  that is not an explicitly persisted product result, credentials, headers,
  tokens, vectors, and raw exceptions are never copied into `state_snapshot`,
  `WorkflowNodeRun.input_summary`, `WorkflowNodeRun.output_summary`, audit
  metadata, normal logs, or test snapshots.
- The existing audit metadata validator rejects sensitive keys such as query,
  excerpt, score, provider response, exception, and credential material. New
  orchestration events must use safe, whitelisted counters, state/status,
  workflow/node names, retry count, and controlled reason codes only.
- The foundation must keep model and tool selection server-owned. No HTTP
  request, case data, prompt row, or graph state may select an arbitrary
  provider/model, endpoint, function, tool name, retry count, or prompt text.
- A deterministic model is plumbing for local/test repeatability only. It
  must be rejected by configuration outside `local` and `test`, must have a
  visible provider label, and must never be described as model-quality or
  evaluation evidence.

## Existing repository baseline to verify before implementation

- `services/agent_orchestrator/` is currently only a reserved uv workspace:
  its `pyproject.toml` has no runtime dependencies and its source/test
  directories are empty.
- Root `pyproject.toml` already includes the service in the uv workspace and
  in the strict Ruff/mypy paths. Root scripts run Ruff and mypy over `services`
  and run the API suite from `apps/api/tests`; add a focused agent test command
  or make the existing Python test invocation include the new package without
  weakening either check.
- `apps/api/src/app/db/models/workflow.py` already defines `WorkflowRun` and
  `WorkflowNodeRun`, including non-negative duration/retry constraints and
  tenant-safe links from workflow runs to cases and users. It has no runtime
  execution behavior yet.
- `apps/api/src/app/services/workflows/service.py` currently offers only
  scoped run creation/list/get. `apps/api/src/app/db/repositories/workflow.py`
  is persistence-only and currently lacks node-run/update helpers. Extend
  those layers, not route handlers, with the bounded persistence operations
  this phase proves.
- `apps/api/src/app/db/models/prompt.py` already contains global or
  organization-specific `PromptVersion` rows, and
  `ModelUsageRecord` already holds safe provider/model/accounting metadata.
  There is no prompt-loading service yet.
- `apps/api/src/app/api/routes/workflows.py` is a truthful no-operation
  boundary. It must remain operation-free in Phase 16; Phase 17 owns the first
  closed workflow trigger/status/correction API surface if it is needed to run
  Intake end to end.
- Phase 15's `app.services.retrieval.generator` is expressly a narrow direct
  RAG adapter. Do not import it into the agent core, change its protocol, or
  make its settings the generic agent-provider contract.

## In scope

### 1. Typed agent-orchestrator package and public contracts

Create an importable package structure under
`services/agent_orchestrator/src/agent_orchestrator/` with intentional public
exports and narrow modules such as:

```text
agent_orchestrator/
  config.py
  errors.py
  types.py
  state/
    case_state.py
    snapshots.py
  graphs/
    runtime.py
    contracts.py
  model_providers/
    base.py
    deterministic.py
    openai.py
    factory.py
  prompts/
    base.py
  tools/
    registry.py
  persistence/
    ports.py
  observability.py
```

The exact filenames may vary only when the same ownership boundaries remain
clear. Keep future graph-specific modules such as `intake_graph.py`,
`evidence_graph.py`, actual node packages, LangMem, retrieval/document tools,
and approval logic out of this phase.

Define immutable Pydantic/dataclass command and result types for at least:

- workflow identity/context (`organization_id`, `case_id`, initiating user,
  workflow name/version) and closed runtime statuses;
- the shared `CaseWorkflowState` shape from Architecture §7.1, using typed
  identifiers, language/risk/approval enums, safe reason-code collections, and
  optional future-result fields rather than unbounded `dict[str, Any]` state;
- node execution metadata, a bounded retry policy, terminal execution outcome,
  controlled error/reason code, and safe timing/accounting metadata;
- a model request/result contract whose request is created only by server graph
  code and whose result can be validated into a graph-owned Pydantic schema;
- effective prompt metadata (id, name, version, organization scope) separate
  from prompt content; and
- registered tool identity, schema/handler contract, and safe invocation
  metadata.

Use `Protocol`/generic boundaries where that avoids an API or database import.
No public core type may accept a mutable request object, raw ORM entity, or
untyped arbitrary callback payload as a durable state substitute.

### 2. LangGraph runtime and safe graph-state handling

Build the reusable runtime that later graph modules call:

- Provide a small graph builder/executor wrapper around LangGraph that accepts
  a server-built graph, typed initial state, execution context, registered
  ports, and a fixed retry policy. It must make node transitions explicit and
  preserve the typed state at each boundary.
- Establish one clear lifecycle: create/claim run, mark node started, invoke a
  node, validate its typed state update, mark node completed, retry only
  configured retryable failures, then mark run completed or failed. A failed
  node/run has a safe stable error code, never an exception string.
- Calculate timing from a monotonic clock, clamp it non-negative, and persist
  it only as integer milliseconds. Define retry semantics unambiguously:
  `retry_count` is the number of retries after the initial attempt, and the
  configured maximum is finite and validated.
- Add a single state-snapshot serializer with an explicit allowlist. It may
  persist workflow/version, state schema version, current/terminal status,
  target language, boolean routing flags, approved low-cardinality enum values,
  bounded reason codes, node count, and counters. It must default-deny unknown
  fields and record only count/shape metadata for lists/maps. It must never
  serialize raw human input, source/document content, prompts, model payloads,
  IDs that duplicate protected record links, or error text.
- Define similarly allowlisted `input_summary` and `output_summary` builders
  for `WorkflowNodeRun`. They must be useful for operational trace later
  (schema version, input/output field names, booleans, enum labels, counts,
  outcome code), while avoiding data content. Do not imply that Phase 23's
  trace API/UI has been implemented.
- Emit structured, content-free runtime events with workflow/run/node status,
  attempt/retry count, and duration. Use the project's safe logging
  conventions; do not configure a competing global logging pipeline.
- Include a tiny internal test-only/no-business graph fixture solely to prove
  the runtime lifecycle. It must not be a disguised Intake, Evidence,
  Extraction, Drafting, Risk, or Approval graph and must not be exposed by API
  or worker code.

### 3. Persistence ports and API-side durable adapters

Define a persistence port in the agent package, then implement it in the API
application where the SQLAlchemy models and transaction ownership already
live. The adapter is responsible for:

- creating a `WorkflowRun` in `queued`/`running` only after scoped case and
  actor validation;
- atomically staging a `WorkflowNodeRun` at node start, completing it with
  safe summaries/timing/retry count, and finalizing the parent run with terminal
  status, timestamps, total tokens/cost when known, controlled error summary,
  and safe state snapshot;
- storing model usage through the existing `ModelUsageRecord` model when a
  model call is actually attempted. Do not manufacture usage rows for
  deterministic no-model test paths or for unattempted work;
- retaining transaction boundaries so a runtime never reports a persisted
  success if the run/node records could not be committed; and
- translating integrity/availability failures to existing or narrowly added
  neutral service errors without leaking SQL/provider exception content.

Add the required repository/service methods for node create/finalize and run
finalize with explicit organization predicates. Do not add an unscoped
`get-by-id`, arbitrary state JSON update, generic delete, or mutable audit
operation. Do not introduce migrations merely for convenience: the Phase 4
tables contain the required fields. If a real schema limitation is discovered,
stop and document it rather than silently widening Phase 16.

Add a prompt-loading port in the core and API implementation that resolves an
effective active prompt for a requested server-owned prompt name:

1. active prompt for the current organization, if present;
2. otherwise active global prompt;
3. otherwise a controlled `prompt_not_configured` failure.

The loader returns content only to the trusted graph/model boundary and returns
metadata for persistence. It does not expose prompt CRUD, admin endpoints,
prompt text in logs, or client-selected prompt names. Tests must establish a
deterministic ordering/ambiguity rule before relying on this query in real
graphs.

### 4. Generic model-provider boundary

Implement a graph-oriented provider abstraction separate from Phase 15 RAG:

- Define a server-built structured-completion request containing operation
  name, effective prompt, validated input object, declared output schema, and
  server-owned model configuration. Define a normalized result with validated
  JSON-compatible output, provider/model label, optional non-negative token
  accounting, latency, and controlled failure code.
- Provide a factory selected only from validated agent settings. It supports
  OpenAI and Azure OpenAI with lazy official-SDK clients, bounded timeout,
  zero/controlled SDK retries (the graph runtime owns retry policy), and
  structured-output parsing. Missing/invalid configuration must yield a safe
  unavailable provider rather than fail at import time or reveal credential
  details.
- Provide a deterministic fixture-backed provider for local/test. Its output is
  keyed by a test-owned operation/fixture identifier, is validated through the
  same output-schema path, and has stable result/usage behavior. It must not
  inspect live environment secrets or make network calls.
- Add agent settings under an explicit `NORDIC_AGENT_` prefix for provider,
  model/deployment, API version, timeout, output cap, node attempts, and
  snapshot bounds. Store key/endpoint as `SecretStr`, validate non-empty public
  values, reject deterministic provider outside local/test, and require the
  appropriate secret pair in staging/production. Extend `.env.example` with
  commented non-secret names and safe defaults only.
- Record only provider/model/operation, success, safe accounting presence,
  latency, and controlled error code through the persistence adapter. Prompt
  content, model input/output bodies, endpoint, credential, and raw exception
  never leave the model boundary.

This phase does not need a live provider credential or a manual provider call.
All automated tests inject deterministic/fake providers.

### 5. Prompt and tool registry foundations

- Implement server-owned prompt resolution as above and retain the effective
  prompt id/version with a model invocation only when an invocation occurs.
  Do not seed production prompt prose or build prompt management UI/API.
- Implement a typed tool registry that supports explicit application startup
  registration, immutable tool name/description/input schema, handler
  protocol, and an allowlisted invocation path. Reject duplicate registration,
  unknown names, malformed validated inputs, and tools not allowed for the
  current graph before invoking any handler.
- Registry instrumentation must log/persist metadata only: tool name, success
  or controlled result code, and duration. It must not persist arguments,
  result bodies, document text, URL credentials, or arbitrary tool errors.
- Register no business-capability tool in Phase 16. A no-op deterministic test
  tool is permitted only in tests to prove schema validation and registry
  enforcement. Retrieval/document/memory/audit tools and real tool-call
  behavior belong to their respective later phases.

### 6. Documentation and dependency hygiene

- Update `services/agent_orchestrator/pyproject.toml`, root lock metadata, and
  only the documentation/configuration necessary to explain the new local/test
  orchestration foundation. Keep `README` claims accurate: no business graph,
  workflow API, or human-approval capability exists after this phase.
- Add/update architecture-facing developer notes only if the exact package
  invocation, deterministic test mode, and secret requirements are confirmed
  by implementation. State clearly that deterministic output is test plumbing,
  not AI quality validation.
- Preserve Phase 15 RAG configuration and direct-answer documentation. Do not
  rename, combine, or deprecate it while no graph consumes the new provider
  factory.

## Out of scope

- Intake classification, language/PII/prompt-injection detection, risk
  scoring, workflow selection, case-field updates, user correction, or an
  Intake Graph. Those are Phase 17.
- Evidence retrieval/reranking/contradiction routing (Phase 18), extraction
  (Phase 19), drafting/citation claim validation (Phase 20), final risk policy
  (Phase 21), approval interrupts/resume (Phase 22), trace views/APIs
  (Phase 23), LangMem (Phase 24), evaluation datasets/runners (Phase 25), and
  observability dashboards (Phase 27).
- Any frontend feature, browser model configuration, token persistence,
  workflow action screen, workflow trace UI, or claim that a placeholder route
  is functional.
- Public workflow run/cancel/status routes, Celery workflow tasks, queue
  dispatch/reconciliation, and modification of the currently truthful
  `workflows` route. Phase 17 owns the first actual executable workflow
  surface.
- New data stores, vector indexes, LangChain, LangMem, external tool
  integrations, caching, streaming, webhooks, broad agent chat, prompt admin,
  model admin, or provider fallback policy.
- Altering direct RAG behavior, direct RAG prompts, retrieval governance,
  source status semantics, case lifecycle transitions, RBAC matrices, existing
  migrations, or roadmap/progress completion markers during plan generation.

## Likely files and ownership

| Area | Likely files | Responsibility in this phase |
| --- | --- | --- |
| Agent core | `services/agent_orchestrator/pyproject.toml`, `src/agent_orchestrator/**` | Typed state/runtime, settings, provider/tool/prompt/persistence ports, safe snapshot/log helpers, deterministic test provider. |
| Agent tests | `services/agent_orchestrator/tests/unit/**`, `tests/graph/**`, `tests/regression/**` | Pure-contract, runtime lifecycle, deterministic model, registry, settings, and safe-redaction tests. Do not add product regression scenarios yet. |
| Workflow persistence adapter | `apps/api/src/app/services/workflows/**`, `apps/api/src/app/db/repositories/workflow.py` and narrowly related model/service files | Tenant-safe run/node persistence implementation and composition adapter; no route operations. |
| Prompt persistence adapter | `apps/api/src/app/db/repositories/prompt.py` and/or `apps/api/src/app/services/workflows/prompts.py` | Active tenant/global prompt lookup through a typed port; no prompt-management API. |
| API tests | `apps/api/tests/unit/test_workflow_*`, `apps/api/tests/integration/test_workflow_*` | Tenant isolation, prompt precedence, durable node/run records, commit/failure behavior. |
| Workspace/config/docs | `pyproject.toml`, `uv.lock`, `.env.example`, applicable testing/development docs | Dependency, command, and secret-safe configuration updates only. |

## Implementation tasks

1. Inspect the current agent workspace, root test scripts, workflow/prompt ORM
   records, current transaction conventions, and Phase 15 direct-RAG seams.
   Confirm the worktree is clean or isolate unrelated changes before edits.
2. Add the minimal package dependencies and lock update. Verify the workspace
   installs without making an API/provider network call and that strict Ruff/
   mypy discover the new package.
3. Define the typed core values, error taxonomy, safe settings, shared case
   state, and snapshot/summary allowlists. Write pure unit tests first for
   enum/identifier validation, default-deny serialization, bounds, and
   controlled error mapping.
4. Implement persistence and prompt ports in the core. Implement API-side
   adapters through scoped repositories/services, including run/node lifecycle
   methods and a deterministic effective-prompt precedence rule.
5. Build the LangGraph runtime around those ports. Prove it with a deliberately
   inert test graph that completes, retries a transient controlled failure,
   and fails permanently without leaking raw exception data.
6. Implement the generic model protocol, deterministic provider, lazy
   OpenAI/Azure adapters/factory, and settings validation. Test schema failures,
   timeout/unavailable normalization, accounting propagation, deterministic
   stability, and no network path under tests.
7. Implement the empty-by-default typed tool registry and its validation/
   metadata-only instrumentation. Test duplicate/unknown/schema-denied paths
   using a test-local no-op tool only.
8. Wire the API composition root only as far as needed for persistence-adapter
   integration tests; do not mount an operation or worker task. Add regression
   guards that the workflow route remains operation-free and that Phase 15 RAG
   does not import the agent provider/runtime.
9. Run focused tests, complete quality checks, and then local-stack validation.
   Update exact docs/config notes only after the verified behavior is known.

## Required tests

### Agent package unit tests

- Settings accept bounded valid values, reject public blank values and invalid
  retry/snapshot limits, hide secrets, reject deterministic outside local/test,
  and fail safely when staging/production provider credentials are missing.
- Shared state rejects malformed identifiers/invalid enum states and has no
  permissive arbitrary JSON escape hatch.
- Snapshot and node-summary serializers include permitted metadata but omit
  raw case text, prompt text, evidence, model payloads, provider endpoint/key,
  arbitrary errors, and unknown future fields by default.
- Retry policy performs exactly the configured finite attempts, stores retries
  as attempts-after-first, never retries controlled permanent failures, and
  preserves the original safe code only.
- Deterministic model output is stable, passes the same Pydantic output schema
  path as a production result, and makes no network call. Provider malformed/
  timeout/SDK failures normalize to controlled errors without raw content.
- Tool registry rejects duplicate/unknown/disallowed/schema-invalid calls and
  retains metadata only for its test no-op path.

### LangGraph/runtime tests

- The internal inert graph has explicit start/node/end behavior, validates
  typed state transitions, persists an ordered node lifecycle, and produces a
  completed terminal run with non-negative duration.
- A retryable node creates one node record with correct retry count (or the
  documented per-attempt model), bounded attempts, and no duplicate terminal
  finalization.
- A permanent failure finalizes node/run safely, leaves no raw exception in
  state summaries/log capture, and does not report success.
- Cancellation/interrupt semantics are not claimed or tested as implemented;
  a regression assertion should keep such APIs absent.

### API persistence integration tests

- Run and node writes retain organization/case/actor linkage; cross-tenant
  reads or writes are not observable as valid resources.
- Start/complete/fail transitions persist timestamps, safe snapshot, duration,
  retry count, and accounting consistently; a persistence failure cannot return
  a successful completed execution.
- Prompt lookup prefers a valid organization prompt over global, falls back to
  global, excludes inactive rows, handles ambiguity by the documented stable
  rule, and never returns a foreign-organization prompt.
- Model usage is written only after a modeled invocation, contains safe
  accounting/provider metadata, and never receives prompt or request/response
  content.
- Existing Phase 15 RAG tests and OpenAPI/workflow-route boundary tests remain
  green and prove no direct RAG behavior changed.

## Validation steps

Run the exact commands supported by the completed implementation (add a focused
agent test script only if it is actually created):

```bash
uv run pytest services/agent_orchestrator/tests
uv run pytest apps/api/tests/unit apps/api/tests/integration
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test:api
pnpm test:web
pnpm check:workspace
pnpm dev:up
docker compose --env-file .env.example exec api uv run alembic current
pnpm verify:local-stack
pnpm dev:down
```

Additionally confirm, without printing credentials or state contents:

- the agent package imports in the workspace and the deterministic-only test
  path completes a minimal inert graph;
- the API docs still show no executable workflow operation after Phase 16;
- no tracked config file contains an agent provider credential or endpoint;
- `git diff --check` is clean and only Phase-16-scoped files changed.

If the local stack cannot be started, retain the completed static and
integration-test evidence, report the environmental blocker precisely, and do
not mark the phase complete until the required stack validation is later run.

## Completion criteria

- `services/agent_orchestrator` is a typed, dependency-locked LangGraph
  workspace package with no placeholder-only implementation remaining for the
  Phase 16 contracts.
- A reusable typed runtime can execute a non-business proof graph with bounded
  retry behavior and durable, tenant-safe workflow/node lifecycle records.
- Safe snapshots, node summaries, logs, errors, and model/tool metadata are
  allowlisted and tested not to contain raw case/evidence/prompt/model/secret
  data.
- The generic provider factory supports safe OpenAI/Azure construction and a
  deterministic local/test implementation; all tests remain offline and
  stable.
- Effective prompt lookup and an empty-by-default tool registry are typed,
  server-owned, test-covered, and not exposed through a public API.
- Existing RAG, API, web, database, auth, and local-stack behavior remains
  green. The Workflow API boundary remains honestly operation-free.
- All required tests and validation commands pass. Only then may a later
  implementation turn mark Phase 16 `(DONE)` in `specs/roadmap.md` and update
  `specs/progress.md`.

## Risks, dependencies, and implementation notes

- **LangGraph API drift:** pin a compatible bounded version and keep the graph
  wrapper narrow. Do not scatter LangGraph imports through API services.
- **Layering risk:** importing ORM entities into `agent_orchestrator` would
  make graph tests need a database and entangle FastAPI with orchestration.
  Preserve core ports plus API-side adapters.
- **Secret/logging risk:** provider setup and model failures are a common leak
  path. Treat all provider exceptions and payloads as unsafe and test log/
  snapshot capture explicitly.
- **Persistence semantics:** do not expose a completed run before its parent
  and node records commit. Reuse the established async-session and engine
  disposal patterns, especially for tests that create event loops.
- **Prompt ambiguity:** the current table does not itself establish a complete
  uniqueness policy for active versions. Define a deterministic lookup rule in
  code/tests; do not invent prompt administration or silently pick an
  unpredictable row.
- **Scope discipline:** a reusable runtime is valuable only if it stays generic.
  The first concrete business node, worker dispatch, endpoint, and case update
  are Phase 17 work.

## Notes for the implementation agent

- Start from this plan, then reread the actual Phase 15 code before changing
  dependencies or composition. Its RAG-only generator is intentionally not the
  generic provider abstraction.
- Prefer adding narrow adapters beside `app.services.workflows` over broad
  changes to FastAPI dependencies or route registration.
- Preserve the project's strict type checking, normal transaction owner,
  content-free audit rules, and safe error envelope conventions.
- Do not mark this phase done merely because unit tests pass. Run the full
  validation sequence and keep Phase 16 free of Phase 17 business behavior.
