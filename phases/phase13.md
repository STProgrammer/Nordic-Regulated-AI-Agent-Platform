# Phase 13 — Retrieval Service Foundation

## Phase objective

Turn the Phase 12 indexed document corpus into one secure, tenant-scoped hybrid
retrieval capability. Add a typed, backend-enforced POST /api/retrieval/search
operation and reusable internal service boundary that:

1. normalizes a case-context query through a deterministic query rewriter;
2. obtains one validated query embedding;
3. searches the existing pgvector cosine and PostgreSQL simple full-text indexes
   independently;
4. merges and deterministically ranks candidates without an LLM or reranker;
5. applies organization, lifecycle, source-governance, and role filters before
   returning a bounded permitted excerpt; and
6. appends a content-free audit event for every successful search.

This is the retrieval foundation, not RAG answering. It returns governed ranked
sources and safe source-status warnings. It must not generate an answer,
construct final citations, assess evidence sufficiency, detect contradictions,
invoke LangGraph, or add a frontend Evidence Panel.

    Phase 12                                  Phase 13
    parsed document -> indexed chunks  ->  governed hybrid source search
                                           no answer, graph, or UI

## How this phase fits the final product

The PRD requires source-grounded output, hybrid semantic/keyword retrieval,
visible evidence, and controls for approved, restricted, deprecated, and
archived sources. Phase 12 deliberately delivered only the ingestion side:
canonical chunks, embeddings, pgvector HNSW cosine indexing, PostgreSQL GIN
full-text indexing, and the rule that only documents whose indexing status is
indexed have a current retrieval index.

Phase 13 is the narrow service layer consuming that durable index.

| Later phase | Consumes from Phase 13 | Still owned by that phase |
| --- | --- | --- |
| Phase 14 — Evidence Panel and Document UI | Typed source metadata, bounded excerpt, page/section, rank, methods, warnings | Document/evidence screens, source-context interaction, source-status controls |
| Phase 15 — RAG Answering with Citations | Governed internal retrieval service and ranked results | Model answering, citation formatting/validation, refusal behavior, AI-message and model-usage persistence |
| Phase 16 — Agent Orchestrator Foundation | Injectable retrieval boundary and optional internal workflow context | LangGraph, prompt/model provider abstractions, workflow execution and persistence |
| Phase 18 — Evidence Graph | Hybrid candidate retrieval and safe audit convention | Graph query planning, reranking, evidence sufficiency, contradiction detection, persisted evidence package |

The public endpoint is intentionally case-contextual so every search is
authorized against a real current-tenant case and audited with its case id.
Retrieval searches the permitted organization corpus; a case is request/audit
context, not an implicit restriction to that case's attachments. An optional
document-id selection deliberately narrows the corpus.

## Relevant context and architectural constraints

- Roadmap Phase 13 requires boundaries for query rewriting, vector search,
  keyword search, candidate merging, permissions filtering, source-status
  filtering, and ranked source return. It also requires approved, draft,
  deprecated, restricted, and archived source behavior plus retrieval logs
  linked to cases/workflow runs where applicable.
- PRD FR-DOC-003 requires chunk identity/page/section/source provenance and
  semantic plus keyword indexing. FR-DOC-004 requires approved-source
  preference, restricted-source permission, deprecated warnings, and archival
  exclusion unless an authorized user explicitly selects a source. FR-RAG-001
  through FR-RAG-003 make answers/citations eventual requirements, but answer
  generation, claim verification, and refusal behavior begin in Phase 15.
- Architecture sections 4.4, 6.4, 9.2, 10.2, 11, 13–14, 17, and 18 require
  PostgreSQL plus pgvector, hybrid retrieval, typed boundaries, backend-enforced
  organization/RBAC filters, structured safe logs, Pydantic schemas, and
  repositories with no business policy.
- The document_chunks table already provides the required vector(1536) HNSW
  cosine index and GIN to_tsvector(simple, content) index. Reuse them. Do not
  add Qdrant, OpenSearch, a second index, or raw SQL assembled from user input.
