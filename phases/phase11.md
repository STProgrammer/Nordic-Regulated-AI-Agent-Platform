# Phase 11 — Document Parsing Pipeline

## Phase objective

Turn each securely stored Phase 10 document into one durable, tenant-safe
parsed-text record without ever exposing raw object-storage details or blocking
an API request. The system must submit parsing to a Redis-backed background
worker, extract readable text and format-specific context for every currently
supported input type, detect the document language, and make parsing progress
and failures safely inspectable through metadata-only API responses.

This phase completes the **parsing** segment of ingestion only:

```text
Phase 10                         Phase 11                         Phase 12
validate + private raw storage → parse + preserve context/text → chunk + embed + index
```

It must be safe to retry a failed parse or intentionally reprocess a parsed
document. A failed job must not damage the raw object, its Case, its audit
trail, or a previously successful `document_texts` record.

## How this phase fits the final product

Document parsing converts a governed raw upload into the canonical text that
Phase 12 will chunk, embed, and index. Later retrieval, evidence, workflow,
and document-UI phases rely on this boundary to provide accurate source
location metadata. The implementation therefore needs to preserve page or
section context now instead of attempting to reconstruct it from flattened text
later.

The user-facing workflow remains deliberately narrow in this phase:

1. A Phase 10 upload commits raw metadata with `parsing_status="pending"`.
2. The API schedules a parsing job that carries identifiers only, never bytes,
   credentials, a storage key, or document text.
3. A worker reads the object privately, verifies it against stored integrity
   metadata, parses it under bounded resource rules, and persists text/context
   atomically.
4. The document becomes `parsed` or `failed`; an authorized caller can request
   another parse without a browser document viewer or retrieval feature.

## Relevant specification context and architecture constraints

- Roadmap Phase 11 requires background parsing for supported formats, safe
  errors, separate parsed text, page/section context where available, language
  detection, parsing status/error summaries, and reprocessing. Parser tests
  must cover every supported type and prove a failure cannot corrupt Case or
  Document state.
- PRD `FR-DOC-002` requires readable text and metadata separate from raw file
  storage, with filename/type/size/checksum/language/page count/uploader
  metadata and safe displayed parsing errors. `FR-DOC-003` defers chunks,
  embeddings, and search to Phase 12. `FR-AUDIT-001`, reliability requirements,
  and privacy requirements require important processing events, bounded retries,
  tenant isolation, and no secret or unnecessary document-content logging.
- Architecture §§4.4–4.6, 6.5–6.7, 9.1, 10.2, 13.3, 14, and 17 require the
  document service to parse PDF/DOCX/TXT/Markdown/CSV/XLSX/EML, use background
  workers with Redis, retain object storage outside PostgreSQL, persist
  `document_texts`, use structured safe logging, and test parsing utilities
  plus upload/indexing flows. The chosen stack permits Celery + Redis for this
  worker boundary and format-specific libraries such as `pypdf`,
  `python-docx`, and `openpyxl`.
- Phases 1–10 are complete. Phase 10 already provides: private Azure
  Blob-compatible raw storage; a server-owned object key; a verified allowed
  format/type/checksum/size boundary; `Document` rows initialized as `pending`;
  `DocumentText` with one record per document; an async SQLAlchemy service and
  repository layer; Redis; and a Compose `worker` that is currently
  readiness-only. Extend these pieces rather than duplicating raw storage,
  document metadata, or tenant predicates.
- The existing database model has the correct Phase 11 persistence shape:
  `documents.language`, `documents.page_count`, `documents.parsing_status`,
  `documents.parsing_error`, and one `document_texts` row containing
  `extracted_text` and JSON `extraction_metadata`. Do not store parsed text in
  `documents`, `audit_events`, Celery messages, logs, or API error payloads.
- The existing upload policy permits Admin, Case Worker, and Manager. New
  document actions must use the same pure policy layer and tenant-scoped lookup
  conventions; no browser-side authorization is acceptable.

