# Phase 15 — RAG Answering with Citations

## Phase objective

Turn the completed governed hybrid retrieval capability into one protected,
source-grounded RAG answer operation.

Implement POST /api/retrieval/answer as a typed, tenant-scoped API operation
that answers a question only from current approved indexed sources, returns
stable inline citations, refuses safely when the evidence is not sufficient,
and uses Norwegian Bokmål or English as requested. Persist the durable evidence,
assistant output, model-call accounting, and bounded execution record needed for
later workflow trace, audit, evaluation, and cost work.

This phase delivers a direct, synchronous RAG answer service. It is not a
LangGraph workflow and must not pre-implement the Agent Orchestrator, drafting
graph, risk graph, approval flow, evaluation runner, trace UI, or a chat UI.

    Phase 13                 Phase 14                    Phase 15
    governed retrieval  ->   evidence display  ->         grounded answer
    ranked excerpts          source context                citations/refusal
                                                               |
                                                               v
                                                        durable RAG records

## How this phase fits the final product

The product must never behave like a black-box chat-with-PDF application.
FR-RAG-001 through FR-RAG-004 require answers to be grounded in approved
sources, cite those sources, state limitations, refuse unsupported requests,
and support Norwegian Bokmål and English. The architecture assigns hybrid
retrieval, citation extraction, evidence sufficiency, and a POST
/api/retrieval/answer boundary to the retrieval layer.

Phases 12 through 14 already provide the prerequisites:

| Completed phase | Reusable result | Phase 15 responsibility |
| --- | --- | --- |
| Phase 12 | Parsed/indexed document chunks, 1536-dimensional embeddings, pgvector and full-text indexes | Consume the current index only; do not change ingestion, chunking, or embeddings. |
| Phase 13 | Tenant-safe hybrid RetrievalService, approved-source default, source governance, bounded excerpts, retrieval audit events | Call it as the sole retrieval path; do not fork its SQL, rewriter, filters, rank fusion, or authorization. |
| Phase 14 | Document governance, bounded source context, Evidence Panel source cards | Return citation-safe source data for later UI use, but do not add an answer screen or change the existing Evidence Panel. |

The persistence schema already includes workflow_runs, retrieved_sources,
agent_messages, and model_usage_records. The source/message rows require a
workflow_run_id. For this phase, each direct answer request therefore adds a
real, bounded RAG execution record with workflow_name rag_answer. It represents
the request that produced the durable answer evidence; it is not a fabricated
graph run, adds no workflow-node rows, and does not introduce LangGraph.
Phase 16 will add the general orchestration service and its reusable graph
persistence semantics on top of this honest record.

| Later phase | May consume Phase 15 output | Still owned by that later phase |
| --- | --- | --- |
| Phase 16 — Agent Orchestrator Foundation | Typed retrieval-answer boundary, direct RAG run records, tested model-call seam | LangGraph, typed graph state, model-provider abstraction, prompt loading, tool registry, retries, and generic workflow persistence. |
| Phase 18 — Evidence Graph | Persisted source provenance and the explicit preliminary sufficiency outcome | Graph-owned rewrites, reranking, contradiction detection, route-to-Needs-More-Evidence logic, and persisted evidence package. |
| Phase 20 — Drafting Graph | Citation label/validation helpers and safe answer generation conventions | Case drafting, claim-level unsupported-claim checks, clarity passes, and final draft workflow records. |
| Phase 21/22 | RAG outcome and safe audit events | Risk assessment, approval routing, interrupts, reviewer decisions, and human edits. |
| Phase 23/25/27 | Run, source, message, and usage records | Trace API/UI, deterministic evaluation datasets, dashboards, metrics, and OpenTelemetry. |

## Relevant context and architectural constraints

- Roadmap Phase 15 requires source-grounded question answering over approved
  sources, citations, evidence sufficiency checks, weak-evidence refusal,
  Norwegian/English output handling, and persistence of retrieved sources, AI
  messages, model usage, latency, tokens, and estimated cost.
- PRD FR-RAG-001 requires citations, uncertainty with incomplete evidence, and
  refusal when support is insufficient. FR-RAG-002 requires hybrid retrieval,
  which is already supplied by Phase 13. FR-RAG-003 requires supported
  citations; this phase establishes deterministic citation membership and
  formatting validation. FR-RAG-004 requires Bokmål queries and responses in
  the interface language unless explicitly requested otherwise.
- Architecture sections 6.2, 6.4, 9.2–9.3, 10.2, 11.2, 13.5, 14, 17, and 18
  require thin typed API boundaries, backend-enforced tenant/RBAC policy,
  source-grounded answer constraints, safe error handling, durable model
  metadata, structured audit data, and testable service design.
- All source acquisition must go through the existing RetrievalService. That
  service already applies organization, active-document, parsed/indexed,
  approved-source, confidentiality, and role predicates before excerpts reach
  application memory. Phase 15 must never query document_chunks directly for
  answering.
- The answer operation searches approved sources only. It accepts no
  source_statuses, restricted/archived selection, raw source context, client
  vectors, caller-supplied scores, workflow ids, model names, provider options,
  prompts, token limits, or citation labels. Non-approved review behavior
  remains the governed search/context capability from Phases 13–14.
- Existing hybrid rank scores are deterministic ordering signals, not
  confidence, truth, faithfulness, or approval scores. Do not use a rank score
  threshold as a claim that evidence is sufficient.
