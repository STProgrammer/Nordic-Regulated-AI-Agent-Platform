# Phase 10 — Secure Document Upload and Storage

## Phase objective

Deliver the first secure document-ingestion boundary: an authorized user can
attach one supported, synthetic/safe document (or pasted email text) to an
existing case, have its raw bytes stored in the configured private object
store, and receive a typed metadata response. The API must validate the actual
content as well as the claimed file type, enforce a configured hard size cap,
derive a SHA-256 checksum while reading the payload, persist tenant-safe
metadata, and append an audit event only when the upload is fully successful.

This phase establishes **ingestion and raw storage only**. It must not parse,
extract, scan with an external malware service, chunk, embed, index, display,
download, or retrieve document content.

## How this phase fits the final product

Cases delivered in Phases 8–9 are the durable records to which uploaded source
material belongs. Phase 10 provides the durable, governed raw-file and metadata
boundary required by the later pipeline:

```text
Phase 10: validate → private object store → document metadata + audit event
Phase 11: parse raw file → document_texts + parsing status/error
Phase 12: chunk/index parsed text
Phase 13+: govern and retrieve sources
Phase 14: display documents and evidence in the UI
```

The API, not the browser, must decide whether an upload is permitted, determine
the authenticated organization/uploader, add the storage key, and persist
the result. Raw objects remain outside PostgreSQL; PostgreSQL remains the
system of record for the document metadata and relationship to the case.

## Relevant specification context and architecture constraints

- Roadmap Phase 10 requires secure upload for PDF, DOCX, TXT, Markdown, CSV,
  XLSX, EML, and pasted email text; local Azurite storage with a cloud-ready
  object-storage abstraction; type/size/checksum/metadata/source-status/
  confidentiality/audit handling; and API tests for accepted files, rejected
  files, size limits, metadata persistence, and audits.
- PRD `FR-DOC-001` requires type validation, size limits, safe storage,
  rejection of unsupported/unsafe inputs, and linkage to organization, user,
  and case. `FR-DOC-002` reserves text extraction, language/page metadata, and
  parsing errors for the parsing pipeline; it does not authorize parsing now.
- Architecture §§4.4–4.5, 6.2/6.5, 9.1, 10.2, 11.2, and 13.3 require Azure
  Blob-compatible object storage (Azurite locally), typed REST schemas, the
  existing tenant-safe `documents` table, no direct storage-key exposure,
  extension plus MIME/content validation, checksum support, and background
  parsing in a later phase.
- The pre-existing `Document` model already contains the needed Phase 10
  metadata: tenant/case/uploader IDs, title, original filename, file type,
  MIME type, byte size, SHA-256, private object key, source status,
  confidentiality level, and parsing status. Reuse it; do not duplicate
  metadata in a new table or write raw bytes to PostgreSQL.
- Phase 6 opaque sessions, RBAC, organization predicates, safe error envelope,
  request correlation, and append-only audit service remain mandatory. Tenant
  identity, actor ID, document ID, and storage key are never client-owned.
- All tests, fixtures, manual uploads, and documentation must use only
  synthetic, public, anonymized, or otherwise safe material. Do not log or
  commit uploaded content, filenames that contain personal data, storage
  credentials, connection strings, cookies, or raw storage keys.

## Existing baseline to extend

| Existing component | Phase 10 use |
| --- | --- |
| `apps/api/src/app/api/routes/documents.py` | Replace the operation-free Documents boundary with the one protected upload endpoint. Preserve its route group for later document operations. |
| `apps/api/src/app/db/models/document.py` | Reuse `Document` and leave `DocumentText`/`DocumentChunk` untouched; the latter two are owned by Phases 11–12. |
| `apps/api/src/app/db/repositories/document.py` | Keep all tenant predicates and metadata persistence here. Add only focused repository support actually needed for Phase 10. |
| `apps/api/src/app/services/documents/service.py` | Evolve the metadata-only service into the single upload coordinator; it must own case relation checks, storage compensation, metadata write, and audit write. |
| `apps/api/src/app/services/auth/policy.py` | Add a small document action vocabulary/policy rather than reusing an unrelated Case mutation policy. |
| `apps/api/src/app/api/dependencies.py` | Add request-scoped document-service/object-storage dependencies, keeping construction and secret handling out of routes. |
| `apps/api/src/app/core/config.py`, `.env.example`, `docker-compose.yml` | Add typed, secret-safe object-storage and upload-limit settings; reuse the existing Azurite service and initialized private local container. |
| `apps/api/src/app/services/audit/service.py` | Write one minimal `document.uploaded` audit event within the successful metadata transaction; never place a filename, payload, or object key in event data. |
| `apps/api/tests/` | Follow the existing API/unit/integration split and tenant fixtures. Add storage fakes through dependency injection; do not make ordinary unit/API tests require a live cloud account. |
| `docs/development.md` | Update the endpoint inventory and precise safe local verification instructions only after implementation. |

