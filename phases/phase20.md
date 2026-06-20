# Phase 20 — Drafting Graph

## Phase objective

Deliver the asynchronous Drafting Graph that produces a reviewable Norwegian Bokmål/English response, internal recommendation, summary, or action plan grounded exclusively in a persisted eligible Evidence package. It must validate citations, detect unsupported claims, run a bounded clarity pass, persist the original AI draft with its source provenance and safe metadata, and display it truthfully on Case Detail.

The result is an AI draft for later risk/approval work—not final advice, a case decision, an approved output, or a human-edited final text.

## Relevant context and constraints

- The architecture defines six nodes: `prepare_context`, `draft_response`, `validate_citations`, `check_unsupported_claims`, `improve_clarity`, and `persist_draft`.
- Drafts must be grounded in retrieved sources, use the UI language unless an authorized user explicitly requests the other supported interface language, and show only source-supported claims. The current Case language may be used as the server-side default; an optional request can contain only `nb` or `en`, never a client prompt/style/model/source list.
- Phase 18's completed, sufficient, non-contradictory Evidence package is mandatory. Phase 19 structured fields may be used as validated supplemental context only when their selected Extraction run is eligible; they never replace source evidence. If evidence is absent/weak/contradictory, or citation/claim checks fail, route to safe Needs More Evidence and do not present an ungrounded draft.
- Reuse Phase 15's strict citation-label/parser utilities and provider abstraction where possible, but preserve Phase 15 direct-RAG endpoint behavior. Citation labels must resolve to the current run's persisted approved Evidence sources.
- Architecture supplies `agent_messages` for draft content/structured output and `retrieved_sources` for provenance. The original AI draft must be retained distinctly for Phase 22; this phase must not let a human overwrite it. State snapshots, nodes, audit metadata, logs, and normal workflow status must remain content-free/default-deny even though the draft content is stored in the dedicated protected record.
- Phase 21 owns final risk and Phase 22 owns approval, interruption/resume, human final text, and edit-and-approve. Do not pre-empt either phase.

## In scope

1. A typed, six-node Drafting Graph with server-owned context composition, language selection, output schema, citation/claim checks, clarity pass, and safe outcomes.
2. Persisted workflow/node/model usage records, Evidence source provenance, and a protected `AgentMessage` original AI draft plus safe structured metadata.
3. Closed start/status/read APIs and dedicated UUID-only worker execution with Evidence eligibility/RBAC/tenant checks.
4. An accessible, localized Case Detail Draft section that displays a safe valid draft and citations/source context, or a truthful Needs More Evidence/failed/queued state.
5. Deterministic fixtures, automated coverage, documentation/settings, and full local validation.

## Out of scope

- New retrieval, source filtering, evidence contradiction decisions, or arbitrary document/context selection (Phase 18 owns evidence).
- Extracted-field editing (Phase 19) beyond reading validated eligible values as bounded supplemental context.
- Final risk level/approval requirement, approval queue/actions, workflow interruption/resume, human edits to the draft, final output, export, audit trace UI, LangMem, evaluation, external integrations, streaming, or cancellation.
- Generic text generation, generic prompt/model configuration, a browser-controlled source list/query, raw model rationales/claim analysis, or client-visible numeric confidence/cost/token details.

## Likely files and ownership

| Area | Likely files/folders | Phase-20 responsibility |
| --- | --- | --- |
| Drafting graph | `services/agent_orchestrator/src/agent_orchestrator/graphs/drafting_*.py`, prompts/state/provider contracts | Typed six-node orchestration and strict candidate/output schemas. |
| Citation/claim policy | Existing `app.services.retrieval.citations`, focused agent/API adapters/policies | Share only tested citation parsing/provenance semantics; add bounded unsupported-claim validation. |
| Workflow persistence | `app/services/workflows/drafting.py`, `orchestrator.py`, workflow repositories/models | Persist original draft and provenance atomically; safe status/audit projection. |
| API/worker | Workflow route/schema modules and `workers/tasks.py` | Extend the closed start/status contract for `drafting`, optional closed output language, and a safe draft-read DTO; UUID-only task. |
| Web | `components/cases/**` or focused `components/drafting/**`, API contracts/query hooks, messages/tests | Read-only localized draft/citation presentation and truthful status/no-evidence UI. |
| Tests/docs | Agent/API/web/E2E suites, docs and only needed non-secret settings | Deterministic test path, verified operation documentation. |

