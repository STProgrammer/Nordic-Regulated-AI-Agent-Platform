# Phase 12 — Chunking, Embeddings, and Indexing

## Phase objective

Turn a successfully parsed, tenant-scoped `DocumentText` record into a durable,
version-consistent set of retrieval chunks with token counts, source-location
metadata, validated embeddings, and PostgreSQL indexes ready for Phase 13. The
work must run asynchronously through the existing Redis-backed Celery worker,
must tolerate retry and duplicate delivery safely, and must never expose parsed
text, chunks, vectors, credentials, or provider exceptions through a public API,
logs, audit data, or queue payloads.

This phase completes the **ingestion/indexing** segment only:

```text
Phase 10                    Phase 11                         Phase 12
private raw upload  ->  parse + location spans  ->  chunk + embed + persist/index
```

Phase 13 consumes the resulting index to implement retrieval. It does not belong
in this phase to add a search endpoint, a ranked-result service, source-status
filtering behavior, citations, RAG answers, or document UI.

## How this phase fits the final product

The platform must later answer questions only from governed, traceable sources.
That depends on chunk records that retain their parent document and organization,
can be traced back to pages or sections, and are represented consistently in both
semantic and exact-term indexes. This phase establishes that durable boundary:

1. Phase 11 parses a private raw object into canonical `DocumentText` plus
   ordered page/section character spans.
2. Phase 12 converts those spans into bounded, tokenizer-aware chunks without
   losing document, page, section, or character-offset provenance.
3. The worker embeds every chunk through a validated provider adapter and
   atomically replaces the document's prior index only after all new chunk rows
   are ready.
4. pgvector's existing HNSW index and PostgreSQL's existing GIN full-text index
   make those rows ready for Phase 13's authorization-aware hybrid retrieval.

The result is governed retrieval data, not a user-facing search feature. A
document being parsed or re-indexed must never yield a partly replaced chunk set.

## Relevant specification context and architecture constraints

- Roadmap Phase 12 requires tokenizer-aware chunking that preserves document
  identity, page, section, chunk index, token count, and metadata; embedding
  generation with pgvector indexing; keyword/full-text indexing for exact terms,
  policy names, numbers, and Norwegian text; and tests for persistence, vector
  index availability, full-text indexing, and re-indexing.
- PRD `FR-DOC-003` requires chunks to preserve document identity, page, section,
  and source location; embeddings plus keyword indexes; and re-indexing whenever
  parsing or embedding settings change. `FR-RAG-002` assigns hybrid retrieval and
  reranking behavior to later work. `FR-DOC-004` source-governance behavior is
  also deferred to Phase 13, even though this phase must retain the source status
  already stored on the parent `Document`.
- Architecture §§4.3–4.6, 6.4–6.7, 9.1, 10.2, 11, 13–14, and 17 require typed
  boundaries, PostgreSQL + pgvector, tokenizer-aware chunking, background work,
  structured safe logging, organization scoping, and testable services. The
  approved production embedding choices are OpenAI or Azure OpenAI; a local
  deterministic adapter may exist only as an explicitly isolated test/local
  plumbing aid, never as a quality claim or deployed default.
- Phase 4 already added `document_chunks` with `organization_id`,
  `document_id`, unique `(document_id, chunk_index)`, `page_number`,
  `section_title`, `content`, `token_count`, JSON metadata, and a non-null
  `vector(1536)` embedding. It also added
  `ix_document_chunks_embedding_hnsw` with cosine operations and
  `ix_document_chunks_content_fts` using
  `to_tsvector('simple', content)`. Reuse these exact foundations; do not add
  a second vector store, duplicate keyword index, or a parallel chunk table.
- Phase 11 already provides canonical text in the one-row-per-document
  `document_texts` table. Its `extraction_metadata.locations` values are ordered
  page/section spans with zero-based, half-open character offsets into
  `extracted_text`; PDF page labels/numbers are source-facing and one-based.
  Chunking must consume this provenanced text rather than re-reading raw object
  storage or reparsing a file.
- The existing worker has a UUID-only parsing task, idempotent claim/retry and
  reconciliation behavior, private storage access, safe audit logging, typed
  settings, and real Compose health checks. Extend this worker and its durable
  state-machine patterns instead of using in-process FastAPI background tasks or
  browser-owned task payloads.
- The existing document API deliberately returns metadata only. Its `Document`
  response excludes raw object keys, checksums, parsed text, locations, and
  worker details. Preserve that boundary. The architecture names a re-index
  operation, and the roadmap requires re-indexing behavior, so this phase may
  add a narrow metadata-only `POST /api/documents/{document_id}/reindex` request;
  it must not expose chunks or implement search.

## Existing baseline to extend