The document service and `DocumentRepository` currently provide only
metadata persistence. They must not remain a public bypass around validation or
object storage after this phase. All HTTP uploads need one validated service
path.

## In scope

- `POST /api/documents/upload` as an authenticated `multipart/form-data`
  endpoint, accurately described in OpenAPI. It accepts exactly one of:
  - a binary upload in `file`, or
  - pasted email content in `email_text`.
- Required case attachment through a current-organization, non-archived
  `case_id`; the route derives organization and uploader from the session
  principal. The nullable model relationship remains available for later
  non-case source-ingestion work, but this public Phase 10 endpoint must not
  add orphan documents.
- A closed allowlist for PDF, DOCX, TXT, Markdown, CSV, XLSX, EML, and pasted
  email text; safe filename normalization; content/extension/MIME consistency
  checks; and a hard configured byte limit enforced while reading, not merely
  from `Content-Length`.
- SHA-256 calculation from the exact accepted bytes; immutable raw-object
  storage in Azurite locally through an injected Azure-Blob-compatible adapter;
  a cloud configuration path using the same abstraction.
- Persisted document metadata and a safe typed added-document response that
  deliberately omits `object_storage_key`, storage URLs, credentials, and raw
  content. Set parsing status to `pending`; Phase 10 does not enqueue or run a
  parser.
- Validated closed metadata values: source status
  (`approved`, `draft`, `deprecated`, `restricted`, `archived`) and a documented
  confidentiality enum. Default source status to `draft` and confidentiality
  to `internal` when absent. They are persistence labels only in this phase;
  retrieval/governance behavior belongs to Phases 13–14.
- A documented, backend-enforced document upload policy and minimal
  `document.uploaded` audit write with no sensitive content/key/filename.
- Unit, API, and integration coverage; formatting, lint/type checks, OpenAPI,
  migration-state, and local-stack validation.

## Out of scope

- Document parsing, conversion, OCR, page/section extraction, language
  detection, page counts, parser failures, parser queue jobs, reprocessing, or
  updates to `document_texts` (Phase 11).
- Chunking, embeddings, vector/keyword indexing, re-indexing, retrieval,
  citations, source filtering, or source-status effects (Phases 12–15).
- Document list/detail UI, upload controls in the Case Detail screen, source
  governance controls, download/preview endpoints, direct/browser blob URLs,
  deletion/archival endpoints, or document UI tests (Phase 14 and later).
- External antivirus/malware scanning, quarantine workflow, upload/retrieval
  rate limiting, CORS/header hardening, CSRF expansion, or a general security
  program (Phase 29). The Phase 10 validation boundary must still reject
  unsupported or structurally unsafe inputs.
- Worker/Celery integration, Azure IaC, production Blob provisioning, S3
  provider implementation, cloud deployment, object-retention cleanup, or
  public container access.
- Any browser-side authorization, client-generated storage key/checksum,
  session-token handling, duplicate-content deduplication, or cross-case/team
  permissions model.
- Changes to `specs/roadmap.md` or `specs/progress.md` during planning. The
  implementation agent updates completion state only after every validation
  requirement passes.

## API and domain contract to implement

### Upload shape

Use `multipart/form-data`, not JSON/base64. Define a typed request boundary
with these fields:

| Field | Rules |
| --- | --- |
| `case_id` | Required UUID; resolve only through the tenant-scoped Case repository after document upload authorization. |
| `file` | Optional uploaded binary. It is mutually exclusive with `email_text`; the supplied filename has no authority beyond validation/display metadata. |
| `email_text` | Optional pasted email body, mutually exclusive with `file`; impose the same byte limit after UTF-8 encoding and synthesize a safe `.eml` filename/type for storage. |
| `title` | Optional, bounded, whitespace-normalized display title. Default to a safe filename-derived title; never treat it as a storage path. |
| `source_status` | Optional closed enum; defaults to `draft`. Persist only—do not add retrieval behavior. |
| `confidentiality_level` | Optional closed enum; defaults to `internal`. |

