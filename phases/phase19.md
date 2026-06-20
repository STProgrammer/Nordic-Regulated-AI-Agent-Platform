# Phase 19 — Extraction Graph

## Phase objective

Implement the asynchronous, typed Extraction Graph that converts a case and its approved/sufficient Evidence package into source-linked structured fields. It must extract the roadmap field taxonomy, validate provider output, mark low-confidence fields, persist `extracted_fields` safely, and let authorized users inspect and make bounded human edits with durable edit tracking.

Extraction makes facts reviewable; it does not draft a response, decide final risk, approve content, or change a case into a completed decision.

## Relevant context and constraints

- The roadmap requires five nodes: `select_extraction_schema`, `extract_fields`, `validate_structured_output`, `mark_low_confidence_fields`, and `persist_extracted_fields`.
- The supported fields are people/organizations, dates/deadlines, amounts, reference numbers, obligations, tasks, risks, missing information, and suggested next actions. Architecture already provides `extracted_fields` with organization, case, workflow, field name/value, confidence, source chunk, `human_edited`, and timestamps.
- Phase 18 is the evidence prerequisite. Extraction must load a completed, sufficient, non-contradictory current-tenant Evidence run and its persisted approved sources; it must never retrieve arbitrary documents or accept source IDs/excerpts from the browser. A missing/weak/contradictory package is a safe `needs_more_evidence` outcome, not a prompt fallback.
- Phase 16 runtime/model/prompt/persistence boundaries and Phase 17 closed start/status/task conventions continue to apply. Raw case text, evidence excerpts, prompts, model bodies, confidence values, and exceptions stay out of ordinary snapshots, queue payloads, audit metadata, and safe status DTOs.
- PRD calls for editable extracted fields and logged human edits. Existing field data can preserve the value, source reference, `human_edited`, and `updated_at`; record content-free audit metadata for edits. Do not add a speculative revision/event store unless the existing model demonstrably cannot meet this required tracking.
- Phase 20 owns drafting. Phase 21 owns final risk; extracted `risks` are source-linked observations, never a final risk assessment.

## In scope

1. The five-node typed Extraction Graph and closed extraction field/value taxonomy.
2. Server-owned selection of a schema based on closed case type/domain context; provider structured output validation, confidence policy, and source-chunk linkage.
3. Durable extraction run/node/model usage records and current Evidence-derived `ExtractedField` persistence.
4. Closed start/status/read/edit API operations, UUID-only worker execution, tenant/RBAC/source eligibility enforcement, content-free audit events, and idempotence.
5. Localized Case Detail structured-field display and a constrained accessible human-edit surface.
6. Deterministic test fixtures, full automated coverage, non-secret configuration/docs, and local-stack validation.

## Out of scope

- A fresh Evidence search, evidence reranking/contradiction policy, or weakening Phase 18 eligibility checks.
- Drafting, generated prose, citation coverage for a draft, unsupported-claim checks, final text editing, approval, final risk, workflow interruption/resume, trace viewer, LangMem, evaluation, export, or integration calls.
- Generic JSON field names/values, generic workflow mutation, raw model/state download, arbitrary free-text audit rationale, client-supplied prompt/model/provider/tool/source controls, cancellation, or WebSockets.
- Changing a Case's lifecycle/risk level or automatically launching Drafting. An extracted `risk` is a field observation only.

## Likely files and ownership

| Area | Likely files/folders | Phase-19 responsibility |
| --- | --- | --- |
| Extraction graph | `services/agent_orchestrator/src/agent_orchestrator/graphs/extraction_*.py`, state/prompt/provider contracts | Typed graph state, closed schemas/value types, deterministic validation/confidence policy. |
| Evidence/extraction ports | Agent persistence ports and narrow API adapters near `app.services.workflows` | Load eligible persisted evidence and persist field commands without ORM imports in graph nodes. |
| API services/repositories | `app/services/workflows/extraction.py`, workflow/extracted-field repository additions, Case policy only if required | Eligibility, source ownership, atomic writes/edit tracking/audit; no route business logic. |
| API/worker | `api/routes/workflows.py`, `api/schemas/workflows.py`, focused field schemas/routes, `workers/tasks.py` | Closed `extraction` start/status result and field edit command; UUID-only task. |
| Web | `components/cases/**`, perhaps `components/extraction/**`, API contracts/query hooks/messages/tests | Safe structured display and field-specific edit controls on Case Detail. |
| Tests/docs | Agent/API/web/E2E fixtures and appropriate development/API docs | Synthetic deterministic validation, documented scope and local path. |