- Phase 12 indexing state is a hard visibility boundary. Retrieval may use only
  active documents with parsing_status parsed and indexing_status indexed. A
  physical documents.archived_at value always excludes the document. Preserved
  but stale chunks while re-indexing is pending, indexing, or failed are not
  current evidence and must never be returned.
- Existing source statuses are approved, draft, deprecated, restricted, and
  archived. Confidentiality also has restricted. The client never supplies an
  organization id, vector, score, SQL/search expression, indexing state, or its
  own entitlement.
- Reuse the existing Phase 12 embedding-provider protocol/factory and strict
  finite 1536-dimensional validation for a query embedding. Its deterministic
  provider remains local/test-only and non-semantic. Do not add an LLM
  query-rewriter or a second provider framework before Phase 16.
- The retrieved_sources table is reserved for later workflow/RAG evidence and
  requires a workflow run. Phase 13 must not fabricate a workflow run, weaken
  that foreign-key contract, or store a direct search as AI evidence. Use one
  minimal audit_events row instead. A future internal context may carry a
  verified workflow-run id; when present, the audit event uses it as resource
  reference. The public endpoint has no workflow-run input.

## In scope

- One protected POST /api/retrieval/search endpoint under the existing retrieval
  route group, using typed request/response schemas and the current standard
  success/error envelope.
- A reusable RetrievalService and typed internal values for request context,
  rewritten query forms, persistence candidates, merged rankings, warning codes,
  and public source results. Routes remain thin.
- Conservative deterministic query rewriting: normalize Unicode whitespace and
  boundaries, preserve Norwegian/English terms, derive a safe full-text form,
  and use a documented bounded expansion contract. It is not LLM rewriting,
  translation, synonym expansion, a model call, or a hidden prompt.
- One validated query embedding plus separate bounded semantic and keyword
  candidate retrieval. Semantic search uses the current pgvector cosine index;
  keyword search uses a parameterized simple text-search query through the
  existing GIN index. Candidate limits are server settings and are at least the
  public result limit.
- Deterministic candidate merging without reranking: deduplicate by chunk id,
  retain methods, and use fixed reciprocal-rank fusion with stable identity
  tie-breakers. The fused score is only a ranking signal, never confidence,
  faithfulness, or approval.
- SQL-level organization, active-document, current-index, source-status,
  selected-document, and restricted-entitlement filtering before content/excerpts
  enter application memory.
- Bounded result data for the future Evidence Panel: document id/title/type,
  chunk id, nullable page/section, source status, rank, fused score, methods,
  bounded excerpt, and warning codes. Do not return raw object data, checksum,
  embedding, token count, offsets, chunk/parser metadata, task id, provider
  data, or a final citation label.
- One successful, content-free retrieval audit event containing actor,
  organization, case, optional verified workflow resource reference, requested
  source statuses, counts, methods, and query length. It contains no query text
  or hash, excerpt/chunk content, vector, score, checksum, storage key, provider
  response, secret, or exception message.
- Validated settings for public result limit, candidate limits, rank-fusion
  constant, max query length, max explicit document selections, and max excerpt
  length. Reuse existing embedding settings and secret handling.

## Out of scope

- An answer endpoint, LLM answers, source-grounded prompts, citation generation
  or validation, unsupported-claim detection, weak-evidence refusal, evidence
  sufficiency, contradiction checks, or model-usage records. These begin in
  Phase 15 and Phase 18.
- Frontend document detail/list work, source context/download/preview, Evidence
  Panel rendering, source-status controls, or any UI action. Phase 14 owns these.
- LangGraph, workflow creation/execution, workflow-node logging, prompts,
  LangMem, risk/approval routing, or fake workflow runs. These start at Phase 16.
- Reranking models, cross encoders, LLM query expansion, translation,
  synonym/ontology systems, Qdrant, OpenSearch, Elasticsearch, caching, or
  evaluation dashboards.
- Changing retrieved_sources, creating a retrieval-results table, weakening
  workflow foreign keys, or persisting a direct search as AI evidence.