Reject requests with neither or both content fields, a missing/blank title when
supplied, malformed UUID/metadata, zero-byte input, declared oversized input,
or an invalid content payload through the existing safe error format. The route
must emit a `201` standard success envelope on success and only documented
safe `400/401/403/404/413/415/422/503` responses otherwise.

The response exposes an explicit `DocumentData` view: document ID, case ID,
uploader ID, safe metadata fields, source/confidentiality values, parsing status
`pending`, and timestamps. It must never serialize ORM models, raw bytes,
checksums unless a later requirement explicitly needs them, object keys, blob
URLs, or storage provider error text.

### File-validation rules

Build one reusable validator that receives a bounded, one-pass-safe payload and
returns a trusted `file_type`, canonical MIME type, sanitized display filename,
byte count, and SHA-256. The client `Content-Type` header is advisory only.

- Permit only the eight roadmap formats. Normalize extension case; strip path
  components/control characters from the display filename; generate a neutral
  filename for pasted email.
- Require an allowed extension and compatible detected media/signature. Verify
  PDF magic bytes; verify DOCX/XLSX as well-formed OOXML ZIP packages with the
  expected `word/` or `xl/` members; reject generic ZIPs and archive traversal
  names. Treat TXT/Markdown/CSV/EML as bounded text and require decodable,
  non-binary content with the expected extension/type rules.
- Do not infer a type solely from the extension, browser header, or filename.
  Reject a mismatch, executable-like/binary data passed as text, empty input,
  unsupported formats, and malformed ZIP containers with generic safe errors.
- Enforce the configured maximum during streaming/spooling even when the
  request has no or a forged `Content-Length`. Drain/close request resources
  correctly on failure; do not retain partial objects.
- Persist the SHA-256 of the exact stored bytes. It enables later duplicate
  detection but must not add a Phase 10 deduplication shortcut or disclose
  whether another case has matching content.

### Storage and persistence boundary

1. Introduce a small typed `ObjectStorage` protocol behind the document
   service (for example, write a private object with key, stream/bytes, and
   trusted content type; delete a just-written object for compensation). Keep
   Azure SDK calls and connection-string handling in an infrastructure adapter,
   not the route, schema, repository, or model.
2. Implement the Azure Blob adapter using the existing Azurite container for
   local development and the same Azure Blob contract for cloud configuration.
   Add only the Azure Blob SDK dependency needed by this adapter. Ensure its
   container is private and that it never produces a public/SAS URL in this
   phase.
3. Construct an opaque, server-owned key from stable IDs and a generated
   document UUID—not the original filename or caller input. The key must be
   recorded only in the database and never in audit events, API responses,
   request logs, exceptions, or documentation examples.
4. Validate and obtain the exact bounded bytes before durable storage. Write
   the object first, then add document metadata and its audit row together
   in the database transaction. If storage fails, write no metadata/audit row;
   if metadata/audit persistence fails after storage, make a best-effort,
   observable-but-safe deletion of the newly written object and return a safe
   failure. Do not report a successful upload unless all three artifacts
   (object, metadata, audit) are present.
5. Reuse the existing `Document` metadata fields and tenant/case/user foreign
   key checks. A migration is not expected if the baseline schema is sufficient;
   if an implementation need genuinely changes constraints/indexes, add a
   reviewed Alembic migration and prove upgrade/rollback rather than mutating
   the baseline migration.

### Authorization and audit rules

- Add `DocumentAction.UPLOAD` to the existing pure policy layer. Use the
  minimal least-privilege matrix matching case submission: Admin, Case Worker,
  and Manager may upload; Compliance Reviewer and Read-only Auditor cannot.
  Do not make the route Admin-only and do not add document-read policy/endpoints
  before their phase.
- Resolve `case_id` through the organization-scoped Case repository/service
  after authorization. Foreign, archived, and absent cases follow the existing
  safe not-found behavior; never leak tenancy through a distinct response.
- The document service, not the route, coordinates policy, Case validation,
  trusted storage operation, repository write, and `AuditService` call.