## Implementation tasks

1. **Establish trustworthy inputs.** Inspect final Phase 18 Evidence outcome/provenance contracts and Phase 19 selected-field contracts. Define a server-side input loader that obtains the case, latest eligible Evidence package, stable citation labels/source excerpts, and optionally validated extracted fields under the same organization/case/run constraints. Reject stale/foreign/non-approved/restricted evidence. Do not accept context from the browser or retain it in general graph state.
2. **Define strict Drafting types.** Add a closed `DraftKind`/purpose taxonomy (response, internal recommendation, summary, action plan), `OutputLanguage` enum (`nb`, `en`), and structured candidate/final output schema. Require bounded text, exact inline citation labels, no extra fields, allowed source-label references, and closed warning/reason codes. Resolve language from explicit optional enum or trusted UI/case default; record only the language code in safe workflow output.
3. **Implement six explicit nodes.**
   - `prepare_context` builds fixed bounded prompt inputs from server-loaded eligible sources and optional validated fields, treating all source text as untrusted reference material.
   - `draft_response` invokes the configured structured provider/prompt through Phase 16; deterministic fixtures must exercise the same Pydantic validation path.
   - `validate_citations` reuses/extends strict Phase-15 label validation, rejecting missing, malformed, duplicate, unknown, or source-mismatched labels.
   - `check_unsupported_claims` applies a documented bounded verification policy against the Evidence package. Any uncertain/unsupported output produces closed flags/reasons and prevents a visible draft; never persist/display a raw model rationale as proof.
   - `improve_clarity` may make only a bounded language/formatting revision that preserves exact claim/citation correspondence; re-run citation and support checks after revision.
   - `persist_draft` writes only a validated, supported candidate and its provenance.
4. **Persist original drafts and terminal outcomes safely.** Create a `drafting` workflow run/version and normal node lifecycle records. For a valid draft, atomically persist an `AgentMessage` with a draft-specific message type/role, original text, safe structured metadata, prompt-version/model usage linkage, and `RetrievedSource` provenance/citation labels tied to the drafting run. The state snapshot/audit response holds only availability/language/counts/closed reasons. If evidence/citation/support checks fail, terminal outcome is Needs More Evidence with no displayable draft; do not store a partially unsafe candidate as a public draft. A worker retry cannot create duplicate original draft messages.
5. **Add only closed execution and read APIs.** Extend the existing workflow start contract with `"drafting"` and an optional closed output-language field only for that workflow. Enforce permitted role, readable/eligible case, completed eligible Evidence (and optional fields) prerequisite, one active run policy, UUID-only dispatch, and a tenant-scoped safe read result. Offer a distinct protected draft-read endpoint/DTO if needed to return the actual draft and citations without polluting generic workflow status; it must authorize the case first and omit model/provider/prompt/trace/claim-analysis internals. There is no PATCH/approve/finalize/edit endpoint in this phase.
6. **Implement the worker composition.** Reload/claim by UUID, build trusted input ports, run the compiled graph with finite retry and loop-safe session disposal, and translate dispatch/runtime/persistence failure into safe terminal status and audit event. Queue payloads never contain text, prompt, evidence, source IDs, field values, model settings, or action choices.
7. **Present a truthful read-only draft.** Add a Bokmål-default/English Case Detail section with an allowed Draft start control, queued/running/complete/needs-more-evidence/failed statuses, selected output-language label, clear "AI draft—requires later review" framing, inline citation links to the existing safe source-context dialog, and safe reason-category display. Keep controls keyboard-accessible and non-color-only. Do not offer content editing, approval, export, a final-answer label, raw unsupported-claim data, numeric confidence/cost, or silent fallback to ungrounded text. Poll only active owned runs with cleanup.
8. **Document verified scope.** Configure only bounded non-secret draft/context/clarity settings and deterministic fixtures. Documentation must state that citations/support validation gates display and that approval/finalization remains later work.

## Required tests

### Graph and policy tests