- Source-status mutation, per-document ACL administration, document archive
  APIs, browser-supplied vectors/scores/SQL, synchronous indexing, or exposing
  chunks, embeddings, or raw text through an endpoint.
- Updating roadmap/progress status during planning. Implementation does that only
  after all required checks pass.

## Source-governance and authorization contract

### Caller and case context

The public request requires a case in the authenticated principal's organization.
The service checks CaseAction.READ and a new RetrievalAction.SEARCH policy before
querying. Admin, Compliance Reviewer, Case Worker, and Manager may make ordinary
searches. Read-only Auditor remains limited to audit inspection and receives 403
for retrieval. A foreign, archived, or missing case is tenant-safe 404.

The case grants neither cross-organization access nor source-governance bypass.
It is authorization/audit context for a search over the current organization's
eligible corpus.

### Source-status behavior

The request has an optional bounded source_statuses set and optional bounded
document_ids selection. The client cannot select a source category it is not
entitled to see.

| Source state | Default | Explicit request | Returned warning |
| --- | --- | --- | --- |
| approved | Included; the default corpus | Any retrieval caller may select it | none |
| draft | Excluded | An operational retrieval caller may select it for review | source_draft |
| deprecated | Excluded | An operational retrieval caller may select it for review | source_deprecated |
| restricted | Excluded | Requires explicit selection plus restricted-source entitlement: Admin or Compliance Reviewer | source_restricted |
| archived source status | Excluded | Requires explicit archived selection, at least one exact document id, and restricted-source entitlement | source_archived |

A document with confidentiality_level restricted requires the same restricted
entitlement even if its source status is approved. A physical archive
(archived_at is not null) is never searchable; archived in the table above is
the governed source-status label only. Do not invent per-document ACLs,
source-status editing, entitlement UI, or a hidden administrator bypass.

### Mandatory retrieval predicates

Every semantic and keyword candidate query must include all of these predicates:

    document_chunks.organization_id = authenticated organization
    documents.organization_id      = authenticated organization
    documents.archived_at          IS NULL
    documents.parsing_status       = parsed
    documents.indexing_status      = indexed
    documents.source_status        IN authorized requested statuses
    documents.confidentiality      allowed by the caller's restricted entitlement
    document id                    IN selected ids only when supplied

Selected-document validation is tenant scoped and must not disclose whether a
foreign id exists. Zero candidates are a valid successful result, never a
fallback to unfiltered/global search.

## Public API contract

### POST /api/retrieval/search

| Field | Required behavior |
| --- | --- |
| case_id | Required UUID for an active current-tenant case that the caller can read; authorization/audit context only |
| query | Required non-blank string after normalization, bounded by configuration, never logged or echoed separately |
| limit | Optional bounded positive result count with conservative server default; callers cannot set candidate-pool sizes |
| source_statuses | Optional bounded set; omission means approved only; non-default values must pass source policy |
| document_ids | Optional bounded UUID list narrowing the current-tenant corpus; mandatory for archived-source request and never able to bypass lifecycle/role filters |

The success payload is an ordered list with document_id, document_title,
document_file_type, chunk_id, nullable page_number and section_title,
source_status, rank, rank_score, retrieval_methods, excerpt, and warning_codes.
The rank score is documented only as deterministic merge score, not confidence.

Expected safe errors are 401 for no session, 403 for role/source-entitlement
denial, tenant-safe 404 for a case or selected document outside visible scope,
422 for malformed/oversized/empty input or invalid source-status combination,
and 503 for neutral retrieval-provider/database availability failure. A valid
query with no eligible results returns 200 and an empty list.

## Likely files, folders, modules, and services affected