| Existing component | Required Phase 12 evolution |
| --- | --- |
| `apps/api/src/app/db/models/document.py` | Reuse `DocumentText` and `DocumentChunk` exactly as the parsed-text and retrieval-record boundary. Add only the indexing lifecycle fields needed on `Document`; preserve the fixed `1536` vector contract and existing database indexes. |
| `apps/api/migrations/versions/d69ce722c102_database_foundation.py` | Treat this as the immutable baseline. Add a forward Alembic migration for new `documents` indexing-state fields/backfill only; do not rewrite the baseline or recreate the HNSW/GIN indexes. |
| `apps/api/src/app/db/repositories/document.py` | Add focused conditional index claims, state transitions, candidate reconciliation, and atomic chunk replacement operations. Repository queries remain tenant-aware and contain no provider calls or chunking policy. |
| `apps/api/src/app/services/documents/parsing.py` | On a successful canonical-text replacement, make the document durably eligible for indexing. Preserve a previously good index when parsing a reprocess attempt fails. |
| `apps/api/src/app/services/documents/` | Add typed tokenizer/chunker, embedding-provider protocol/adapters, indexing coordinator, safe index errors, and UUID-only dispatch. Keep raw-storage parsing and document upload validation separate. |
| `apps/api/src/app/workers/` | Add an index task plus bounded retry/reconciliation for index work. The actual local worker must consume both parser and index tasks safely; parsing success must schedule indexing only after its database transaction commits. |
| `apps/api/src/app/core/config.py`, `.env.example` | Add validated, secret-safe chunking, batching, provider, and index-worker settings. Do not log model keys, endpoints with credentials, raw chunks, vectors, or request payloads. |
| `apps/api/src/app/api/*` and `services/auth/policy.py` | Add only a protected re-index request, indexing metadata to the existing safe document schema, and a pure `DocumentAction.REINDEX` policy. Do not add chunk inspection or search routes. |
| `apps/api/tests/` | Extend the current unit/integration/API split with deterministic tokenizer/provider fakes, Postgres index checks, worker-dispatch fakes, lifecycle tests, and metadata-redaction checks. |
| `docs/development.md`, `README.md` | Document the real index lifecycle, explicit provider configuration, local/test deterministic limitations, synthetic verification procedure, and the fact that retrieval/UI are still unavailable. |

## In scope

- Deterministic, tokenizer-aware conversion of canonical `DocumentText` into
  bounded chunks. Chunking starts from Phase 11's trusted location spans, never
  raw blob bytes, filenames, browser MIME data, or untrusted client offsets.
- A stable chunk contract that persists `organization_id`, `document_id`, a
  zero-based contiguous `chunk_index`, source-facing `page_number` when known,
  `section_title` when known, exact token count, content, a compact provenance
  metadata object, and exactly one finite 1536-dimensional embedding per row.
- Natural-boundary splitting inside each parser span. Prefer paragraph and
  sentence/whitespace boundaries, then make a deterministic tokenizer-safe hard
  split when a single sentence/term exceeds the limit. Never merge unrelated
  page/section spans merely to fill a chunk, and never produce a chunk with no
  source span.
- Explicit configurable chunk size and overlap measured using the tokenizer that
  the selected embedding model uses. The overlap must be bounded below the
  maximum chunk size and must not add duplicate, empty, out-of-order, or
  unbounded chunks. A long source span may yield multiple chunks carrying the
  same source locator.
- Compact chunk provenance metadata sufficient for later citation construction:
  zero-based half-open `char_start`/`char_end` offsets into `DocumentText`, the
  overlapping trusted location span(s), parser/version and language value when
  available, and an explicit chunking/embedding configuration version or model
  identifier. Do not duplicate full parsed text, raw storage data, secrets, or
  arbitrary parser output in metadata.
- An `EmbeddingProvider` protocol with bounded batch input/output, explicit
  timeout/retry semantics, order preservation, finite-number checks, and strict
  1536-dimension validation before persistence. Implement configured OpenAI and
  Azure OpenAI adapters through a narrow service boundary. Keep their HTTP/API
  details out of repositories, workers, routes, schemas, and test fixtures.
- A clearly named deterministic provider for unit tests and explicitly opted-in
  local plumbing checks only. It may be enabled only in `test` or `local`
  environments, must be blocked by configuration in staging/production, must
  return reproducible 1536-dimensional finite vectors, and must be documented as
  non-semantic. It is not a fallback for a missing production provider and must
  not be presented as RAG-quality validation.