## Existing baseline to extend

| Existing component | Required Phase 11 evolution |
| --- | --- |
| `apps/api/src/app/db/models/document.py` | Reuse `Document`, `DocumentText`, and their one-text-record relationship. Add a migration only if an objectively necessary new persistence field/index is introduced; none is expected for the defined contract. |
| `apps/api/src/app/db/repositories/document.py` | Add focused tenant-safe claim, state-transition, and text upsert operations. Keep raw-object operations out of the repository. |
| `apps/api/src/app/services/documents/storage.py` | Extend the private storage protocol/adapter with a bounded read operation. It must not create URLs or disclose keys. |
| `apps/api/src/app/services/documents/service.py` | Retain secure upload behavior, schedule parsing only after the upload is durable, coordinate user-requested reprocessing, and expose no direct raw content operation. |
| `apps/api/src/app/services/documents/validator.py` | Keep Phase 10 validation as the first barrier; parsers must still fail closed if a stored object is inconsistent or malformed. |
| `apps/api/src/app/workers/readiness.py` and `docker-compose.yml` | Replace the readiness-only runtime with the real parser worker while preserving an observable, non-sensitive worker health/readiness contract for local validation. |
| `apps/api/src/app/api/routes/documents.py`, schemas, and dependencies | Add only status/detail/reprocessing APIs and injectable dispatcher/service dependencies. Continue to omit blob keys, checksums, raw text, excerpts, and storage URLs. |
| `apps/api/tests/` | Extend the existing unit/API/integration split with deterministic parser fixtures, queue-dispatch fakes, and database-backed lifecycle assertions. |

## In scope

- A Celery + Redis parser queue and worker process, configured from typed
  `AppSettings` and Compose without hard-coded credentials. The task payload is
  only the document UUID; it must derive all tenancy, storage, and integrity
  data from the database in the worker.
- Automatic scheduling of a successfully committed Phase 10 upload, plus
  durable reconciliation of `pending` documents so a temporary broker failure
  cannot leave a valid upload permanently unprocessed. Queue dispatch failures
  are observable through safe logs/status but never delete a successfully
  uploaded document.
- A finite state machine with `pending`, `processing`, `parsed`, and `failed`
  states; safe terminal error codes/summaries; guarded transitions; idempotent
  duplicate task behavior; and bounded retry only for transient infrastructure
  failures.
- A private storage read that checks the stored raw bytes against the existing
  `file_size_bytes` and SHA-256 before parsing. A mismatch must fail safely and
  must not overwrite existing parsed text.
- Parser implementations for PDF, DOCX, TXT, Markdown, CSV, XLSX, EML, and
  pasted email (already stored as EML):
  - PDF: extract page-ordered text and page count with page context.
  - DOCX: extract paragraph text and preserve headings/section association when
    available.
  - TXT: preserve plain text as one logical text section.
  - Markdown: preserve heading-delimited sections.
  - CSV: produce a deterministic, readable tabular representation and retain
    header/row context without converting values into inferred business fields.
  - XLSX: produce deterministic worksheet/row text and preserve worksheet names
    as section context; do not evaluate formulas or infer values beyond the
    saved workbook representation.
  - EML: parse standard message headers and readable text body safely; prefer
    plain text and use a bounded, dependency-light HTML-to-text fallback only
    when no plain-text body exists. Do not fetch remote content or process
    attachments in this phase.
- One canonical `DocumentText` upsert on success. Store normalized extracted
  text plus compact JSON extraction metadata sufficient for Phase 12 to retain
  location context: parser/version, trusted file type, detected language and
  confidence/unknown result, text length, page count where meaningful, and an
  ordered list of page/section spans with character offsets. Do not put raw
  storage/provider details, secrets, or unbounded duplicate text into metadata.