| Area | Expected change |
| --- | --- |
| apps/api/src/app/services/retrieval/__init__.py | Create the narrow Phase 13 retrieval package and intentional public exports. |
| apps/api/src/app/services/retrieval/types.py | Internal request/context, rewritten query, candidate, merge, warning, and safe-result values. Keep ORM/API schemas out. |
| apps/api/src/app/services/retrieval/rewriting.py | Deterministic injectable rewriter protocol/implementation; no model or prompt. |
| apps/api/src/app/services/retrieval/merging.py | Pure candidate deduplication, fixed reciprocal-rank fusion, stable ordering, warning helpers. |
| apps/api/src/app/services/retrieval/service.py | Policy, case/workflow context validation, embedding, repository calls, merging, excerpt construction, audit coordination. |
| apps/api/src/app/services/auth/policy.py | New narrow retrieval role matrix and restricted-source entitlement policy. |
| apps/api/src/app/db/repositories/retrieval.py | Parameterized async SQLAlchemy/pgvector candidate queries with mandatory predicates. |
| apps/api/src/app/db/repositories/case.py and workflow.py | Reuse for tenant-scoped context validation; add only a focused helper if workflow/case association cannot be checked. |
| apps/api/src/app/core/config.py and .env.example | Retrieval limits/fusion/excerpt settings only; reuse Phase 12 embedding configuration. |
| apps/api/src/app/api/schemas/retrieval.py | Bounded request/result schemas and safe warning-code enum. |
| apps/api/src/app/api/routes/retrieval.py | Add only the protected search route, accurate OpenAPI descriptions, and safe errors. |
| apps/api/src/app/api/dependencies.py | Request-scoped retrieval-service factory with test seams and no eager network client. |
| apps/api/src/app/services/errors.py and core/errors.py | Reuse/add one neutral retrieval-unavailable 503 domain error; no pgvector, SQL, or provider details. |
| apps/api/tests/unit/test_retrieval_*.py | Rewriter, policy, merge/ranking, redaction, settings, and error tests. |
| apps/api/tests/integration/test_retrieval_service.py | PostgreSQL/pgvector/GIN hybrid-query, filtering, isolation, audit, and transaction tests. |
| apps/api/tests/api/test_retrieval.py plus router/OpenAPI tests | Authentication/RBAC/validation/error/redaction/OpenAPI coverage. |
| docs/development.md and README.md | Synthetic verification, status semantics, limits, provider dependency, and later-phase exclusions. |

No migration is expected. Phase 4/12 documents, chunks, workflow, and audit
tables already provide the required foundation. Do not alter retrieved_sources
merely to record a direct search. If implementation discovers a real schema
defect that makes this contract impossible, stop and document evidence rather
than quietly expanding scope.

## Implementation tasks

1. Freeze the retrieval boundary and public contract.

   - Define internal values for public case-context search, optional internal
     workflow context, semantic/keyword rewritten forms, persistence candidates,
     merged candidates, warnings, and safe results.
   - Add Pydantic schemas with strict UUID/list/string bounds, enum validation,
     duplicate document-id normalization/rejection, and default approved-only
     source selection. Reject client candidate limits, vectors, scores,
     organization ids, workflow ids, and arbitrary search expressions.
   - Add exactly one truthful search route. Keep SQL, role logic, embedding, and
     audit-shape composition out of the route handler.

2. Implement deterministic query rewriting without premature AI behavior.

   - Define a QueryRewriter protocol and default implementation that normalizes
     Unicode whitespace/control characters, bounds post-normalization length,
     preserves meaningful terms, and creates semantic plus full-text forms.
   - Use only a parameterized PostgreSQL-safe constructor such as
     websearch_to_tsquery(simple, bound value), or a proven equivalent. Do not
     concatenate user terms into to_tsquery or accept a query DSL. Empty lexemes
     produce an empty keyword candidate set, never a broad search.
   - Do not invoke OpenAI, Azure OpenAI, LangChain, LangGraph, translation, or a
     prompt from the rewriter. Phase 18 can later supply graph-owned query
     planning through this narrow input boundary.

3. Put authorization and source governance ahead of candidate retrieval.

   - Add RetrievalAction.SEARCH and the role matrix above. An auditor cannot
     retrieve source content even though it can inspect audit records.
   - Implement pure source-scope policy that resolves default/requested statuses
     and restricted entitlement before SQL. A restricted confidentiality level is
     handled like a restricted source.
   - Require a current-tenant readable case. For a future internal workflow
     caller, verify that workflow run and case share organization and case before
     using the run as audit resource reference. Do not create workflow runs,
     expose workflow input, or add orchestration.
   - Validate selected document ids in the current tenant without leaking a
     foreign id. Repeat all lifecycle/status/entitlement predicates in both
     candidate queries; preflight validation alone is insufficient.