- Append exactly one `document.uploaded` event only after a successful upload.
  Record operational metadata such as trusted file type, byte size, selected
  source status, confidentiality level, and parsing status. Do **not** record
  title, filename, raw MIME header, checksum, object key, document text,
  request form, storage URL, credentials, cookies, or exception text. Failed
  validation, denied requests, missing cases, storage failure, and DB failure
  add no success audit event.

## Likely files, folders, modules, and services affected

| Area | Expected changes |
| --- | --- |
| `apps/api/src/app/api/routes/documents.py` | Add the single protected multipart upload operation, typed response declaration, and no service/storage logic. |
| `apps/api/src/app/api/schemas/documents.py` | Add strict request metadata enums and safe document response models. Do not reuse ORM models or accept client-owned tenant/uploader/key/checksum fields. |
| `apps/api/src/app/api/dependencies.py` | Provide a document service and storage adapter through injectable dependencies. |
| `apps/api/src/app/services/documents/` | Add validator, storage protocol/adapter wiring, upload command/result, orchestration, policy invocation, rollback/compensation, and audit coordination. |
| `apps/api/src/app/db/repositories/document.py` | Keep focused metadata persistence and current tenant/archive rules; add no raw storage behavior. |
| `apps/api/src/app/services/auth/policy.py` | Add the isolated Document action/role policy with unit tests. |
| `apps/api/src/app/core/config.py` | Add validated upload-size and private Azure Blob/Azurite configuration, keeping connection strings and account keys as `SecretStr` values. |
| `apps/api/pyproject.toml`, `uv.lock` | Add the minimal Azure Blob client library and regenerate the locked dependency state. |
| `.env.example`, `docker-compose.yml` | Document/wire local-only Azurite adapter settings and existing initialized container without changing its public-development credential warning. |
| `apps/api/tests/unit/` | Add validator, policy, key-generation, safe-error, and storage-compensation tests using fakes. |
| `apps/api/tests/api/` | Add authenticated multipart route/OpenAPI tests through dependency-overridden fake storage. |
| `apps/api/tests/integration/` | Add database-backed metadata/tenant/audit assertions and an Azurite adapter integration test when the local emulator is available. |
| `docs/development.md` | Accurately document the Phase 10 endpoint, safe test file workflow, and no-download/no-parsing limitation after implementation. |

Do not modify the web app for this backend/storage phase. A browser upload form
and document display belong to Phase 14.

## Implementation tasks

1. **Freeze the document upload contract before wiring storage.**

   - Add the documents API schemas/enums and an explicit safe metadata response.
     Keep request fields limited to case attachment and user-editable metadata.
   - Register the `POST /api/documents/upload` operation with
     `multipart/form-data`, auth/error responses, `201`, and accurate OpenAPI
     description. Verify the router is still mounted under `/api/documents`.
   - Decide and document one configured maximum payload value. Use a
     conservative local default of **25 MiB** unless existing configuration
     establishes a different product limit; validate it at settings load and
     make tests override it rather than hard-code a second limit.

2. **Implement policy and trusted input validation.**

   - Add the document upload action to the pure authorization policy and test
     every canonical role.
   - Implement one validator with streaming/bounded-spool semantics, SHA-256
     calculation, filename handling, MIME/signature checks, OOXML package
     checks, text validation, and stable safe domain errors.
   - Ensure the validator returns only trusted metadata. It must not log,
     retain, or publish content after failure.

3. **Add cloud-compatible private object storage.**

   - Introduce the minimal storage protocol and a test fake. Implement its
     Azure Blob adapter so local configuration targets the existing Azurite
     endpoint/container while deployed configuration can use Azure Blob.
   - Add settings validation for mutually coherent local/cloud storage inputs;
     keep all sensitive values secret-redacted and out of model representations.
   - Generate opaque keys from server-owned IDs, make container access private,
     and use trusted canonical MIME values for Blob metadata. Do not add a
     download adapter or public URL generator.

4. **Make `DocumentService` the transaction coordinator.**

   - Replace HTTP-callable metadata-only addition with an upload command that
     authorizes, confirms the active current-tenant case, allocates the
     document/key identity, invokes the validator/storage adapter, persists
     metadata, and writes the audit event.
   - Use the established `stage_write`/audit transaction conventions. On each
     failure path prove no partial document/audit row survives, and compensate a
     just-added blob if database persistence cannot succeed.
   - Persist `parsing_status="pending"`; do not enqueue a worker or populate
     text/page/language fields. Keep model/repository operations typed and keep
     routes thin.