- A durable indexing lifecycle on `Document`, with a forward migration for
  `indexing_status`, a safe `indexing_error`, and `indexed_at` (or an equally
  explicit, documented timestamp field). Use the following closed states:
  `not_ready`, `pending`, `indexing`, `indexed`, and `failed`.
  - New uploads begin `not_ready` while parsing is incomplete.
  - A first successful parse atomically marks the document `pending` for index
    work. A migration backfills already parsed documents as `pending` and all
    other existing documents as `not_ready` unless a safe equivalent is proven.
  - A conditional worker claim changes `pending` to `indexing`; duplicate tasks
    become no-ops rather than concurrent writers.
  - A successful run atomically replaces all old chunks for that document,
    changes the status to `indexed`, clears the safe error, and records the
    timestamp.
  - A permanent index/embedding failure records only a stable neutral error
    summary and moves to `failed`; transient infrastructure failures return to
    `pending` for bounded Celery retry. Neither failure path deletes the last
    complete set of chunks.
  - An authorized re-index request moves an eligible parsed document to
    `pending`, retains its current chunks until a complete replacement succeeds,
    and rejects an already-pending/indexing request with `409`.
- Atomic re-index replacement: construct and validate every candidate chunk and
  embedding before the replacement transaction; then delete the old rows and
  insert the complete new contiguous set in one transaction while finalizing
  `indexing_status`. A failed build, invalid vector, race, or rollback must leave
  no partial new index and no duplicate `(document_id, chunk_index)` rows.
- Automatic asynchronous dispatch after a successful parse commit and explicit
  re-index dispatch after the re-index request commit. Both queue payloads carry
  exactly one document UUID. Broker publication remains best effort only after a
  durable state change; a bounded periodic reconciler must recover `pending`
  documents and stale `indexing` claims after queue/worker loss.
- A dedicated logical Celery queue/task route for document indexing, or an
  equally observable isolated route, while retaining the existing single local
  worker service if it consumes both queues. Apply finite task timeouts, retry
  limits, prefetch/concurrency bounds, and safe worker-health checks. Do not
  expose task ids or broker information.
- A protected, metadata-only `POST /api/documents/{document_id}/reindex`
  operation returning `202`. It must require an active, tenant-scoped parsed
  document; apply `DocumentAction.REINDEX` to Admin, Case Worker, and Manager;
  return `401`, `403`, tenant-safe `404`, `409`, `422`, or safe `503` as
  appropriate; and publish no body or client-owned worker/provider fields.
  Compliance Reviewer and Read-only Auditor remain read-only.
- Extension of the existing safe `DocumentData` response/OpenAPI contract with
  `indexing_status`, nullable safe `indexing_error`, and `indexed_at`. No public
  response may contain a chunk body, text offsets, embeddings, object-storage
  key, checksum, model key, endpoint secret, task id, or provider exception.
- Minimal audit events for user-requested indexing and terminal index success or
  failure. Event metadata may identify the document/case, state transition,
  chunk count, token count, and non-secret model/config label. It must not record
  document content, chunk content, vectors, raw parser metadata, storage keys,
  task payloads, credentials, or raw provider errors.
- Dependency/lockfile updates for the selected tokenizer and official embedding
  client, using the repository-managed `uv` workflow. Keep type handling outside
  application namespaces if a dependency needs it; preserve Ruff and strict
  mypy compatibility.

## Out of scope

- A retrieval service, query rewriting, vector/keyword query execution,
  candidate merging, ranking/reranking, source-status filtering behavior,
  restricted-source permission behavior, citations, evidence sufficiency,
  contradiction checks, RAG answers, or retrieval logs. These start in Phase 13
  and Phase 15.
- Any frontend document list/detail page, chunk viewer, source-context viewer,
  Evidence Panel, or re-indexing control. Phase 14 owns those UI surfaces; this
  phase supplies only the safe API/status contract they will consume.
- OCR, image/handwriting processing, new file formats, reparsing libraries,
  raw-object download/preview, malware scanning, PII detection,
  prompt-injection detection, LLM summaries, structured extraction, or changes
  to Phase 11 parser semantics.
- LangGraph, workflow orchestration, model/prompt abstractions for agent graphs,
  risk/approval behavior, evaluation dashboards, observability dashboards,
  Azure IaC, deployment, retention cleanup, or production hardening beyond the
  safe behavior necessary for this phase.
- A second vector database, Qdrant, OpenSearch, Elasticsearch, a generic search
  API, database triggers that generate embeddings, client-submitted embeddings,
  client-provided token counts, client-provided source locations, or synchronous
  embedding during upload/reprocess requests.
- Rewriting `specs/roadmap.md` or `specs/progress.md` during planning. The
  implementation agent changes status only after the required validation passes.

## Data, lifecycle, and API contract

### Chunk invariants

Every persisted chunk must satisfy all of the following:

| Invariant | Required behavior |
| --- | --- |
| Tenant identity | `organization_id` comes from the parent `Document` in the database; it is never accepted from a task or client. |
| Parent identity | `document_id` references the parsed, non-archived source document. The worker must reject/no-op safely if the parent no longer qualifies. |
| Ordering | `chunk_index` is contiguous and zero-based for one complete index generation. The existing database uniqueness constraint remains the final guard. |
| Tokenization | `token_count` equals the configured tokenizer's count for exactly the stored `content`; it is positive and no greater than the configured maximum. |
| Provenance | `char_start`/`char_end` are valid half-open offsets into the canonical text. Location metadata is ordered, compact, and inherited only from overlapping Phase 11 spans. |
| Page/section labels | `page_number` retains the source-facing value where a chunk maps to one page. `section_title` derives only from trusted parser labels. Mixed/unknown values are nullable; no invented citation location is allowed. |
| Embedding | The vector is finite, ordered with the input batch, and exactly `EMBEDDING_DIMENSIONS` (1536) values before it reaches `Vector(1536)`. |
| Text safety | Chunk content is intentional retrieval data in PostgreSQL, but it is not copied into API metadata, audit events, logs, Celery messages, or documentation examples. |

### Indexing-state transitions

| Current state | Event | Next state | Required effect |
| --- | --- | --- | --- |
| `not_ready` | First parse succeeds | `pending` | Canonical text exists and is durably eligible for indexing; old chunks do not exist for a first parse. |
| `pending` | Worker conditionally claims document | `indexing` | One worker owns this index generation. Duplicate deliveries leave the state unchanged and return a safe no-op. |
| `indexing` | All chunks/embeddings validate and replacement transaction commits | `indexed` | Atomically replace all document chunks, clear safe error, set `indexed_at`, and emit terminal audit event. |
| `indexing` | Permanent tokenizer/content/provider/vector failure | `failed` | Persist only a neutral error summary; retain prior complete chunks if any; emit a safe failure event. |
| `indexing` | Transient provider/database/worker failure | `pending` then bounded retry | Do not add partial rows. On exhausted retry, use the safe `failed` transition. |
| `failed` or `indexed` | Authorized `reindex` request | `pending` | Keep old chunks until an atomically complete replacement succeeds; audit request and schedule/reconcile one UUID-only task. |
| `indexing` | Duplicate task/re-index request | unchanged / `409` for request | Never allow concurrent replacements. |
| any indexed state | Reprocess parse fails | unchanged | Preserve the last-good text and index exactly as Phase 11 preserves parsing output. |
| `indexed` | Reprocess parse succeeds | `pending` | The old chunk set remains durable but must not be treated as current by later retrieval until the new index reaches `indexed`. Phase 13 must honor this state. |

`DocumentText` remains one canonical record per document. It is not duplicated
per chunk; each chunk contains only its own retrieval content plus compact
provenance metadata.

### Public API addition

| Operation | Response | Contract |
| --- | --- | --- |
| `POST /api/documents/{document_id}/reindex` | `202` standard success envelope with expanded safe `DocumentData` | Tenant-scoped, parsed-document-only, Admin/Case Worker/Manager action. No request body, no raw content, no provider fields. `409` when pending/indexing, `422` when parsing has not produced usable text, and safe `503` when post-commit dispatch is unavailable while reconciliation retains durable pending work. |

Keep `POST /api/documents/upload`, `GET /api/documents/{document_id}`, and
`POST /api/documents/{document_id}/reprocess` backward compatible except for
the additive safe indexing metadata fields. Document that `GET` remains metadata
only and is not a chunk, search, or retrieval endpoint.

## Likely files, folders, modules, and services affected