- Language detection over the extracted text, returning a stable supported
  value such as `nb`, `en`, or `unknown` (with a confidence threshold) rather
  than claiming a language from filename or browser metadata. Norwegian Bokmål
  and English must be covered explicitly.
- Safe parsing metadata updates: set `language`, `page_count` where applicable,
  `parsing_status`, and a cleared or safe `parsing_error`. Persist a
  non-sensitive code/summary on failure, never raw library exceptions, raw
  content, filenames, object keys, credentials, or stack traces.
- A protected metadata-only document-status/detail operation and a
  `POST /api/documents/{document_id}/reprocess` operation that returns `202`
  after safely requesting reprocessing. Reprocessing is backend-authorized for
  Admin, Case Worker, and Manager, tenant-scoped, rejected while actively
  `processing`, and available for `pending`, `failed`, or `parsed` documents.
  It is API support only; Phase 14 owns controls and document UI.
- Minimal audit events for a user-initiated reprocess request and parser
  terminal success/failure. Event data may include document id/case id, trusted
  type, transition, language, page count, text length, and a safe failure code;
  it must not include document text, filename, object key, checksum, parser
  exception, Celery task payload, or credentials.
- Typed configuration for queue/broker, worker concurrency, task timeout/retry,
  pending-job reconciliation interval, maximum extracted characters/sections,
  and language-confidence threshold. Defaults must be conservative, validated,
  documented, and overrideable in tests.
- Required dependency and lockfile updates for the chosen worker, parser, and
  language-detector libraries. Use the minimum supported libraries; do not add
  OCR, a general `unstructured` pipeline, external AI calls, or cloud services
  merely for parsing.
- Accurate local development/operations documentation covering worker startup,
  synthetic test inputs, safe status/reprocess verification, queue health, and
  cleanup. Continue to state that document preview, download, UI, chunking, and
  retrieval are unavailable.

## Out of scope

- Tokenizer-aware chunking, token counts, embeddings, pgvector/full-text
  indexing, indexing status, source snippets, retrieval, citations, reranking,
  or any `reindex` API semantics (Phase 12 onward).
- A document list/detail page, browser upload UI, raw-document download,
  preview, source-context viewer, evidence panel, source-governance controls,
  or end-to-end browser document workflow (Phase 14).
- OCR, image extraction, handwriting recognition, media parsing, archive
  extraction, EML attachment parsing, formula calculation, remote URL fetching,
  malware scanning, PII analysis, prompt-injection detection, LLM summaries, or
  structured business-field extraction.
- Changes to Case lifecycle/status, model workflows, LangGraph, approval,
  retrieval permissions, source-status meaning, retention cleanup, metrics
  dashboards, OpenTelemetry, Azure IaC, or production deployment.
- A public queue dashboard, arbitrary task submission, client-provided job
  arguments, client-provided storage keys/checksums, synchronous parse API,
  raw parser exception output, or a new generic document CRUD surface.
- Modifying `specs/roadmap.md` or `specs/progress.md` during planning. The
  implementation agent marks Phase 11 complete only after every required check
  passes.

## Lifecycle and API contract

### Parsing state transitions

| Current state | Event | Next state | Required effect |
| --- | --- | --- | --- |
| `pending` | Worker atomically claims job | `processing` | Clear a stale safe error; leave any prior `DocumentText` untouched. |
| `processing` | Parse and persistence succeed | `parsed` | Atomically replace/create the single `DocumentText`, update language/page count, clear error, and emit safe success audit event. |
| `processing` | Permanent parse/integrity error | `failed` | Record only a stable safe error code/summary, preserve an existing `DocumentText`, and emit safe failure audit event. |
| `processing` | Transient storage/database/worker error | `pending` then bounded retry | Do not write a terminal parse result until retries are exhausted; on exhaustion use the safe `failed` transition. |
| `failed` or `parsed` | Authorized reprocess request | `pending` | Clear previous error, preserve old text until a replacement succeeds, record request audit event, and schedule/reconcile one job. |
| `processing` | Duplicate task or reprocess request | unchanged / `409` for request | Do not run concurrent parsing or create a second text record. |