4. Add safe hybrid retrieval and deterministic merge.

   - Implement separate semantic and keyword repository queries. Both join
     chunks to documents, bind all inputs, and contain mandatory organization,
     lifecycle, source-status, confidentiality, and optional-selection filters.
   - Get exactly one semantic query vector through the Phase 12 provider
     factory/protocol and existing vector validator. Close provider resources
     correctly. Never silently substitute an all-zero, different-dimensional, or
     production deterministic vector.
   - Retrieve only minimal candidate data: ids, document presentation metadata,
     statuses, page/section, chunk content long enough for a bounded excerpt, and
     method-local rank. Do not load DocumentText, storage keys, checksums,
     metadata JSON, or stored vectors into a response path.
   - Merge by chunk id using fixed reciprocal-rank fusion. Retain method names,
     produce contiguous one-based ranks, and stabilize ties by document id then
     chunk index/id. Do not add learned ranking, cross encoders, citation logic,
     or evidence-sufficiency decisions.

5. Return safe source metadata and append minimal audit logs.

   - Make excerpts server-side and hard-bounded with deterministic truncation.
     Do not return whole chunks by default, offsets, full provenance metadata,
     embeddings, storage/parser data, or provider details.
   - Map each permitted non-approved status to the stable warning code above.
     The API returns status/codes only; Phase 14 renders them and Phase 15
     decides what supports an answer.
   - Append one retrieval.search_completed event for every successful request in
     the same successful service transaction. Link to the required case; use a
     verified workflow run as resource reference only for an internal caller.
     Store query length, requested categories, selection count,
     semantic/keyword/merged/returned counts, and method names only.
   - Do not write RetrievedSource, AgentMessage, ModelUsageRecord, evaluation,
     workflow-node, risk, or approval rows.

6. Wire settings, dependencies, errors, docs, and tests.

   - Add relational settings validation: result limit positive and no larger than
     candidate limits; selection/excerpt/query limits bounded; fusion constant
     positive. Keep safe settings representations and logs.
   - Add a dependency/factory with test overrides and no secret/network client at
     import time. Map provider/pgvector/database operational failures to one
     neutral 503 domain error without raw exception details.
   - Document supported source-status semantics, synthetic-data-only local flow,
     provider prerequisite, empty-result semantics, and the exact exclusions:
     Phase 14 UI, Phase 15 answers/citations, Phase 16 orchestration, and
     Phase 18 reranking/evidence logic.

## Required tests

### Unit tests

- Query rewriting: Unicode/whitespace normalization, Norwegian and English
  terms, punctuation/operator safety, empty-normalized rejection, configured
  max length, stable forms, and no network/model use.
- Authorization/source scope: full role matrix; approved default; explicit
  draft/deprecated behavior; restricted source/confidentiality denial/allowance;
  archived requiring exact document selection plus entitlement; auditor denial.
- Merge/ranking: semantic-only, keyword-only, overlap/deduplication, fixed
  reciprocal-rank fusion, methods retained, one-based ranks, limits, stable ties,
  and no confidence interpretation.
- Safe result construction: warning codes, nullable page/section, deterministic
  excerpt truncation, and absence of vectors, offsets, raw full chunks, storage
  key, checksum, parser metadata, provider values, task ids, citation, or answer.
- Service fakes: one query embedding, invalid/wrong-dimension/non-finite vector,
  retryable/non-retryable provider failure, empty keyword/merged set, neutral
  availability error, and provider closure.
- Audit shape: case and optional verified workflow resource linkage; permitted
  counters/status/method metadata; no query text/hash, excerpts, chunk ids,
  scores, vectors, credentials, exceptions, or SQL details.
- Settings validation and confirmation that settings/log representations do not
  leak secrets or endpoints containing credentials.