| Area | Expected changes |
| --- | --- |
| `apps/api/migrations/versions/` | Add one forward migration for indexing lifecycle fields, check/default constraints if consistent with repository conventions, backfill of existing parsed documents, and a safe downgrade. Do not alter the Phase 4 baseline migration. |
| `apps/api/src/app/db/models/document.py`, `db/base.py` | Add typed indexing lifecycle fields/enums while retaining the current `DocumentChunk`, 1536-dimension vector, HNSW cosine index, GIN `simple` full-text index, and parent relationships. |
| `apps/api/src/app/db/repositories/document.py` | Add conditional index claim/release/fail/complete/reindex helpers; bounded pending/stale candidate queries; parsed-text loading; and one transaction-safe delete-and-insert chunk replacement path. |
| `apps/api/src/app/services/documents/chunking.py` (or focused package) | Add tokenizer adapter, validated chunk policy/config, source-span mapping, natural-boundary splitter, long-span fallback, and typed chunk-candidate/provenance models. |
| `apps/api/src/app/services/documents/embeddings.py` (or focused package) | Add provider protocol, OpenAI/Azure adapters, explicit local/test deterministic adapter, batch/result validation, safe provider errors, and factory wiring. |
| `apps/api/src/app/services/documents/indexing.py` | Add worker-only index coordinator that claims work, reads canonical text, builds/embeds candidates, performs the atomic replacement, records terminal audit events, and returns a typed task outcome. |
| `apps/api/src/app/services/documents/dispatch.py`, `parsing.py`, `service.py` | Extend UUID-only dispatch with index dispatch; mark successful parse results index-pending; queue indexing after parse commit; add authorized re-index coordination without changing upload or raw-storage contracts. |
| `apps/api/src/app/workers/celery_app.py`, `workers/tasks.py`, worker Docker/Compose/verifier | Register/rout index tasks, finite retries and reconciliation, consume both logical queues, preserve beat and health behavior, and keep no secrets/task payloads in output. |
| `apps/api/src/app/core/config.py`, `.env.example`, `apps/api/pyproject.toml`, `uv.lock` | Add validated chunk/overlap/batch/model/provider/timeouts/retry settings, secret values, tokenizer/embedding dependencies, and lockfile updates. |
| `apps/api/src/app/services/auth/policy.py`, `api/schemas/documents.py`, `api/routes/documents.py`, `api/dependencies.py`, `services/errors.py` | Add pure re-index authorization, safe indexing status schema, narrow request transport, injected dispatcher/provider seams, safe conflict/unavailable error mapping, and OpenAPI declarations. |
| `apps/api/tests/unit/` | Add chunker, tokenizer, provenance, embedding adapter/fake, lifecycle, policy, settings, dispatcher, and metadata-redaction tests. |
| `apps/api/tests/integration/` | Add PostgreSQL-backed chunk persistence/replacement/rollback/tenant-isolation tests and pgvector/full-text catalog/query evidence using synthetic text. |
| `apps/api/tests/api/` | Add re-index transport/RBAC/state/OpenAPI/metadata-only response tests with injected services/dispatchers. |
| `docs/development.md`, `README.md` | Update worker/index operations, provider setup/redaction, synthetic-only validation, index state meanings, local deterministic limitations, and clear Phase 13/14 exclusions. |

## Implementation tasks

1. **Freeze the indexing lifecycle and safe public contract.**

   - Define a closed indexing-status enum and stable neutral indexing error
     summaries/codes. Keep parsing and indexing status separate; neither is a
     substitute for source status, case status, workflow status, or audit state.
   - Add a forward migration and typed model fields for `indexing_status`,
     `indexing_error`, and `indexed_at`. Set new upload defaults to `not_ready`;
     backfill existing parsed rows to `pending` so the reconciler can index them.
     Write and test a downgrade that removes only Phase 12 additions.
   - Expand only the existing safe document response with the three lifecycle
     fields. Assert response serialization excludes all chunk, text, provider,
     storage, checksum, and task implementation data.
   - Specify re-index eligibility precisely: it requires an active current-tenant
     document with `parsing_status="parsed"` and canonical text. Define the
     stable API behavior for not-ready/failed parsing, active indexing, a
     missing/archived document, and a queue outage.

2. **Build a tokenizer-aware, provenance-preserving chunker.**

   - Choose and configure a tokenizer compatible with the production embedding
     model (for example an explicit tokenizer encoding rather than guessing from
     a deployment name). Put size, overlap, minimum content, and maximum chunks
     per document behind validated settings with clear conservative defaults.
   - Define typed input/output structures for canonical text, trusted parser
     spans, chunk candidates, and compact provenance. Validate all incoming
     location spans before chunking; malformed metadata fails safely rather than
     inventing a citation location.
   - Split inside one trusted source span at natural text boundaries first. For a
     long span, hard split deterministically while honoring token size and
     overlap. Preserve stable order and calculate offsets against the unmodified
     canonical text; never use character count as a token-count proxy.
   - Derive nullable `page_number`/`section_title` only where provenance is
     unambiguous. Retain all overlapping span locators in metadata when needed,
     without flattening spans into an unbounded duplicate text structure.
   - Enforce every candidate's non-empty content, exact token count, bounded
     token limit, contiguous planned index, valid offsets, compact metadata, and
     bounded total chunk count before any embedding call.

3. **Add a narrow, validated embedding-provider boundary.**

   - Define a provider protocol accepting ordered bounded batches and returning
     the same number of ordered vectors. Wrap provider exceptions in neutral
     domain errors that distinguish retryable infrastructure issues from
     permanent configuration/response/input failures without retaining raw
     messages.
   - Add OpenAI and Azure OpenAI adapter implementations selected by typed
     configuration. Use `SecretStr` for keys, validate a 1536-dimensional model
     or deployment contract, cap batch size/timeouts/retries, and never emit
     request bodies or headers to logs.
   - Add the deterministic provider only behind explicit `test`/`local`
     configuration gates. Its vectors must be repeatable, finite, correctly
     sized, and clearly non-semantic in code/doc comments and docs.
   - Validate vector count, ordering, dimension, finiteness, and batch result
     association before persistence. A provider returning an incorrect count or
     dimension must fail the index safely and never partially write a chunk set.