`DocumentText` must never be deleted before its replacement has parsed and
validated successfully. This is the key no-corruption rule for reprocessing.
The worker must use a transaction/row lock or conditional update to claim work
so retries and duplicate Celery deliveries cannot produce competing writes.

### Public API additions

Add a narrowly scoped protected document operation group:

| Operation | Response | Contract |
| --- | --- | --- |
| `GET /api/documents/{document_id}` | Existing safe metadata shape, expanded for parsing status, language, page count, and safe error summary | Tenant-scoped metadata only; never raw object/text/key/checksum. Apply a pure document-read policy suitable for all authenticated roles that may already see the related Case, subject to the current backend Case policy. |
| `POST /api/documents/{document_id}/reprocess` | `202` safe metadata/status envelope | Admin, Case Worker, or Manager only; tenant-scoped; `409` while `processing`; no body, raw content, or client-owned queue fields. |

Keep the existing `POST /api/documents/upload` response contract compatible.
It may expose the expanded parsing-status enum, but it must still return only
safe metadata and must not wait for parsing to finish.

Document the final status/error response schemas and `401`, `403`, `404`,
`409`, `422`, and `503` failures in OpenAPI. A queue outage must be represented
with the existing safe error envelope; it must never leak broker URLs, task ids,
or provider messages.

## Likely files, folders, modules, and services affected

| Area | Expected changes |
| --- | --- |
| `apps/api/pyproject.toml`, `uv.lock` | Add pinned-compatible Celery/Redis worker and minimal local parser/language dependencies; update lockfile through the repository toolchain. |
| `apps/api/src/app/core/config.py`, `.env.example` | Add validated queue/parser limits and environment-safe defaults with secret redaction. |
| `apps/api/src/app/workers/` | Add Celery application, document parsing task, bounded retry routing, task-registration/import-safe entrypoint, reconciliation scheduler, and worker health/readiness support. Retire the readiness-only assumption without removing the health contract. |
| `docker-compose.yml`, `infra/docker/worker.dev.Dockerfile`, `scripts/verify_local_stack.sh` | Start the actual parser worker, preserve loopback-only local checks, make worker readiness prove broker/task-consumer availability safely, and retain no automatic migrations/seeding. |
| `apps/api/src/app/services/documents/parsers/` | Add typed parser protocol, parsed-result/location models, per-format parsers, language detector adapter, parser registry, bounded normalization, and neutral parser errors. |
| `apps/api/src/app/services/documents/storage.py` | Add bounded private read support and an Azure/Azurite implementation; keep no URL/public-access capability. |
| `apps/api/src/app/services/documents/service.py` | Add scheduling/reprocessing coordination and a worker-facing parse coordinator that loads tenant-owned metadata, verifies integrity, claims state, and persists outcomes. |
| `apps/api/src/app/db/repositories/document.py` | Add explicit tenant-scoped metadata fetch, conditional claim/transition helpers, and atomic `DocumentText` upsert support. |
| `apps/api/src/app/services/auth/policy.py` | Add focused `DocumentAction.READ` and `DocumentAction.REPROCESS` rules with exhaustive role tests; do not broaden unrelated Case policies. |
| `apps/api/src/app/api/dependencies.py`, `api/routes/documents.py`, `api/schemas/documents.py` | Inject dispatcher/parse service, expose only safe status/reprocess routes, expand typed parsing-status response fields, and update OpenAPI/error declarations. |
| `apps/api/tests/unit/` | Add pure parser, location-metadata, language, integrity, state-machine, policy, dispatcher, and safe-error tests using synthetic fixtures/fakes. |
| `apps/api/tests/integration/` | Add Postgres-backed claim/upsert/reprocess/no-corruption/tenant-isolation tests and opt-in local Azurite read evidence. |
| `apps/api/tests/api/` | Add auth/RBAC/OpenAPI/metadata-redaction/reprocess transport tests with an injected dispatcher fake. |
| `docs/development.md`, `README.md` | Update the actual worker contract, queue/local verification, supported parsing behavior, known limitations, and safe manual test procedure. |