5. **Wire local configuration and documentation.**

   - Add Azure SDK dependency plus typed `AppSettings` and local `.env.example`
     values. Reuse `azurite-init` and its empty named container; do not add a
     second storage emulator or expose host credentials in an API response.
   - Update `docs/development.md` only with verified commands, endpoint
     behavior, container assumptions, and the Phase 10 boundary. Do not claim
     parsing, download, a document UI, malware scanning, or source retrieval.

6. **Run the full quality and manual verification loop.**

   - Apply a migration only if schema inspection proves it is necessary; run
     upgrade, migration check, and rollback/replay proof if one is added.
   - Run the automated suites below, inspect generated OpenAPI, then perform a
     local synthetic upload to a seeded case and verify metadata/audit/blob
     presence without printing secrets, cookies, key values, or file contents.

## Required tests

### Unit tests

- File validation accepts safe representative PDF, DOCX, TXT, Markdown, CSV,
  XLSX, EML, and pasted email payloads, assigning canonical type/MIME values
  and exact size/SHA-256.
- It rejects unsupported extensions, mismatched declared type/signature,
  generic/malformed/traversal ZIPs, binary masquerading as text, empty data,
  invalid/ambiguous field combinations, and streaming payloads beyond the
  configured cap. Verify no storage call happens for these cases.
- Boundary tests exercise `Content-Length` absence/forgery, the exact size
  limit, one byte over the limit, filename path/control-character handling,
  whitespace metadata, defaults, and every closed enum value.
- Document authorization proves Admin/Case Worker/Manager are allowed and
  Compliance Reviewer/Read-only Auditor are denied. No browser-only role check
  is accepted as proof.
- Storage-key tests prove keys are deterministic only from server-owned inputs,
  unique per document, do not include the original filename, and never surface
  in safe result/error/audit serializers.
- Service tests cover object-store failure, metadata/audit write failure with
  best-effort deletion, and successful `pending` persistence. Failed paths
  produce no success audit event and no committed metadata.

### API tests

- Authenticated multipart requests return `201` with the standard envelope and
  metadata-only response for each accepted format and pasted email; request
  body/response never expose storage values or content.
- Anonymous requests receive `401`; denied roles receive `403`; invalid,
  unsupported, missing/foreign/archived-case, oversized, and malformed upload
  paths use documented safe responses without details from a storage SDK.
- The handler derives tenant/uploader/key/checksum/status from trusted service
  data and rejects attempts to supply system-owned JSON/form fields.
- OpenAPI includes the protected multipart operation, file/text exclusivity
  description, `201`, and safe error response models with no accidental
  operation-free Documents description left behind.

### Integration tests

- A real test database persists all required metadata against the correct
  organization/user/case, defaults source/confidentiality values, saves the
  exact trusted checksum and byte count, and starts at `pending` with no
  `DocumentText`/`DocumentChunk` row.
- Cross-organization and archived cases remain indistinguishable from missing
  ones; no document or audit record is written in either tenant.
- A successful upload adds exactly one `document.uploaded` audit event with
  actor, organization, case, and document resource references, and its event
  data contains no content, filename/title, checksum, key, or secret.
- The Azurite adapter test writes and deletes a synthetic object against the
  configured local emulator/private container. Keep this isolated from unit
  tests and skip only under a clearly documented unavailable-emulator condition;
  it is mandatory in the local Compose verification path.
- Existing Phase 4–9 repository, audit, auth/session/RBAC, Case API, and web
  regression tests remain green.

## Validation steps

Run these from the repository root after implementation and before declaring
the phase complete:

```bash
pnpm install --frozen-lockfile
uv sync --all-packages --locked
pnpm format:check
pnpm lint
pnpm typecheck
pnpm check:workspace
pnpm test:web
pnpm test:api
```

If a migration is added, validate it from a fresh local database according to
the existing guide:

```bash
pnpm dev:up
docker compose --env-file .env.example exec api alembic -c apps/api/alembic.ini upgrade head
docker compose --env-file .env.example exec api python scripts/check_migrations.py
docker compose --env-file .env.example exec api alembic -c apps/api/alembic.ini downgrade -1
docker compose --env-file .env.example exec api alembic -c apps/api/alembic.ini upgrade head
```