4. **Make index persistence atomic, idempotent, and tenant-safe.**

   - Add repository methods that atomically claim `pending` indexing work and
     load the parent `Document` plus its single canonical `DocumentText` only
     after a claim. Derive organization/document identifiers from PostgreSQL,
     never a task payload.
   - Build chunk candidates and embeddings outside the replacement transaction;
     then in one transaction conditionally confirm the claim, delete all prior
     chunks for that parent, bulk insert the complete validated replacement,
     finalize `indexed`, clear the safe error, set `indexed_at`, and append the
     terminal audit event.
   - On permanent failures move only the lifecycle state to `failed` and retain
     any prior complete chunks. On transient database/provider/worker failures
     return the claim to `pending` for finite retry. Include stale-claim recovery
     that cannot race an active worker.
   - Ensure parsing success sets `indexing_status` to `pending` as part of its
     canonical-text persistence, but do not erase a last-good index merely
     because a reparse later fails. Make these cross-phase invariants explicit in
     repository and coordinator tests.

5. **Extend the real worker and durable scheduling path.**

   - Extend `DocumentTaskDispatcher` with a second UUID-only `dispatch_index`
     method. Keep the parser and index task arguments to exactly a document UUID
     string; the worker derives all tenancy, text, provider, and status state.
   - After a parse task reports a committed successful parse, publish its index
     task. Immediate publication is best effort; a document remains `pending`
     if it cannot be published and the reconciler must recover it.
   - Add an index task with the same explicit outcome model as parsing,
     bounded exponential retry, exhausted-retry terminal failure handling, and
     `acks_late`/worker-loss safeguards. Add a bounded periodic reconciler for
     pending documents and stale indexing leases.
   - Route indexing observably (prefer a separate `document-indexer` queue) and
     make the existing Compose worker consume the registered parser/index tasks.
     Update worker readiness so it still verifies the live named consumer and
     does not turn into a process-only health check.

6. **Expose controlled re-indexing without exposing retrieval data.**

   - Add `DocumentAction.REINDEX` with the same mutation roles as reprocessing:
     Admin, Case Worker, and Manager. Test it exhaustively; reviewer/auditor
     roles may read status but cannot queue work.
   - Add a thin `DocumentService.reindex` method that authorizes, does a
     tenant-scoped conditional state transition, records a minimal request audit
     event, commits, and only then calls the dispatcher. Retain the durable
     pending state if post-commit dispatch fails so reconciliation can recover.
   - Add the metadata-only route/schema/OpenAPI contract and use injectable
     fakes in API tests. Do not add a public `GET .../chunks`, content endpoint,
     search endpoint, or frontend control.

7. **Prove the database indexes and indexing lifecycle, then update docs.**

   - Exercise actual PostgreSQL/pgvector persistence in integration tests:
     correct 1536-length vectors persist, the existing HNSW cosine index is
     present, and the existing GIN `simple` full-text expression indexes
     synthetic Norwegian terms, reference numbers, and policy-like exact text.
     These are storage/index assertions only, not a new retrieval service.
   - Add documentation for provider configuration using environment-variable
     names only, local deterministic limitations, token/chunk settings, index
     state meanings, safe re-index/reconciliation behavior, and the fact that
     Phase 13 owns query behavior. Keep manual examples synthetic and avoid
     values that disclose credentials, session cookies, blob keys, or document
     bodies.
   - Update local Compose/verifier instructions if worker queue/health behavior
     changes. Preserve the explicit-migrations/no-automatic-seed contract.

## Required tests

### Unit tests

- Tokenizer configuration and validation: model/encoding selection, valid
  maximum-token/overlap relationships, batch limits, invalid values, and strict
  local/test-only deterministic-provider gating.
- Chunking of Norwegian and English synthetic canonical text: exact token counts,
  natural splitting, deterministic hard split, overlap behavior, no empty chunks,
  stable contiguous indexes, and bounded total output.
- Provenance mapping: page and section labels, character offsets, multiple chunks
  from one long span, no cross-span merge, malformed/out-of-range/overlapping
  parser-span rejection, and compact metadata without duplicated document text.
- Embedding provider protocol behavior: stable deterministic vectors, OpenAI/Azure
  request boundary with mocked transport, batch ordering/count validation,
  incorrect dimensions, NaN/infinite values, timeouts, retryable failures, and
  redaction of raw provider responses.
- Pure indexing lifecycle and authorization: all state transitions, active-work
  conflict, parsed-text eligibility, failed-parse behavior, duplicate task no-op,
  reprocess/index interaction, `DocumentAction.REINDEX` role matrix, and safe
  audit event shapes.
- Configuration/logging/error tests that prove keys, endpoints containing
  credentials, chunk bodies, vectors, and provider exceptions never reach safe
  settings representations, logs, errors, audit metadata, or task messages.