## Implementation tasks

1. **Freeze the parsing lifecycle and public safety contract.**

   - Define typed parsing status and safe parser-error-code enums. Use
     `pending`, `processing`, `parsed`, and `failed`; do not overload source
     status or Case status.
   - Define a small typed parser result containing normalized full text,
     ordered location spans, page count, parser metadata, and language result.
     Establish character-offset semantics precisely: zero-based, half-open
     ranges into `extracted_text`, ordered and non-overlapping.
   - Extend the safe document response/status schema only with phase-owned
     metadata (`language`, `page_count`, `parsing_status`, safe error summary
     when failed). Assert the response excludes text, spans, storage data,
     checksums, task identifiers, and raw errors.
   - Decide the finite resource bounds before implementation: maximum parser
     input read from storage, extracted characters, location spans, task runtime,
     and retry attempts. These must be settings with tests, not scattered
     constants.

2. **Build isolated, deterministic parser components.**

   - Create a parser registry keyed exclusively by trusted persisted
     `Document.file_type`; do not rediscover types from user data or trust a
     content-type header at this stage.
   - Implement each required parser using format-appropriate local libraries
     and bounded reads. Normalize line endings/whitespace deterministically
     without losing page/section boundaries; reject empty/unreadable extraction
     with a stable parse error rather than treating it as a successful document.
   - Preserve pages for PDF and sections for structured/text formats as defined
     above. Ensure metadata contains only locator/span information necessary for
     Phase 12, not a second unbounded copy of the document text.
   - Parse EML strictly as stored message content: no network loads and no
     recursive attachment handling. Treat malformed mail or non-text-only mail
     without readable body as a safe parse failure.
   - Add a deterministic language detector wrapper with a minimum-text and
     confidence policy. It must return `unknown` rather than making a weak claim
     and must recognize synthetic Norwegian Bokmål and English fixtures.

3. **Extend private storage safely and verify raw integrity.**

   - Add a bounded `get_bytes`/read operation to `ObjectStorage` and
     `AzureBlobObjectStorage`, plus test fakes. Do not add download routes,
     signed URLs, public ACLs, or storage-key exposure.
   - In the worker-facing coordinator, compare the exact retrieved byte length
     and SHA-256 with the document metadata before selecting a parser. Convert
     absence, over-limit data, mismatch, or provider errors into neutral domain
     outcomes and structured safe logs.
   - Ensure storage clients are correctly closed in worker execution and that
     neither exception chains nor Azure responses flow to API/audit outputs.

4. **Make persistence transitions atomic and replacement-safe.**

   - Add repository methods that load by `organization_id`/document ID, claim
     only `pending` work atomically, and update parser metadata within an
     explicit transaction. A duplicate/late task must become a harmless no-op.
   - On success, atomically create or replace the unique `DocumentText` row and
     transition document metadata to `parsed`. Include parser/version,
     trustworthy text dimensions, language, and location spans in
     `extraction_metadata`.
   - On a permanent failure, write only the safe status/error on `Document`.
     Preserve any prior successful `DocumentText`, all raw upload metadata, and
     Case state. Never create partial text rows.
   - Reprocess must reset a non-processing document to `pending`, clear its
     prior failure summary, and preserve its last-good text until a successful
     replacement. Add no schema migration unless this contract cannot be
     represented by the existing fields.