## Implementation tasks

1. **Verify Phase 18's final contract.** Inspect its Evidence result/status API, terminal state, source persistence, citation labels, Case transition behavior, and final state names. Use a completed sufficient current-tenant Evidence package as the exclusive Extraction input; return an ordinary safe conflict/Needs More Evidence outcome when it is absent or no longer eligible.
2. **Design the closed field contract.** Define an explicit enum for each supported field kind and per-kind Pydantic value schema, cardinality, maximum count/length, normalized date/amount/reference forms, optional source citation label/chunk reference, and closed confidence band (`high`/`low` rather than a public numeric score). Define server-owned schemas per permitted case-type/domain combination and a conservative fallback schema; reject extra fields and unbounded free-form model objects.
3. **Implement the five nodes.** `select_extraction_schema` selects only a server-owned schema; `extract_fields` invokes the active fixed extraction operation through the Phase-16 structured provider with transient case/evidence text; `validate_structured_output` validates each field, its source reference, type/value bounds, duplicate policy, and citation membership; `mark_low_confidence_fields` applies the configured fixed threshold/policy; `persist_extracted_fields` commits only the validated result. A provider's unvalidated source identifier or confidence cannot be persisted.
4. **Persist without accidental duplication.** Create an `extraction` workflow run/version and regular safe node lifecycle records. For a successful run, insert source-linked `ExtractedField` rows transactionally, keyed to this run, and preserve raw value only in the field record required by the product—not workflow snapshots or audit events. Repeat delivery/retry must not create duplicate semantic fields. Define how a later re-run coexists with earlier extraction runs without mutating historical rows; the safe default is a new run with a clearly selected latest completed result, not a destructive overwrite.
5. **Support controlled human editing.** Expose an edit command only for an allowed current-tenant user and only for a field shown from the selected latest completed Extraction run. Validate the replacement with the exact per-kind schema, retain its original source reference unless a later phase owns relinking, set `human_edited=true`, update timestamp, and atomically record a content-free `workflow.extraction_field_edited` audit event (field kind, run, changed flag—never field value). Do not let editing create arbitrary fields, rewrite source links, change confidence/risk/case lifecycle, or silently mutate a foreign/stale row.
6. **Extend closed workflow APIs and worker.** Add `"extraction"` only to the established closed start flow after its Evidence prerequisite check. Extend safe workflow result DTOs with aggregate field counts, availability, low-confidence presence, and a bounded presentation list whose values remain in the explicitly designed field API—not an arbitrary state snapshot. Add a separately typed case extraction-result/list endpoint and field edit endpoint if that keeps the status DTO small and clearer. The worker reloads case/evidence/run by UUID, claims idempotently, has finite retry/disposal behavior, and never takes sources/state/options from queue payload.
7. **Build an accessible Case Detail section.** Add Bokmål-first/English labels for field groups, source citation/context action, low-confidence indicator, extraction status, no-evidence state, and safe errors. Render field value according to its typed format, display provenance by existing safe citation/source-context mechanism, and use labelled field-specific edit controls with cancel/submit/refresh behavior. Do not expose numeric confidence, raw model explanations, arbitrary JSON editing, Draft/Approval buttons, or an implied final risk conclusion.
8. **Document after proof.** Add only bounded, non-secret extraction settings and synthetic fixtures. Update docs to say that extraction is source-linked, reviewable information—not verified final advice or an approval decision.

## Required tests

### Graph/schema tests