### Integration tests

- PostgreSQL-backed successful indexing of a parsed synthetic document: one
  tenant-safe parent, contiguous rows, exact metadata/token counts, validated
  1536-length vectors, correct `indexed` state/timestamp, and terminal audit
  event.
- Database evidence that `ix_document_chunks_embedding_hnsw` exists with cosine
  vector operations and `ix_document_chunks_content_fts` is a GIN `simple`
  full-text index. Execute a direct synthetic SQL assertion showing exact
  Norwegian terms/reference numbers can be indexed and matched; do not add a
  production retrieval helper solely for this test.
- Atomic re-index replacement: changed canonical text replaces the whole old
  chunk set, preserves the unique `(document_id, chunk_index)` invariant, leaves
  no partial rows on forced provider/database failure, and keeps the last-good
  rows when a re-index cannot complete.
- Tenant isolation: a foreign organization cannot claim, re-index, replace, or
  observe another tenant's metadata/chunks; archived/not-ready documents are
  safely excluded.
- Duplicate delivery, stale-claim recovery, pending reconciliation, transient
  retry/exhaustion, wrong-dimension provider response, and post-parse missed
  dispatch recovery. Assert every task message/fake dispatcher receives only a
  document UUID.
- Migration upgrade/backfill and downgrade/re-upgrade from the current Phase 11
  schema, including that existing parsed documents become indexable and the
  pre-existing pgvector/full-text indexes remain intact.

### API and worker contract tests

- `GET /api/documents/{document_id}` and existing upload/reprocess responses
  serialize additive indexing metadata but never canonical text, chunk content,
  offsets, vectors, object keys, checksums, credentials, or task identifiers.
- `POST /api/documents/{document_id}/reindex` covers session enforcement,
  role matrix, tenant-safe not-found behavior, parsed eligibility, pending/
  indexing `409`, safe dispatcher failure, state transition, and the standard
  `202` envelope.
- OpenAPI includes the new status fields, documented cookie security, and all
  relevant safe error models; no misleading chunk/search endpoint appears.
- Worker task tests cover UUID parsing, safe no-op behavior, bounded retry,
  exhausted retry finalization, parser-success-to-index dispatch only after
  durable success, and reconciliation without raw data/provider leakage.

## Validation steps

Run all commands from the repository root after implementation. Do not mark the
phase complete if any required check fails.

1. Refresh and verify dependency/migration/Compose definitions without exposing
   environment values:

   ```bash
   uv lock --check
   docker compose --env-file .env.example config --quiet
   ```

2. Run the focused chunking, embedding, lifecycle, worker, API, and PostgreSQL
   tests first; then run the entire backend suite:

   ```bash
   uv run pytest apps/api/tests/unit apps/api/tests/integration apps/api/tests/api
   pnpm test:api
   ```

3. Run all workspace formatting, lint, strict typing, and existing frontend
   regression checks even though this phase adds no frontend feature:

   ```bash
   pnpm check:workspace
   pnpm format:check
   pnpm lint
   pnpm typecheck
   pnpm test:web
   pnpm --filter @nordic-regulated-ai-agent-platform/web build
   ```

4. From a clean local Compose environment, prove the migration state and real
   parser/index worker health. Use only synthetic data and never echo
   passwords, cookies, provider credentials, blob keys, chunk content, or
   vectors:

   ```bash
   pnpm dev:up
   docker compose --env-file .env.example exec -T api uv run alembic -c apps/api/alembic.ini current
   pnpm verify:local-stack
   ```

5. Follow the updated documented synthetic manual flow with an explicitly
   configured permitted provider (or the clearly labelled local deterministic
   plumbing mode): upload/parse a safe document, poll metadata until `indexed`,
   request re-indexing, confirm the status returns to `indexed`, and inspect only
   safe metadata/audit fields. Confirm a provider failure produces a neutral
   `failed` state with no partial index. Then stop the stack:

   ```bash
   pnpm dev:down
   ```

6. Inspect OpenAPI and the final worktree. Confirm the changes remain within
   Phase 12, generated outputs are untracked/ignored, no secrets or raw
   documents are tracked, and neither Phase 13 retrieval behavior nor Phase 14
   UI work slipped into the implementation.

## Completion criteria

- A successfully parsed document is chunked asynchronously using a real
  tokenizer-aware policy, with complete document/tenant/page/section/offset
  provenance, deterministic ordering, accurate token counts, and bounded
  overlap.
- Each persisted chunk has exactly one finite 1536-dimensional vector, and the
  existing pgvector HNSW cosine and PostgreSQL GIN full-text indexes are proven
  available by database-backed tests.
- The system has no second vector/index store and no public retrieval/search
  surface. It is ready for Phase 13 to query safely, but does not implement that
  behavior early.