5. **Introduce the broker/worker boundary.**

   - Add a single Celery application with Redis broker configuration from
     `AppSettings`, an explicitly named parser queue, JSON-safe identifier-only
     task serialization, acknowledgement/retry configuration, and no eager mode
     in production-like runtime.
   - Implement one task that creates its own settings/storage/database session,
     invokes the parse coordinator, and closes resources deterministically. It
     must not reuse an API request session or accept text/key/checksum values
     from the caller.
   - Distinguish transient infrastructure errors (bounded exponential retry) from
     permanent parser/integrity errors (terminal `failed`). Ensure a hard task
     timeout cannot leave a document indefinitely `processing`; reconciliation
     must safely requeue/mark stale claims according to a documented lease or
     timeout policy.
   - Add a durable pending/stale-job reconciliation path that periodically
     enqueues eligible rows. This is required because queue publish and database
     commit are not a single transaction in the current architecture. It must be
     idempotent and must not scan or expose raw content.

6. **Schedule uploads and implement controlled reprocessing.**

   - Extend the Phase 10 successful-upload path to request parse scheduling only
     after the document/audit transaction is committed. If immediate dispatch
     cannot occur, retain `pending`, log a safe operational event, and rely on
     reconciliation; never undo a successful upload or claim it has parsed.
   - Add a `DocumentAction.REPROCESS` policy for Admin, Case Worker, and Manager
     and `DocumentAction.READ` matching current Case-read eligibility. Test all
     five canonical roles explicitly.
   - Implement tenant-scoped status lookup and `POST /reprocess` with guarded
     transitions, `202`, and a dispatcher abstraction that API tests can fake.
     Reject archived, foreign, missing, and actively processing resources
     through established safe behavior; do not add download/list UI features.
   - Record the minimal reprocess-request and terminal parse audit events only
     after their respective state changes are durable.

7. **Run the real local worker without weakening operations.**

   - Update the Compose worker command/image/dependencies to run the actual
     parser consumer against the local Redis/Azurite/PostgreSQL services.
   - Preserve a verifiable worker health/readiness surface or equivalent
     service-level probe that checks only safe dependency/consumer state. Update
     `verify_local_stack.sh` and documentation in the same change so they no
     longer claim that the worker consumes no jobs.
   - Keep process ports loopback-only, keep normal API/worker startup free of
     automatic migrations and seeds, and avoid logging queue URLs, account keys,
     document content, or task arguments.

8. **Add focused tests and update documentation.**

   - Use small synthetic safe fixtures built in tests or stored under a clearly
     safe test-data location. Include at least one valid PDF, DOCX, TXT,
     Markdown, CSV, XLSX, EML, and pasted-email path; no real personal data.
   - Cover parser text/span/page/section outputs, language values, malformed or
     empty content, bounded-resource failures, unsupported trusted type,
     storage corruption, and safe error mapping.
   - Cover queue payload redaction, scheduling after durable upload,
     duplicate-task idempotency, retry classification, stale-pending recovery,
     successful parse, failed parse, reprocess from both `failed` and `parsed`,
     reprocess conflict during `processing`, and preservation of old text on a
     failed reparse.
   - Add API tests for session/RBAC/tenant behavior, response redaction, `202`,
     `409`, OpenAPI declarations, and absence of raw parser errors. Add
     Postgres-backed tests for one-text uniqueness, atomic state updates, audit
     event safety, and no Case/document/raw-object corruption after failures.
   - Update developer/README wording and manual commands only after the worker
     behavior is implemented and verified.

## Required tests

### Unit tests

- Every supported trusted file type produces expected normalized text and the
  appropriate page/section spans from small synthetic fixtures.
- PDF order/page count; DOCX heading association; Markdown heading segmentation;
  CSV headers/rows; XLSX worksheet association; EML plain-text preference and
  safe HTML fallback; TXT normalization; pasted-email handling.
- Malformed PDF/OOXML/EML, unreadable PDF, empty extraction, oversized extracted
  text/section count, unsupported persisted type, language confidence below the
  threshold, and language `unknown` all map to stable safe outcomes.