- Model credentials, endpoints, request bodies, system prompts, source
  excerpts, user question text, and raw provider errors must never be written
  to logs, audit event_data, OpenAPI examples, docs, or normal test artifacts.
  Assistant output and approved-source excerpts are durable tenant-scoped
  product records only where this phase explicitly requires them.
- Source text is untrusted data, never executable instruction. The fixed
  server-owned prompt must say that evidence excerpts are reference material,
  may contain malicious instructions, and cannot override system or user
  instructions. Full prompt-injection detection/routing remains Phase 17.
- Do not add a browser token, local/session storage of questions or answers,
  frontend answer UI, new vector store, reranker, LangChain, LangGraph,
  LangMem, cache, Celery answer job, OpenSearch/Qdrant, evaluation framework,
  or a prompt-version administration surface.

## Existing baseline to extend

The implementation agent must verify these actual repository contracts before
editing:

- apps/api/src/app/api/routes/retrieval.py currently exposes only the protected
  source search endpoint and explicitly documents that answers/citations are
  future work.
- apps/api/src/app/api/schemas/retrieval.py has closed Pydantic request/result
  models for search. Extend this ownership boundary with separate answer
  request/result schemas; do not weaken search schemas or expose a generic
  free-form model API.
- apps/api/src/app/services/retrieval/service.py owns authorization, case
  verification, query rewriting, embedding, governed hybrid retrieval, bounded
  source results, and retrieval.search_completed audit records.
- apps/api/src/app/services/retrieval/types.py exposes RetrievedSource with
  rank, methods, bounded excerpt, document/chunk identity, and safe
  source-governance information. It does not contain a citation label yet.
- apps/api/src/app/services/auth/policy.py grants ordinary retrieval only to
  Admin, Compliance Reviewer, Case Worker, and Manager. Read-only Auditor has
  audit visibility but must remain unable to retrieve evidence or generate an
  answer.
- apps/api/src/app/db/models/workflow.py and prompt.py already define the
  durable WorkflowRun, RetrievedSource, AgentMessage, and ModelUsageRecord
  tables. Their composite tenant foreign keys must remain intact. No migration
  should be introduced unless an implementation discovery proves an existing
  schema constraint prevents the documented Phase 15 record shape.
- apps/api/src/app/db/repositories/workflow.py already has tenant-safe
  WorkflowRun addition. New RAG-specific persistence must follow the existing
  repository/service separation rather than adding SQL or model writes to the
  route.
- apps/api/src/app/core/config.py, dependencies.py, errors.py, and
  core/errors.py provide the typed settings, dependency injection, and neutral
  error envelope conventions to extend.
- The OpenAI SDK is already a declared API dependency because ingestion supports
  OpenAI/Azure OpenAI embeddings. Its presence does not authorize an
  unbounded/general provider framework before Phase 16.

## In scope

### 1. One protected, direct answer API

- Add POST /api/retrieval/answer to the existing Retrieval route group, with
  the normal success/error envelope, OpenAPI cookie security, typed schemas,
  standard request id metadata, and no new top-level route group.
- Require a current, readable case in the authenticated organization and a
  question. The case is authorization and audit context; it does not restrict
  retrieval to the case attachments.
- Accept an optional answer_language enum with only nb and en. When omitted,
  resolve the target from the authenticated user preferred language: nb,
  nb-NO, and Norwegian variants resolve to nb; en and en-* resolve to en; a
  missing/unknown stored preference falls back to nb. Do not infer language
  from browser headers or translate the query.
- Use the existing RetrievalService with the server-owned approved-source
  default. The public answer operation has no non-approved source-selection
  capability.
- Return either an answered outcome with answer text and citations, or a
  needs_more_evidence outcome with a localized safe refusal. Weak evidence is
  an expected product outcome and returns HTTP 200, not a 4xx/5xx error.

### 2. Deterministic evidence sufficiency and refusal behavior

- Build a pure, fully tested preliminary evidence-sufficiency policy before
  any model call. It must require only approved, retrieved sources and enforce
  server-owned minimum source count plus minimum combined bounded-excerpt
  characters. Its decision must expose a stable, non-sensitive reason code,
  never a score interpreted as confidence.
- If retrieval returns no usable evidence or fails the configured deterministic
  threshold, do not invoke the model. Persist the RAG execution outcome and
  retrieved-source provenance that exists, append a safe refusal audit event,
  and return a short localized refusal directing the user to provide more
  approved sources or clarify the question.
- A model may additionally return that the supplied evidence cannot support an
  answer. Normalize that to the same needs_more_evidence outcome. Do not turn
  an uncertain answer into a confident answer, invent sources, or fall back to
  general model knowledge.
- This check is deliberately preliminary. It does not perform claim-level
  entailment, contradiction analysis, risk assessment, approval routing, or
  evaluation scoring; those are later phase responsibilities.

### 3. Source-grounded generation and citation validation

- Add a narrow injectable RAG answer generator protocol and production adapter
  local to this retrieval-answer capability. It is a small test seam for a
  single completion operation, not the multi-provider abstraction, prompt
  registry, tool system, or graph runtime planned for Phase 16.
- Build the prompt entirely on the server from the user question, selected
  bounded excerpts, canonical labels, target language, and fixed grounding
  instructions. Require only evidence-supported statements, concise uncertainty
  when needed, no outside knowledge, no invented citations, and inline source
  labels in the exact form [S1], [S2], and so on.