For manual local validation, start the standard stack, run the normal
migration/seed workflow with an ephemeral synthetic password, authenticate via
`http://127.0.0.1:8000/docs`, add or select a synthetic current-tenant case,
and upload one harmless supported sample. Confirm only the safe response,
metadata row, audit event, and private-container object existence; do not print
the cookie, password, object key, account key, storage connection string, or
document body. Also confirm a rejected unsupported/oversize upload leaves no
new metadata/audit/object. Finish with:

```bash
pnpm verify:local-stack
pnpm dev:down
```

## Completion criteria

Phase 10 is complete only when all of the following are true:

- The authenticated upload endpoint accepts each roadmap format and pasted
  email text, requires an active case in the caller's organization, and returns
  a typed safe metadata envelope with no storage implementation details.
- Extension, MIME/content signature, ZIP structure, text validity, mutual
  exclusivity, zero-byte, and configured size-limit checks reject unsafe or
  unsupported input before durable storage.
- Exact raw bytes are stored in the private configured object store, metadata
  contains a correct SHA-256/size/type and server-generated opaque key, and
  no raw object is stored in PostgreSQL or publicly accessible.
- Metadata defaults/closed values, tenant and actor relations, parsing status
  `pending`, source status, and confidentiality level are correctly persisted;
  no parsing/text/chunk/indexing work occurs.
- The document upload role policy, tenant case check, compensation behavior,
  safe error handling, and one-success-only audit event are fully covered.
- Unit, API, integration, existing regression, formatting, lint, strict type,
  workspace, migration (if applicable), OpenAPI, and local-stack checks pass.
- Documentation states the implemented upload/storage capability accurately;
  it makes no claim that later parsing, document UI, retrieval, or security
  hardening work is finished.
- Only after those checks pass may the implementation agent mark Phase 10
  `(DONE)` in `specs/roadmap.md` and update `specs/progress.md` consistently.

## Risks, dependencies, and explicit assumptions

- **Phase 4/5/6/8 are hard dependencies.** The database model, scoped
  repository/service conventions, session principal, audit service, and Case
  records already exist. Do not replace their patterns with direct SQL,
  bearer-token auth, client tenant IDs, or a second audit table.
- **Azurite is already provided by the local stack.** Phase 10 must reuse it
  and its initialized container. The cloud adapter is Azure Blob compatible;
  adding an S3 implementation now is scope expansion.
- **25 MiB is an explicit planning default, not an immutable product law.**
  The limit must be a typed configuration value and be adjusted only through a
  documented product/security decision, with tests bound to that single value.
- **Structural validation is not malware scanning.** Magic-byte/package/text
  checks are necessary now to meet the secure upload boundary; an external
  scanning/quarantine integration needs a separate approved phase/design.
- **Checksum is identity metadata, not an authorization mechanism.** Do not
  use it to reveal duplicates across cases or organizations, and do not turn it
  into global content deduplication.
- **No document-specific RBAC matrix exists yet.** The least-privilege upload
  matrix above is the smallest consistent extension of the Case submit roles.
  Revisit document read/edit/download permissions when their endpoints exist.
- **The worktree is already dirty from earlier phases.** Preserve all existing
  user changes. This planning task changes only `phases/phase10.md`; do not
  alter source, implementation status, or unrelated documentation.

## Notes for the implementation agent

- Read this plan first, then inspect the current document model/repository,
  Case service, audit transaction pattern, auth policy, API error handlers, and
  Compose/Azurite wiring before editing.
- Keep FastAPI routes as transport adapters. Validation/staging, storage,
  authorization, metadata persistence, and audit coordination belong in typed
  document-domain/infrastructure components with injected dependencies.
- Prefer small, testable interfaces and fake storage in unit/API tests; use the
  real Azurite adapter only where it provides integration evidence. Never
  require Azure credentials or network access for the ordinary suite.
- Preserve byte-for-byte integrity. Compute checksum, size, validation result,
  and stored object from the same accepted payload; do not read an
  `UploadFile` twice assuming its position is unchanged.
- Treat all storage SDK exceptions as internal operational failures: log only
  safe classification/correlation data, compensate safely, and return the
  established error envelope. Do not surface provider response text.
- Do not mark this phase done until the required tests and validation pass.