- Private-read length/checksum mismatch and storage failures never pass data to
  a parser or expose raw provider messages.
- Parsing state-machine transition rules, stale-claim recovery, retry
  classification, duplicate-task no-op, metadata offset validation, and old-text
  preservation are deterministic.
- All roles are tested for `DocumentAction.READ` and `REPROCESS`; no policy test
  uses a route handler as its authority source.
- Celery/dispatcher tests assert identifiers-only payloads, no eager background
  execution in production settings, and safe behavior when broker publishing
  fails.

### API tests

- `GET /api/documents/{id}` and `POST /api/documents/{id}/reprocess` require a
  valid opaque session, enforce canonical role rules and tenant isolation, and
  use the standard success/error envelope.
- Reprocess returns `202` for eligible `pending`/`failed`/`parsed` documents;
  `409` for `processing`; and safe not-found behavior for foreign, archived, or
  absent documents.
- Responses and OpenAPI never contain extracted text, spans, raw filenames in
  errors, checksum, object-storage key/URL, queue URL/task id, credentials, or
  raw parser/provider exception details.
- Existing multipart upload tests remain compatible: upload returns quickly with
  `pending` metadata and does not synchronously parse payloads.

### Integration tests

- PostgreSQL Testcontainers tests prove one `DocumentText` row per document,
  tenant-safe lookup/claim/update, correct success/failure audit metadata, and
  atomic document-text/status changes.
- A successful parse creates expected text/metadata and updates language/page
  count/status. A failed initial parse creates no text; a failed reparse retains
  the prior text; neither alters the related Case or raw object metadata.
- Worker coordinator tests use fake dispatcher/storage for deterministic
  behavior; an opt-in Azurite test reads a synthetic stored object through the
  same private adapter without outputting key/content/account credentials.
- A local Compose smoke check verifies a pending synthetic document is consumed
  by the real worker and reaches `parsed` or the expected safe `failed` result
  within a bounded polling window, then verifies worker health/readiness.

## Validation steps

Run all commands from the repository root after implementation. Do not mark the
phase complete if any required check fails.

1. Refresh the locked Python dependency state through the repository-managed
   workflow, then confirm the worker/image configuration is valid:

   ```bash
   uv lock --check
   docker compose --env-file .env.example config --quiet
   ```

2. Run targeted parser, worker, API, and persistence suites first, then the
   complete backend suite:

   ```bash
   uv run pytest apps/api/tests/unit apps/api/tests/integration apps/api/tests/api
   pnpm test:api
   ```

3. Run workspace, formatting, lint, and strict typing checks:

   ```bash
   pnpm check:workspace
   pnpm format:check
   pnpm lint
   pnpm typecheck
   ```

4. From a clean local Compose environment, prove the database state and worker
   runtime. Use only synthetic data and do not echo local passwords, cookies,
   connection strings, blob keys, or document bodies:

   ```bash
   pnpm dev:up
   docker compose --env-file .env.example exec -T api uv run alembic -c apps/api/alembic.ini current
   pnpm verify:local-stack
   ```

5. Follow the updated documented local workflow to create/use a synthetic Case,
   upload a safe file, poll the metadata-only document status until terminal,
   request reprocessing, and inspect only safe metadata/audit fields. Run the
   opt-in Azurite read test with a loopback endpoint if provided by the
   implementation. Finish by shutting down the stack:

   ```bash
   pnpm dev:down
   ```

6. Inspect the final worktree and OpenAPI schema before completion. Confirm that
   source changes are limited to Phase 11 scope and that neither generated
   parser outputs nor synthetic upload bodies, queue credentials, or storage
   secrets are tracked.

## Completion criteria

- A completed Phase 10 upload is parsed asynchronously by the real local worker
  without blocking its API response.
- All eight supported upload forms produce canonical parsed text from valid
  synthetic fixtures, preserve the required page/section context where
  available, and store a reliable language value or `unknown`.