- Select source context deterministically in retrieval rank order under
  server-owned source-count and character budgets. Use Phase 13 excerpts only;
  never fetch raw files, full extracted text, generic chunks, storage objects,
  or parser metadata for an answer.
- Normalize the provider result to a typed internal answer/refusal value,
  including model identity, token accounting when supplied, latency, and
  selected citation labels. Enforce a bounded answer length.
- Validate before publishing an answered result:

  1. every cited label is a label assigned to a retrieved approved source in
     this answer run;
  2. every returned citation label appears inline in the answer;
  3. no unknown, duplicate, malformed, or client-controlled label is returned;
  4. an answered outcome has at least one valid citation; and
  5. the target-language field matches the server-selected nb/en value.

- If the generated answer fails structural citation validation, never return
  that answer. Record a safe needs_more_evidence/refusal outcome with a
  non-sensitive internal reason code, preserve only allowable provider
  accounting, and emit an audit event with counters rather than content.
- This structural validation does not claim to prove claim-level faithfulness.
  Do not add semantic claim extraction, an LLM judge, citation scoring,
  contradiction detection, or an unsupported-claim graph. Phase 20 and the
  later evaluation phases own those stronger controls.

### 4. Durable RAG execution, source, message, usage, and audit records

- Add one WorkflowRun for every accepted answer request before final result
  persistence. Use the fixed workflow_name rag_answer and a documented
  Phase-15 version value; set the caller as started_by_user_id and the current
  case/organization ids. Its allowed statuses are running, completed,
  needs_more_evidence, and failed.
- The run state_snapshot may contain only safe, bounded operational metadata:
  target language, evidence-source count, cited-source count, preliminary
  outcome/reason code, and whether a model call was attempted. It must not
  contain question text, excerpts, prompt text, answer text, vectors, source
  ids, provider response bodies, credentials, or raw exceptions.
- Persist one RetrievedSource row for every source selected by governed
  retrieval, including its run-local canonical S-number citation_label, rank,
  deterministic rank score, normalized retrieval method names, and already
  bounded excerpt. Persist all retrieved evidence, not merely the citations
  that appear in the published answer.
- Persist one assistant AgentMessage only for a model-produced answer or
  model-produced refusal that is allowed to be retained. Its content is the
  resulting answer/refusal; its structured output contains only stable outcome,
  target language, and canonical citation-label metadata. Do not duplicate the
  user question, full system prompt, or evidence prompt into AgentMessage.
- Persist one ModelUsageRecord for each attempted model invocation with
  provider, model, operation rag_answer, token input/output where available,
  estimated cost where configured, latency, success, and a controlled safe
  failure summary where appropriate. A preliminary no-model refusal does not
  fabricate a model usage row.
- Update WorkflowRun finished_at, duration_ms, total_tokens, total_cost_estimate,
  status, and safe state snapshot consistently with the result. Never add a
  WorkflowNodeRun in this phase.
- Append one content-free audit event for each final outcome:
  rag.answer_completed, rag.answer_refused, or rag.answer_failed. It links
  actor, case, and RAG run, and contains only language, evidence/citation
  counts, outcome/reason code, whether a model was called, and safe timing/
  accounting presence flags. It must contain no question, answer, excerpt,
  citation label, source/chunk/document id, score, prompt, token value,
  cost value, raw error, provider response, or credential.
- Coordinate persistence so a successful response is backed by complete,
  internally consistent tenant-scoped records. If a database error prevents
  that, return no success answer. If a provider call fails after the run
  begins, make the failed run and safe ModelUsageRecord/audit persistence
  durable through the established transaction pattern before returning a
  neutral availability error; never expose provider detail.

### 5. Bounded configuration, error handling, documentation, and tests

- Add validated, non-secret RAG settings for completion provider choice,
  model/deployment name, timeout, maximum output tokens/answer characters,
  maximum evidence sources/characters, deterministic evidence-minimum
  thresholds, and input/output price rates for cost calculation.
- Keep API keys and Azure endpoint values secret. Reuse a secret only through
  settings access at adapter construction; never log or render it. Production
  configuration must use a real OpenAI or Azure OpenAI completion deployment.
  Unit/API tests inject a fake generator and must make no network call.
- Permit an unknown token/cost value to remain null only when the provider does
  not supply usage or local/test pricing is deliberately unavailable. Require
  both price rates together, calculate cost with Decimal arithmetic when usage
  and rates exist, and require pricing configuration outside local/test if the
  selected provider cannot report cost directly. Do not hard-code volatile
  vendor prices in source.
- Add one neutral service error for unavailable/invalid RAG generation and map
  it to the existing 503 error envelope. Keep malformed client input at 422,
  absent session at 401, unauthorized role at 403, and foreign/missing case at
  tenant-safe 404. A no-evidence or invalid-citation refusal remains 200.
- Update README and development/API documentation only after implementation
  confirms the exact endpoint and local prerequisites. Explain that a real
  provider credential is needed for manual model answering, that deterministic
  embedding mode is not answer-quality validation, and that only synthetic
  content may be used.

## Out of scope

- LangGraph, LangChain, LangMem, generic agent state, graph nodes, tool
  registry, retry framework, prompt version loading/admin, model-provider
  abstraction for all workflows, or workflow-node persistence. These begin in
  Phase 16.