### Integration tests

- PostgreSQL semantic search with a controlled valid 1536-vector and actual
  pgvector cosine operator. Assert same-tenant indexed expected chunks rank
  above farther candidates without an external embedding provider.
- PostgreSQL keyword search with synthetic Norwegian policy terms, exact
  references, and English terms through actual simple full-text indexing.
  Operator-like input remains bound and cannot broaden to all chunks.
- Hybrid merge over overlapping candidate sets, with deduplication, method
  retention, deterministic fused order, and server-enforced limits.
- Mandatory filters: foreign tenant, physical archive, unparsed document,
  pending/indexing/failed/not-ready index states never appear even if chunk rows
  exist; only current indexed documents can appear.
- Every source status, restricted confidentiality, explicit document selection,
  archived selection, and tenant-safe known foreign ids. Assert warnings only
  for authorized returned sources.
- Case/workflow context and audit persistence: direct API-style search writes a
  case-linked safe event; verified internal workflow context uses workflow
  resource reference; mismatched/foreign contexts fail. Assert no
  retrieved_sources or other future evidence/model rows are created.
- Transaction/error behavior: no audit event survives a failed retrieval;
  availability failures stay neutral; an empty authorized result still writes one
  safe completion audit event.

### API and OpenAPI contract tests

- Cookie authentication, allowed roles, auditor/restricted denial, tenant-safe
  case/document handling, malformed ids, invalid status combinations, blank or
  oversized query, oversized selection, and out-of-range limit.
- Valid approved search; explicit draft/deprecated with warnings; authorized
  restricted/archived search; unauthorized restricted request; empty 200 result;
  predictable rank ordering.
- Response redaction proving no rewrite internals, raw full chunks, vectors,
  offsets, metadata, storage keys, checksums, task ids, provider/model settings,
  RetrievedSource ids, citations, or answer.
- Audit assertions ensuring query text never appears in response logs, audit data,
  or safe errors.
- Router/OpenAPI assertions that exactly the documented search operation exists
  with cookie security and safe errors, while answer and chunk/download routes
  do not appear.

## Validation steps

Run all commands from the repository root after implementation. Do not mark the
phase complete if any required check fails.

1. Validate dependency, migration, and Compose configuration without printing
   environment values.

       uv lock --check
       docker compose --env-file .env.example config --quiet

2. Run focused retrieval tests, then the complete backend suite.

       uv run pytest apps/api/tests/unit -k retrieval
       uv run pytest apps/api/tests/integration -k retrieval
       uv run pytest apps/api/tests/api -k retrieval
       uv run pytest apps/api/tests
       pnpm test:api

3. Run workspace formatting, linting, strict typing, and frontend regression
   checks. This phase adds no frontend feature but must not regress the workspace.

       pnpm check:workspace
       pnpm format:check
       pnpm lint
       pnpm typecheck
       pnpm test:web
       pnpm --filter @nordic-regulated-ai-agent-platform/web build

4. From a clean Compose environment, migrate and verify health before manual
   search. Use synthetic documents only; do not print passwords, cookies,
   provider credentials, raw queries/documents, or retrieved excerpts.

       pnpm dev:up
       docker compose --env-file .env.example exec -T api uv run alembic -c apps/api/alembic.ini upgrade head
       pnpm verify:local-stack

5. Follow the updated synthetic flow in the API docs: log in with a transient
   local account, create/select a synthetic case, wait for a synthetic document
   to become indexed, and call POST /api/retrieval/search. Confirm approved
   sources return bounded results; default search excludes non-approved and
   re-indexing sources; authorized explicit deprecated results carry warnings;
   unauthorized restricted requests are denied. Inspect only safe API/audit data.

6. Stop the stack, inspect OpenAPI and the worktree, and confirm no answer, UI,
   graph, schema workaround, or tracked sensitive test output entered the phase.

       pnpm dev:down
       git diff --check
       git status --short

## Completion criteria

- POST /api/retrieval/search is the only new public retrieval operation and
  returns bounded, typed, tenant-governed ranked source metadata/excerpts for a
  valid case-context request.