- Raw storage remains private; reads are bounded and validated against stored
  size/checksum; no raw object/text/key/checksum/credential/task id leaks from
  API, logs, audit metadata, queue payloads, or documentation examples.
- `Document` progresses safely through `pending`, `processing`, `parsed`, and
  `failed`; terminal failures have neutral summaries; retries are finite;
  duplicate deliveries are idempotent; reconciliation handles unscheduled
  pending work.
- Failed parsing never corrupts the Case, raw-object metadata, audit history, or
  an earlier good `DocumentText`; the one-text-record invariant is proven by
  integration tests.
- Authorized reprocessing works from terminal states and is tenant-safe,
  conflict-safe, audited, documented in OpenAPI, and verified by API tests.
- The parser worker, worker health/readiness contract, Docker Compose setup, and
  local verifier work with PostgreSQL, Redis, and Azurite using synthetic data.
- All required unit, API, integration, full-suite, formatting, lint, type,
  workspace, migration-state, Compose, and local-stack checks pass.
- Only after all of the above pass may the implementation agent mark Phase 11
  `(DONE)` in `specs/roadmap.md` and update `specs/progress.md` consistently.

## Risks and dependencies

| Risk or dependency | Required mitigation |
| --- | --- |
| The current worker is health-only, while Phase 11 needs an actual consumer. | Introduce the Celery worker deliberately, preserve a safe service-health contract, and update Compose/verifier/docs together. Do not leave a fake worker process. |
| Database commit and broker publish are not atomic. | Persist `pending` first, dispatch only after durable commit, and reconcile pending/stale rows idempotently. A queue outage must not erase or falsely complete an upload. |
| PDFs may be image-only; OOXML, spreadsheet, and email inputs can be malformed or resource-heavy. | Use format-specific bounded parsers, explicit text/section limits, task timeouts, and neutral terminal errors. OCR/attachment parsing are not fallback behavior. |
| Reprocessing can destroy useful prior text or race with duplicate tasks. | Claim work conditionally/under lock, preserve last-good text until replacement succeeds, and reject active-processing reprocess requests. |
| Raw document data may be sensitive even when demo fixtures are synthetic. | Keep bytes in private storage, pass only UUIDs through the queue, redact all exceptions/logs/audit data, and avoid fixture content in operational output. |
| Parser packages and Celery introduce dependency, locking, and typing complexity. | Choose minimal maintained libraries, pin compatible constraints, add any required typing approach outside application namespaces, and validate with strict mypy/Ruff plus the full suite. |
| Phase 12 needs location context but not implementation now. | Store stable parser/version/span metadata in `DocumentText` only; add no chunk/token/vector/full-text logic. |

## Notes for the implementation agent

- Treat this file as the primary scope authority. Re-read the PRD/architecture
  only when resolving an ambiguity; do not pull Phase 12 indexing, Phase 14 UI,
  or Phase 29 hardening into this change.
- Preserve the existing uncommitted Phase 10 worktree changes. Do not reset,
  overwrite, or "clean up" unrelated files. Re-check `git status --short`
  before reporting which files changed.
- Keep route handlers thin. Parsing, integrity verification, queue dispatch,
  worker execution, and state transitions belong in typed services/adapters with
  injectable fakes; repositories own database predicates and persistence only.
- Do not make an API request wait for `DocumentText`, and do not use
  FastAPI in-process background tasks as a substitute for the required worker
  boundary.
- Keep successful upload compatibility intact: a parser outage leaves a truthful
  `pending` document that reconciliation/reprocessing can recover. Never turn a
  successful raw upload into a false HTTP failure just because immediate queue
  dispatch was unavailable.
- Use only synthetic/public/anonymized test material. Never add real documents,
  passwords, cookies, connection strings, account keys, or raw text fixtures to
  logs, audit data, docs command output, or committed sample data.