- The six nodes run in architecture order; state/output models reject extra keys, malformed/oversized drafts, invalid language/purpose, unknown citations, model rationale fields, and arbitrary context.
- Norwegian Bokmål is the default for a Bokmål case/UI; an explicit closed English request works; unsupported language/style instructions do not alter server-owned controls.
- Every draft citation maps exactly to an eligible current Evidence source. Missing, malformed, duplicate, unknown, unsupported, or post-clarity-invalid citations prevent display/persistence as a valid draft.
- Supported deterministic drafts pass citation/support checks; weak/contradictory/no evidence and unsupported-claim fixtures route to Needs More Evidence without an exposed fallback answer.
- Context treats case/doc/source content as untrusted: injection-like text cannot select tools, model/prompt/provider, language, sources, or a workflow action.
- Provider/validation/persistence/clarity failures remain bounded/retried only by policy and keep raw content/prompt/model/error data out of snapshots, logs, and audit metadata.

### Persistence/API/worker/audit tests

- Closed drafting start/read endpoints enforce cookie auth, role, tenant/case visibility, Evidence eligibility, request strictness, active-run policy, and foreign/missing/archived safety.
- UUID-only dispatch, duplicate delivery, bounded retry, broker/persistence failure, and engine disposal are covered.
- A valid run persists one original draft message with matching organization/case/run/provenance/prompt/model-usage records. Source rows are current-run, readable, and stable-labelled; cross-tenant reads fail safely.
- Needs More Evidence/status API projections contain only designed availability/count/language/reason data. Protected draft-read DTO contains only validated draft text and safe citation/source presentation fields—not state snapshot, node trace, prompt/provider values, raw support analysis, numeric score/cost/token, or exceptions.
- Audit events (`workflow.drafting_queued`, `started`, `completed`, `needs_more_evidence`, `failed`) are content-free and transactionally consistent. No case finalization/risk/approval/human-edit record is created.
- Phase 15 direct-RAG citation/answer behavior and all prior workflow/retrieval/auth/Case suites remain green.

### Web and end-to-end tests

- Bokmål and English cover start, AI-draft/review notice, language, citations, needs-more-evidence, failure, loading, empty, and safe error states.
- Draft body/citations have semantic structure, keyboard source-context access, visible focus, non-color-only states, and no editable/approval controls.
- Client tests validate strict API contracts, active polling cleanup, safe errors, and absence of tokens/raw workflow payloads in browser storage.
- Playwright uses a synthetic sufficient Evidence fixture to run Drafting, inspect a supported Bokmål draft and source context, then uses an unsupported/weak fixture to prove no draft is shown and Needs More Evidence is visible.

## Validation steps

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

Manual synthetic-only check: at `http://127.0.0.1:3000/nb/cases`, open a case with eligible Evidence, run Drafting, verify the result says AI draft/review required, confirm all citations open authorized source context, and verify no edit/approve control exists. Repeat with weak/unsupported fixture and confirm Needs More Evidence with no draft body. Inspect cookie-secured contracts at `http://127.0.0.1:8000/docs`; never print credentials, cookies, draft/evidence text, prompts, or provider values.

## Completion criteria

- The typed six-node Drafting Graph produces only source-supported, citation-validated, language-correct original AI drafts from eligible Evidence.
- Citation/support failure and weak/contradictory evidence safely yield Needs More Evidence with no user-visible ungrounded draft.
- Original drafts and provenance persist behind tenant/RBAC checks; status/audit/state projections stay default-deny and content-free.
- Case Detail presents a localized, accessible, read-only AI draft with safe source links and accurate non-final framing. No approval/finalization/risk/human-edit/tracing behavior is implemented.
- Deterministic graph, persistence, API, worker, web, and E2E tests pass along with full static/local-stack validation.

## Risks, dependencies, and notes for the implementation agent

- Phase 18 is non-negotiable: do not use direct RAG search or client-provided sources as a shortcut around the eligible Evidence package.
- Citation format alone is not support. Validate label membership and independently gate unsupported claims before presentation; prefer a safe refusal over a persuasive ungrounded draft.
- Preserve original AI draft immutability now so Phase 22 can retain it beside later human-approved text. Do not smuggle human edits into `AgentMessage` in this phase.
- Language selection is a presentation preference, not a prompt injection channel. Keep it closed to `nb`/`en` and server-resolved.
- Do not mark Phase 20 `(DONE)` or edit progress while generating this plan; only a later implementation turn may do so after all validation succeeds.