- The service uses the existing Phase 12 embedding boundary, pgvector cosine
  index, and PostgreSQL simple full-text index through separate bounded,
  parameterized queries. It merges/deduplicates deterministically with no
  reranker or answer generation.
- Every search path enforces organization, active document, parsed/indexed
  lifecycle, selected-document, source-status, and restricted-confidentiality
  predicates in SQL. Stale, archived, foreign, unauthorized, or non-current
  sources cannot leak through either retrieval method.
- Approved is safe default. Draft, deprecated, restricted, and archived behavior
  follows the explicit policy exactly, with stable warnings and no frontend-only
  authorization.
- Successful searches write one minimal content-free audit event linked to the
  case and, for verified internal context, workflow-run resource. No fake
  workflow/evidence/model rows are created and no query/source/vector/provider
  data reaches ordinary logs, audit records, or errors.
- The API exposes no raw document, full chunk, chunk metadata/offset, embedding,
  storage data, checksum, credential, task id, provider detail, citation,
  evidence decision, or generated answer.
- All required unit, integration, API/OpenAPI, full-backend, workspace, format,
  lint, type, frontend-regression, Compose, and synthetic manual checks pass.
- Only then may the implementation agent mark Phase 13 DONE in roadmap and
  update progress consistently.

## Risks and dependencies

| Risk or dependency | Required mitigation |
| --- | --- |
| Phase 12 preserves old chunks while re-indexing | Filter indexing_status indexed in both candidate queries; chunk presence alone never proves current evidence. |
| Cosine distance and full-text rank use incomparable scales | Merge method-local ranks with fixed reciprocal-rank fusion; never present fused score as confidence. |
| Query rewriting/full-text syntax changes meaning or accepts unsafe expression | Keep rewrite minimal/deterministic, bound input, use parameterized PostgreSQL search construction, test operator-like input. |
| Query embeddings are unavailable or can leak sensitive query content | Reuse validated provider, map failures to neutral 503, use fakes for tests, never log raw query or exception. |
| A known document id bypasses governance | Resolve entitlement before SQL and repeat status/confidentiality/lifecycle filters in every query. |
| retrieved_sources requires a workflow run Phase 13 does not own | Use audit events only; do not fabricate runs or change its foreign keys. |
| Evidence excerpt exposes too much content | Require retrieval authorization, include only permitted sources, hard-bound excerpts, and defer expanded context to Phase 14. |
| Later graph/RAG needs richer planning/persistence | Keep rewriter, repository, merger, results, and optional verified workflow context typed/injectable; do not prebuild LangGraph/citation persistence. |
| Existing Phase 10–12 worktree changes | Preserve them, avoid destructive Git operations, re-check status before reporting, and change only this phase file in G mode. |

## Notes for the implementation agent

- Treat this plan as the scope authority. A source search is not a
  source-grounded answer. Do not pull Phase 14 UI, Phase 15 answer/citation and
  refusal work, Phase 16 orchestration, Phase 18 reranking/evidence work, or
  Phase 23 trace UI into this phase.
- Reuse the Phase 12 EmbeddingProvider and DocumentChunk HNSW/GIN indexes. Do
  not add a vector database, second provider client, migration, or local fallback
  that silently changes production semantics.
- Routes stay thin; repositories own parameterized retrieval SQL; services own
  authorization, rewriting, embedding, merge, excerpt, and audit coordination;
  schemas own API validation/serialization. Never put source authorization in
  frontend code.
- Source status archived differs from physical archival. Both must be handled as
  specified and physical archival always wins.
- Do not hash queries for the audit trail: hashes are reversible for a small
  sensitive query vocabulary. Query text and result ids do not belong in Phase 13
  audit data or normal logs.
- Use synthetic/public/anonymized fixtures only. Never commit provider keys,
  passwords, session cookies, object-storage values, raw sensitive documents,
  generated vectors, browser traces, or manual output with retrieved content.
- Planning does not alter roadmap/progress. The implementation agent can mark
  completion only after every validation step succeeds.