- The indexing lifecycle is durable, tenant-safe, idempotent, retry-bounded, and
  reconciliation-capable. Queue outages or worker loss leave truthful pending/
  failed state, not a silent loss or a false success.
- Re-indexing is an authorized, metadata-only asynchronous operation. It atomically
  replaces a complete chunk set, retains prior chunks through failed replacement,
  rejects concurrent runs, is fully audited without content leakage, and is
  documented in OpenAPI.
- Parsing-to-index handoff uses committed state and UUID-only queue messages;
  automatic scheduling plus reconciliation can recover missed publication and
  stale claims.
- Provider credentials, raw chunks/text, vectors, storage details, checksums,
  provider exceptions, and task ids are absent from API responses, error payloads,
  logs, audit metadata, task payloads, docs examples, and tracked files.
- All required migration, dependency, unit, integration, API, worker, full-suite,
  formatting, lint, type, workspace, frontend-regression, Compose, and local
  validation checks pass.
- Only after all criteria pass may the implementation agent mark Phase 12
  `(DONE)` in `specs/roadmap.md` and update `specs/progress.md` consistently.

## Risks and dependencies

| Risk or dependency | Required mitigation |
| --- | --- |
| Embedding providers can be unavailable, rate limited, expensive, or return a different dimension than the database contract. | Use typed adapters, finite bounded batches, explicit timeout/retry classification, strict 1536-vector validation, safe failure status, and test fakes. Never silently substitute an unknown model/vector dimension. |
| Token count and model input limits can drift if the embedding deployment name is not a known tokenizer name. | Configure an explicit compatible tokenizer encoding, validate it at startup/factory construction, test its output, and record a non-secret model/config label in chunk metadata. |
| Re-indexing can expose partly new/partly old evidence or delete the last good index. | Build/validate candidates first, then atomically replace rows and state; retain prior chunks on all failure paths; use conditional claims and transaction rollback tests. |
| A parse commit and broker publish are not atomic. | Persist `pending` in the parse transaction, publish only afterward, and reconcile pending/stale work with UUID-only idempotent tasks. |
| Parsing a reprocess result can make existing chunks stale before replacement finishes. | Move the index to `pending` only after canonical text commits, preserve old rows physically, and require Phase 13 to consider only `indexed` documents current. Document and test this handoff. |
| The GIN `simple` index is language-neutral rather than a Norwegian linguistic stemmer. | Retain the architecture-approved `simple` exact-term index for policy names/numbers/Norwegian text. Do not introduce a language-specific search/retrieval design before Phase 13 validates requirements. |
| Existing Phase 4 indexes/schema may be modified accidentally while adding status fields. | Add a narrow forward migration, verify catalog/index contracts before and after migration, and never rewrite the baseline migration. |
| Local no-key development must not masquerade as semantic AI quality. | Make deterministic embedding explicit, local/test-only, and non-semantic; document it as plumbing validation. Require a configured approved provider for real embedding behavior. |
| Documents can contain sensitive content even when project fixtures are synthetic. | Keep content in governed database rows only, use UUID-only tasks, redact logs/audit/API, avoid fixture bodies in operational output, and use safe synthetic inputs exclusively. |

## Notes for the implementation agent

- Treat this file as the primary scope authority. Consult the PRD/architecture
  only to resolve a genuine ambiguity; do not pull Phase 13 retrieval, Phase 14
  document/evidence UI, Phase 15 RAG, or Phase 16 graph provider abstraction
  into this implementation.
- Preserve all existing worktree changes. The current repository may contain
  uncommitted completed Phase 10/11 work; do not reset, overwrite, or clean up
  unrelated files. Re-check `git status --short` before reporting changed files.
- Keep route handlers thin. Tokenization, embedding adapters, index lifecycle,
  retries, and audit composition belong in typed services/adapters; repositories
  own SQL predicates and persistence only; Celery tasks orchestrate UUID-only
  work without carrying content or provider configuration.
- The existing Phase 4 `DocumentChunk` schema already declares a non-null
  1536-dimensional vector and HNSW/GIN indexes. Preserve it unless a real
  migration constraint proves incompatible; do not introduce Qdrant/OpenSearch
  or silently change vector dimensions.
- Avoid mutable global embedding clients or configuration initialized with
  secrets at import time. Keep factories injectable for tests, build clients at
  use time, close them appropriately, and ensure safe `AppSettings` construction
  still works in unit/API tests without live provider credentials.
- A document/index state is not a source-governance decision. Do not add
  approved/draft/deprecated/restricted/archived retrieval behavior here; retain
  the parent metadata for Phase 13's backend-enforced filtering.
- Use synthetic/public/anonymized inputs only. Never commit provider keys,
  passwords, session cookies, storage values, raw source documents, raw chunk
  text in docs/logs, or embeddings generated from sensitive material.