- Each supported field kind accepts valid normalized synthetic values and rejects unknown names, extra keys, blank/oversized values, invalid dates/amounts/reference numbers, invalid source references, duplicate violations, and malformed provider output.
- Closed schema selection is deterministic for each allowed case type/domain and never follows case/document instructions or client input.
- Each graph node has a single responsibility and runs in documented order. Deterministic Norwegian and English fixtures yield stable typed results without a network call.
- Source linkage must resolve only to the selected Evidence run's approved sources. Empty, stale, weak, contradictory, foreign, or missing evidence never causes ungrounded extraction.
- Low-confidence fields are marked by fixed policy, not hidden or silently discarded. Field-level `risks` and `missing_information` remain observations and do not create a final risk assessment.
- Failed/retried provider, validation, persistence, or runtime paths reveal only controlled codes and retain no raw case/evidence/prompt/model/error content in summaries/logs.

### Persistence/API/worker/audit tests

- Authentication, allowed role, readable current-tenant case, eligible Evidence run, closed request validation, active-run conflict, foreign/missing/archived resources, and unsupported workflow all receive the expected safe result.
- UUID-only queue delivery, claim/idempotence, bounded retries, dispatch/persistence failure, and loop disposal are covered.
- Persisted rows carry matching organization/case/run/chunk identifiers; are tenant-isolated; preserve source links; provide stable ordering; and do not duplicate on delivery.
- Field edits require authorization and correct kind schema, set `human_edited`, retain source linkage, update timestamps, and are atomic with a content-free audit row. Cross-tenant/stale/non-selected/unsupported edits are indistinguishable from not found where appropriate.
- Safe workflow/status/field responses omit raw graph state, evidence/context body, prompt/provider data, numeric confidence, exceptions, and Phase-20/23 data.
- Existing Evidence, Intake, direct RAG, retrieval, document, Case, auth/RBAC, and workflow-runtime test suites remain green.

### Web and end-to-end tests

- Both locales cover status, no-eligible-evidence, empty, low-confidence, human-edited, loading, and safe error messages.
- Semantic headings, descriptions, labels, keyboard flows, focus restoration, non-color-only low-confidence state, typed input validation, and source-context access are tested.
- Mocked/deterministic tests prove only field-specific values are sent; browser cookies remain HTTP-only and no raw graph output/token is retained in local storage.
- Playwright covers an Evidence-backed Extraction run, source-linked result inspection, one valid human field edit, refresh persistence, and a blocked weak-evidence path using synthetic fixtures only.

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

Manual synthetic-only flow: log in at `http://127.0.0.1:3000/nb/cases`, open a case with a completed sufficient Evidence package, run Extraction, inspect typed fields and source context, make one allowed edit, reload, and confirm the human-edited state. Inspect closed contracts at `http://127.0.0.1:8000/docs`. Do not expose test case text, field values, passwords, cookies, prompts, or provider configuration in terminal output.

## Completion criteria

- The five-node Extraction Graph accepts only eligible persisted evidence and produces schema-validated, source-linked, bounded structured fields.
- Low-confidence fields are visible as review signals; authorized human edits are validated, durable, source-preserving, and content-free audited.
- No extraction route/worker/UI can create arbitrary fields, alter final risk/case lifecycle, launch drafting, or expose raw workflow/model state.
- Deterministic graph, persistence, API, audit, worker, web, and E2E tests pass; full formatting/type/local-stack validation passes.

## Risks, dependencies, and notes for the implementation agent

- Do not start by guessing Phase 18's data contract. Its completed Evidence run and source rows are the data authority for this graph.
- Extraction is susceptible to schema drift and hallucinated provenance. Favor strict per-kind schemas and citation membership validation over a permissive "metadata" JSON field.
- Human edit tracking must respect the privacy/audit rule: durable business data may include the edited value, but audit metadata/logs must not echo it. Use existing schema before introducing a new historical data model.
- Source-linked `risks` and `missing information` are not final compliance judgments. Preserve that distinction visibly and in types until Phase 21.
- Do not mark Phase 19 `(DONE)` or edit progress while generating this plan.