- Graph-owned query rewriting, reranking, contradiction detection, evidence
  package persistence, evidence routing, and Needs More Evidence case-status
  transition. Phase 18 owns them. Phase 15 returns an answer outcome only and
  must not mutate case status.
- Draft response workflows, claim-level unsupported-claim detection,
  semantic citation/faithfulness scoring, clarity rewriting, final case drafts,
  or human-edit tracking. These are Phase 20 and Phase 22 work.
- PII/prompt-injection detection, risk scoring, approval requirement,
  approval queue, workflow interrupt/resume, human decisions, or audit/trace
  inspection UI. These are Phases 17 and 21–23.
- New frontend question/answer pages, chat controls, answer cards, Evidence
  Panel behavior, local browser persistence, or Playwright answer UI flows.
  This phase is API/service/persistence only; the existing frontend remains
  truthful.
- New retrieval indexes, a direct document_chunks answer query, Qdrant,
  OpenSearch, Elasticsearch, reranking/cross-encoder models, caching,
  background answer jobs, streaming/SSE/WebSockets, or document download/raw
  text access.
- Evaluation datasets/runners, quality dashboards, metrics dashboards,
  OpenTelemetry, exports, rate-limit hardening, security hardening beyond the
  existing safe boundary, or deployment/CI work.
- Changing source-status governance, weakening tenant/composite foreign keys,
  making restricted/draft/deprecated/archived sources answerable, altering
  Phase 13 public search semantics, or marking roadmap/progress complete
  during plan generation.

## API and authorization contract

### POST /api/retrieval/answer

The request is deliberately smaller than POST /api/retrieval/search:

| Request field | Required behavior |
| --- | --- |
| case_id | Required UUID. Must identify an active, readable case in the authenticated organization. It is authorization/audit context, not a corpus restriction. |
| question | Required non-blank UTF-8 text after the same safe normalization/bounds used by retrieval. It is passed only to the server-owned retrieval/generation path and is never placed in audit event_data. |
| answer_language | Optional closed enum nb or en. Omission uses the authenticated user preferred-language resolution specified above. Values such as locale headers, model/provider selection, source statuses, document ids, prompt text, citation labels, and limits are rejected as extra fields. |

The success envelope contains:

| Response field | Answered outcome | needs_more_evidence outcome |
| --- | --- | --- |
| run_id | RAG execution UUID | RAG execution UUID |
| outcome | answered | needs_more_evidence |
| language | nb or en | nb or en |
| answer | Bounded source-grounded answer with inline [S#] labels | Localized safe refusal without unsupported factual claims |
| citations | Ordered safe citation objects only for labels actually used inline | Empty list |
| evidence_reason | Null | Stable safe reason such as no_eligible_sources, insufficient_evidence, model_refused, or citation_validation_failed |

Each citation object is derived server-side from a persisted approved
RetrievedSource row and includes only label, document_id, document_title,
document_file_type, chunk_id, nullable page_number/section_title, bounded
excerpt, rank, and retrieval_methods. It does not expose raw chunks, object
storage, checksums, vectors, token counts, source metadata, provider details,
scores as confidence, or any non-approved source.

### Authorization and source rules

- Add RetrievalAction.ANSWER with the same operating-role matrix as SEARCH:
  Admin, Compliance Reviewer, Case Worker, and Manager are eligible; Read-only
  Auditor is denied before content/model work begins.
- The RAG service must authorize ANSWER, then invoke the existing retrieval
  service. The retrieval service still validates CaseAction.READ and enforces
  tenant/source policy. Do not rely on frontend role data.
- Answering has a hard approved-only source scope. Physical archives,
  non-parsed/non-indexed documents, draft, deprecated, restricted, archived
  source statuses, and restricted confidentiality remain excluded even for
  Admin/Compliance Reviewer. There is no privileged answer bypass.
- A valid request with no eligible evidence returns the localized normal
  needs_more_evidence response. It must not fall back to a global corpus,
  language model knowledge, or an unfiltered document search.

### Citation and language contract

- Labels are run-local and deterministic: sources selected in rank order receive
  S1, S2, and so on. Inline answer references must use [S1] syntax exactly.
  The client may localize surrounding display copy such as Source or Kilde, but
  may not invent or renumber labels.
- Citation order in the response follows first appearance in the validated
  answer, with a stable source-rank tie-breaker. Source rows remain stored in
  rank order for later trace/evaluation work.
- The nb refusal/prompt wording uses clear Norwegian Bokmål. The en wording uses
  plain English. The API does not promise automatic language detection or
  translation in this phase; it passes the submitted question to governed
  retrieval and asks the model for the explicitly selected output language.

## Persistence contract

No new table is required for the baseline Phase 15 record shape. Confirm
existing models and migration state instead of adding duplicate storage.

| Record | When added | Required safe content |
| --- | --- | --- |
| WorkflowRun | Every accepted answer request | Fixed RAG name/version, current tenant/case/caller, lifecycle timestamps/status, aggregate duration/tokens/cost, and content-free state snapshot. |
| RetrievedSource | Every governed source selected for this run | Tenant/case/run/document/chunk references, rank, rank signal, normalized method name(s), bounded excerpt, and canonical S-number label. |
| AgentMessage | A model-generated answer or model-generated refusal retained for the run | Assistant output plus small structured outcome/language/citation-label metadata; no user question, system prompt, or evidence prompt duplication. |
| ModelUsageRecord | Every attempted provider completion | Provider/model/operation, nullable usage/cost where unavailable, latency, success, and controlled failure summary only. |
| AuditEvent | One terminal RAG outcome | Content-free actor/case/run reference and approved counters/outcome metadata only. |

The direct RAG execution is not an approval, case-status transition, workflow
node, or final case draft. Its records must remain tenant-scoped and append-only
from normal application flows.

## Likely files, folders, modules, and services affected

| Area | Expected change |
| --- | --- |
| apps/api/src/app/api/routes/retrieval.py | Add the one thin POST /answer route and update truthful route-group descriptions. Keep search behavior unchanged. |
| apps/api/src/app/api/schemas/retrieval.py | Add closed answer request/outcome/citation schemas, language/outcome enums, strict field bounds, and safe OpenAPI descriptions. |
| apps/api/src/app/api/dependencies.py | Add a request-scoped RagAnswerService factory with injectable generator construction; no eager provider client/network connection. |
| apps/api/src/app/services/auth/policy.py | Add the narrow RetrievalAction.ANSWER role rule; retain all existing source entitlements unchanged. |
| apps/api/src/app/services/retrieval/types.py | Add small internal answer-command/result/citation/evidence-policy values without coupling them to Pydantic or ORM models. |
| apps/api/src/app/services/retrieval/answering.py | New orchestration service that coordinates authorization, RetrievalService, deterministic sufficiency, context construction, generator invocation, citation validation, persistence, and safe audit events. |
| apps/api/src/app/services/retrieval/generator.py | New bounded RAG-only generator protocol/adapter/result normalization and provider cleanup. Do not add the Phase 16 general provider package. |
| apps/api/src/app/services/retrieval/citations.py | New pure canonical-label, inline-citation parsing/validation, answer-bound, and safe citation-response helpers. |
| apps/api/src/app/services/retrieval/evidence.py | New pure preliminary sufficiency and evidence-context budget helpers. |
| apps/api/src/app/db/repositories/rag_answer.py | New persistence-only repository for staging direct RAG run/source/message/model-usage records with no authorization or model logic. |
| apps/api/src/app/db/repositories/__init__.py | Export only the intentional new repository if repository conventions require it. |
| apps/api/src/app/core/config.py | Add validated, secret-safe RAG completion/context/threshold/cost settings and cross-field validation. |
| apps/api/src/app/services/errors.py and apps/api/src/app/core/errors.py | Add/map one neutral RAG-generation availability error while retaining standard envelopes. |
| apps/api/tests/unit/test_rag_*.py | Add pure policy, citation, prompt/result-normalization, cost, and service orchestration tests with fake generators. |
| apps/api/tests/api/test_retrieval.py and apps/api/tests/api/test_openapi.py | Extend endpoint/auth/schema/OpenAPI coverage without weakening search assertions. |
| apps/api/tests/integration/test_rag_answer_service.py | Add PostgreSQL-backed tenant, approved-source, persistence, and audit coverage using synthetic fixtures. |
| README.md and docs/development.md | Document the verified Phase 15 endpoint, local real-provider prerequisite, safety boundaries, and synthetic-only manual path after implementation. |
| .env.example | Add commented, non-secret RAG configuration documentation only. Preserve the user’s existing unrelated uncommitted edits exactly. |
| apps/web/** | No change expected. Do not add answer UI in this phase. |

## Implementation tasks

1. Establish the closed answer contract and preserve the Phase 13 boundary.

   - Read the current retrieval route/schema/service, Phase 13 tests, existing
     standard API envelopes, and persistence transaction conventions before
     editing.
   - Define strict Pydantic answer request/response types with extra fields
     forbidden, UUID/string bounds, closed nb/en and outcome enums, and no
     caller-owned operational/model/source fields.
   - Add POST /api/retrieval/answer to the existing router only. Keep the
     handler transport-only: obtain principal/service, map schema to an internal
     command, and map the internal result to the normal success envelope.
   - Update existing retrieval descriptions/tests so API documentation no longer
     falsely says no answer operation exists, while search remains explicitly
     retrieval-only and citation-label-free.

2. Add answer authorization, language resolution, and approved-only retrieval.

   - Add RetrievalAction.ANSWER and test its complete role matrix. A Read-only
     Auditor must receive 403 before source excerpts or model work.
   - Resolve answer language solely from the closed request value or normalized
     principal preference, with a deterministic Bokmål fallback. Do not add
     Accept-Language parsing, client-side locale dependencies, translation, or
     model-selected language.
   - Build the internal RetrievalRequest from the question with empty
     source-status/document selections so existing policy selects approved
     sources only. Reuse the existing service verbatim; do not access
     DocumentChunk/Document repositories for answering.
   - Retain the existing retrieval.search_completed audit convention and add
     the separate terminal RAG audit event. Neither event may contain source or
     question content.

3. Implement pure preliminary evidence policy and context budgeting.

   - Add a typed policy result with is_sufficient, stable reason code, selected
     source list, and safe counts. Enforce configured minimum source and
     combined-excerpt character requirements after server bounds are applied.
   - Verify each selected source is approved and derive canonical S-labels in
     rank order. Reject impossible/internal inconsistent source states rather
     than widening scope.
   - Build bounded generator context from selected excerpts only, preserving
     document/page/section information necessary for the model to cite labels.
     Enforce configured maximum evidence-source count and total context
     characters with deterministic rank-order truncation.
   - Treat preliminary failure as a normal local refusal. Do not call a
     generator, fabricate model usage, add case status changes, or use rank
     score as an evidence-confidence shortcut.

4. Implement the narrow grounded generator seam.

   - Define a protocol returning a typed generated answer/refusal and safe model
     accounting. Tests supply an in-memory fake; production constructs its
     client only when called and closes it reliably.
   - Support the configured OpenAI or Azure OpenAI completion path required for
     this endpoint only. Keep provider/model/deployment selection server-owned,
     with private credentials/endpoints accessed through typed settings.
   - Compose a fixed server prompt that names the target language, forbids
     external knowledge, mandates [S#] citations for factual statements,
     permits refusal when evidence is inadequate, bounds output, and treats
     source excerpts as untrusted reference data rather than instructions.
   - Normalize provider response/usage into domain values. Map transport,
     timeout, malformed response, and unavailable-provider failures to one
     neutral RAG availability error with no raw provider text.
   - Add Decimal cost computation from configured per-million-token rates only
     when usage/rates are both known. Keep model usage/cost accounting data
     separate from logs and client payloads.

5. Validate citations before any answer becomes visible.

   - Implement pure label parsing and validation over the exact canonical
     [S#] format. Require citation labels to be source-owned, unique, and
     present inline. Bound citation count to selected evidence.
   - Produce citation response data from validated labels and existing safe
     RetrievedSource fields. Preserve source rank/method information but do not
     represent rank score as confidence.
   - If the generator refuses, return the localized refusal and no citations.
     If it attempts an answer with missing/invalid citations, suppress that
     answer, classify the outcome as needs_more_evidence with
     citation_validation_failed, and return a localized safe refusal instead.
   - Do not call another model to judge support, rewrite the answer, or verify
     semantic entailment. Structural grounding guards are the Phase 15 limit.

6. Add RAG-specific persistence and audit coordination.

   - Implement a persistence-only repository that stages the exact existing
     ORM record types. It must receive trusted domain values and explicit
     organization ids; it must not determine policy, construct prompts, or
     make provider calls.
   - Add and flush the RAG WorkflowRun before source/message records need
     its id. Finalize it for completed, needs_more_evidence, or failed outcomes
     with consistent timestamps, aggregate accounting, and content-free state.
   - Persist every selected source with a canonical label and normalized
     retrieval methods. Persist assistant output only when a model result is
     retained. Persist ModelUsageRecord for every actual model attempt,
     including safe failures.
   - Use a deliberate transaction/error path that cannot return a successful
     answer without matching durable records. Audit rows must be appended only
     for the final durable outcome and remain content-free.
   - Add explicit tests for foreign-key validity, organization isolation,
     completed/refused/failed transitions, no model record on preliminary
     refusal, and the absence of workflow-node records.

7. Wire safe settings, error handling, documentation, and regression coverage.

   - Add relational settings validation: context/evidence limits are positive
     and internally ordered, output bound is positive, price rates appear as a
     pair, and deterministic/test-only shortcuts cannot be selected in staging
     or production. Avoid loading clients or secrets during settings addition.
   - Add dependency construction/overrides that make unit/API tests fully
     network-free. Preserve existing embedding-provider behavior and settings.
   - Update README/development docs after the endpoint and local sequence are
     proven. State the exact answer/refusal contract, approved-only rule,
     provider prerequisite, persistence/audit scope, and phase exclusions.
   - Retain the existing local setup, document lifecycle, retrieval search, UI,
     API, and security regression tests. Keep every fixture and manual example
     synthetic; do not use a real personal case, document, question, credential,
     or model response in the repository.

## Required tests

### Unit tests

- Answer language resolution covers explicit nb/en, nb-NO/norwegian-like
  principal preferences, en-* preferences, empty/unknown preference fallback,
  and request precedence.
- Answer authorization covers all five roles, ensuring Read-only Auditor is
  denied and all permitted roles still rely on existing case/retrieval policy.
- Closed schema tests reject blank/overlong questions, malformed UUIDs,
  unsupported language values, extra fields, caller-supplied source status,
  document id, run id, model/provider, prompt, score, token, cost, or
  citation-label values.
- Preliminary evidence policy covers zero sources, too few sources, too little
  total excerpt content, approved eligible sources, impossible non-approved
  internal results, deterministic source selection/order, and no use of
  retrieval rank score as confidence.
- Context-builder tests cover source/character budgets, deterministic
  truncation, page/section fallbacks, untrusted-source instruction framing,
  and absence of raw chunks/storage/parser/model metadata.
- Citation helper tests cover canonical label assignment, valid inline
  references, source-order preservation, duplicate/unknown/malformed labels,
  answer with no labels, labels not present inline, answer-size bounds, and
  response shaping without unsafe fields.
- Generator adapter tests use mocked SDK transport and cover target-language
  prompt construction, response normalization, model refusal, missing usage,
  timeout/provider/malformed-output neutralization, safe cleanup, and no
  secret/prompt/excerpt logging.
- Cost/accounting tests cover Decimal calculation, input/output token
  combinations, absent usage/rates, nonnegative values, and no hard-coded
  vendor price assumption.
- RAG service orchestration tests use fakes to cover answered, preliminary
  refusal, model refusal, citation-validation refusal, provider failure, and
  database failure. Assert that the retrieval service is the only source path,
  no generator runs on preliminary refusal, no unsupported answer is returned,
  and audit payloads contain counters/reason codes only.

### API, OpenAPI, and error tests

- Cookie-session authentication, all role outcomes, current-tenant/missing/
  archived case behavior, standard request id/meta envelope, and strict
  validation errors.
- Answered response contains a bounded answer, nb/en value, run id, inline
  citations, and only safe citation fields. It must never return model name,
  provider, tokens, cost, prompt, raw source content, vectors, storage keys,
  checksum, metadata JSON, rank score as confidence, or a non-approved source.
- No-evidence, preliminary-threshold, model-refusal, and
  citation-validation-failure paths return HTTP 200 needs_more_evidence with
  an empty citation collection and localized safe message.
- Provider availability/malformed-response failures produce the standard
  neutral 503 envelope; no raw exception, endpoint, request body, or provider
  response leaks.
- Existing POST /api/retrieval/search contract tests remain intact: search
  still returns no citation label/answer, its non-approved governed review
  behavior is unchanged, and no new generic model endpoint appears.
- Router/OpenAPI tests assert POST /api/retrieval/answer, cookie security,
  closed schemas, normal errors, truthful descriptions, and the continued
  absence of raw chunks/downloads/streaming/chat/provider configuration
  endpoints.

### Integration tests

- PostgreSQL integration seeds two synthetic organizations, active indexed
  approved sources, unavailable/stale/physically archived sources, and
  non-approved/restricted sources. It proves the RAG operation selects only
  current approved primary-tenant evidence through governed retrieval.
- Persisted completed path verifies one RAG run, all selected RetrievedSource
  rows, run-local labels, an assistant AgentMessage, one successful
  ModelUsageRecord, aggregate run accounting, and one content-free terminal
  audit event with tenant-safe foreign keys.
- Persisted preliminary refusal verifies a RAG run and terminal audit event,
  no assistant/model usage records, no generated answer, and no case status
  mutation.
- Model refusal/citation-validation paths verify an answer is not exposed,
  the final run outcome is needs_more_evidence, retained model usage is
  correctly accounted for, and citations are empty in the public result.
- Provider failure verifies failed execution/model-usage/audit persistence
  follows the chosen transaction contract and the client sees only neutral
  failure. Database/persistence failure must never leave a successful public
  response.
- Tenant isolation tests prove a foreign case, document, chunk, run, or
  persisted source cannot be found or referenced by another organization; an
  Auditor cannot cause model/source persistence.
- Existing retrieval/document/identity/audit integration tests remain green.

### Manual verification

- Use only a disposable local stack, synthetic seeded user/password, synthetic
  approved indexed document, and a real configured completion credential held
  outside source control.
- In Swagger at http://127.0.0.1:8000/docs, log in through the normal cookie
  flow, select POST /api/retrieval/answer, submit a simple Bokmål question for
  an approved source, and verify an answered response has inline [S#]
  citations whose safe metadata matches the Evidence Panel/source context.
- Repeat with answer_language en and verify an English answer/refusal while
  source identity/citation labels remain stable and no browser token is used.
- Submit a question with no matching approved source and confirm HTTP 200
  needs_more_evidence, a localized refusal, no fabricated citation, and no
  answer derived from general knowledge.
- Verify a Read-only Auditor receives 403 and an operational user cannot make
  non-approved/restricted evidence answerable through hidden request fields.
- Inspect only safe record metadata through controlled local database queries
  if needed; do not print questions, assistant output, source excerpts,
  cookies, passwords, API keys, storage keys, or raw provider payloads into
  shell history, test output, screenshots, or repository documentation.

## Validation steps

Run from the repository root after implementation. Do not mark the phase
complete if any check fails.

1. Verify locked dependencies and Compose configuration without printing
   environment values:

   ~~~bash
   pnpm install --frozen-lockfile
   uv sync --all-packages --locked
   uv lock --check
   docker compose --env-file .env.example config --quiet
   ~~~

2. Run focused RAG/retrieval tests first, then the full backend test suite:

   ~~~bash
   uv run pytest apps/api/tests/unit -k 'rag or retrieval or citation or policy'
   uv run pytest apps/api/tests/integration -k 'rag or retrieval or audit'
   uv run pytest apps/api/tests/api -k 'retrieval or openapi or error'
   pnpm test:api
   ~~~

3. Run workspace quality gates. Although no frontend feature is in scope,
   retain the web checks as regression protection:

   ~~~bash
   pnpm check:workspace
   pnpm format:check
   pnpm lint
   pnpm typecheck
   pnpm test:web
   pnpm --filter @nordic-regulated-ai-agent-platform/web build
   ~~~

4. Prove migrations, local infrastructure, and API documentation from the
   running stack. Run migrations explicitly; normal service startup must not
   migrate or seed:

   ~~~bash
   pnpm dev:up
   docker compose --env-file .env.example exec -T api uv run alembic -c apps/api/alembic.ini upgrade head
   docker compose --env-file .env.example exec -T api python scripts/check_migrations.py
   pnpm verify:local-stack
   ~~~

5. Provision only a synthetic local login when manual model verification is
   required, then carry out the manual API checks above with a real
   completion-provider credential supplied through an untracked environment
   mechanism:

   ~~~bash
   read -r -s NORDIC_LOCAL_SEED_PASSWORD
   export NORDIC_LOCAL_SEED_PASSWORD
   docker compose --env-file .env.example exec -e NORDIC_LOCAL_SEED_PASSWORD api python scripts/seed_local.py --password-env NORDIC_LOCAL_SEED_PASSWORD
   unset NORDIC_LOCAL_SEED_PASSWORD
   ~~~

   Do not present deterministic embeddings or a fake test generator as proof
   of semantic answer quality. Unit/integration tests must remain deterministic
   and network-free; manual real-provider verification proves only the safe
   runtime path with synthetic data.

6. Stop the local stack and inspect the planned scope/worktree:

   ~~~bash
   pnpm dev:down
   git diff --check
   git status --short
   ~~~

## Completion criteria

- POST /api/retrieval/answer is protected, tenant-scoped, documented, and
  strictly typed. It uses the existing hybrid retrieval service only and cannot
  be used to select non-approved/restricted/stale/archived evidence.
- A valid answer is source-grounded in selected bounded approved excerpts,
  uses the requested/default nb or en language, contains structurally valid
  inline [S#] citations, and returns only safe citation metadata.
- Weak/absent evidence, a model refusal, or invalid generated citations never
  produce an unsupported answer. Each yields the normal localized
  needs_more_evidence response with no citations and a stable safe reason.
- Every accepted answer request has a durable, honest RAG execution record.
  Retrieved sources, assistant output where applicable, provider usage,
  latency/tokens/cost where available, terminal status, and content-free audit
  event are consistent and tenant-scoped.
- No direct RAG answer adds fake graph nodes, changes case status, bypasses
  approval/risk policy, exposes model/provider secrets, logs sensitive content,
  or adds frontend/chat/orchestration/evaluation features ahead of their
  roadmap phases.
- Unit, API, integration, existing regression, OpenAPI, format, lint, type,
  web-build, migration, local-stack, and synthetic manual checks pass.
- Documentation accurately identifies the direct Phase 15 scope and its
  limitations. Only then may the implementation agent mark Phase 15 (DONE) in
  specs/roadmap.md and update specs/progress.md consistently if it exists.

## Risks, dependencies, and assumptions

| Risk, dependency, or assumption | Required mitigation |
| --- | --- |
| Direct RAG persistence rows require a workflow run before Phase 16 exists | Add one honest bounded rag_answer execution record, not a fake LangGraph run; do not add nodes/graph state/framework abstractions. |
| A retrieval rank signal could be misrepresented as answer confidence | Use only deterministic source-count/excerpt-availability checks in Phase 15 and never expose rank score as truth, faithfulness, or approval. |
| A model can hallucinate a citation or provide unsupported text | Fixed grounding prompt, server-owned labels, structural citation membership/inline validation, and safe refusal suppress invalid output. Claim-level verification remains later work. |
| Sources may contain prompt injection text | Treat excerpts as untrusted reference data in the fixed prompt; do not add hidden instruction-following from documents. Full detection/routing begins in Phase 17. |
| Provider APIs, prices, and token fields vary | Hide SDK behavior behind the narrow injectable endpoint seam, record nullable usage only where unavailable, calculate Decimal cost from operator-configured rates, and never hard-code volatile prices. |
| An external model call can fail after run addition | Persist a safe failed terminal record through the chosen transaction pattern, return neutral 503, and never return a success answer without durable state. |
| Real provider credentials are unavailable locally | Keep all automated tests fake/injected and network-free; document manual real-provider verification as optional runtime proof, not a reason to add an unsafe fallback. |
| Retaining answer data can add privacy exposure | Store only the required assistant output/evidence provenance under existing tenant isolation; omit question/prompt content from audit/state snapshots and prohibit secrets in logs. |
| Existing .env.example is dirty before this plan | Preserve that unrelated user change. Any Phase 15 environment-example work must be additive, commented, non-secret, and carefully merged during implementation. |
| A plan may tempt a frontend chat demo | Keep apps/web untouched. The existing Evidence Panel is source inspection, not generated-answer presentation; a user-facing answer flow belongs only when a later roadmap phase explicitly owns it. |

## Notes for the implementation agent

- Read this plan first, then inspect the actual Phase 13 retrieval service,
  Phase 14 source-context/UI contracts, ORM foreign keys, session transaction
  pattern, seed fixtures, settings, errors, and tests before changing code.
- Keep the layering explicit: Pydantic schemas validate transport; routes map
  transport only; the RAG service owns policy/orchestration; pure helpers own
  evidence/citation logic; the generator adapter owns SDK calls; repositories
  own persistence statements; existing RetrievalService remains the sole hybrid
  source boundary.
- Do not silently alter the current public search endpoint to make answer
  implementation easier. Search still has its own governed review use case and
  deliberately returns no final citations or answer.
- Use no real personal data. Do not commit model credentials, endpoint URLs,
  provider prompts, response transcripts, or screenshots/source text. Keep
  tests synthetic and provider-free.
- Do not call an answer an approval, a final case output, a verified
  faithfulness result, or a LangGraph workflow. The honest Phase 15 vocabulary
  is direct RAG answer execution, preliminary evidence sufficiency, structural
  citation validation, and needs_more_evidence outcome.
- Do not edit specs/roadmap.md, specs/progress.md, or unrelated files while
  executing this G-mode task. Implementation may update completion status only
  after every required validation step passes.
