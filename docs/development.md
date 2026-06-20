# Developer Guide

## Scope of the current workspace

This is the Phase 17 Intake Graph slice, built on the Phase 16 typed LangGraph orchestration
foundation and the secure Phase 10–15 document, parsing, indexing, and governed retrieval
boundaries, plus the Case Management UI/backend, frontend shell, authentication/session/RBAC API,
service layer, database schema, API shell, and local runtime. Docker Compose starts the Next.js web
application, API process, Redis-backed Celery worker, PostgreSQL, Redis, Azurite, and an Azurite
container initializer.

The web application provides localized session UX, an accessible server-backed Case Inbox, Case
submission, and Case Detail. It proxies same-origin `/api/...` requests to the API service, while
the API remains the authorization authority for opaque server-side sessions, tenant isolation, RBAC,
and Case Management. The API accepts one safe, supported document attached to an active case and
stores raw bytes privately in Azurite. The worker validates the stored byte length and checksum,
then extracts canonical text and page/section context asynchronously. Case Detail now lists safe
metadata, displays lifecycle/governance state, and delegates source search to Phase 13; only a
user-requested, server-bounded source context can display text. The protected answer API is now
available, but there is still no browser upload, download, preview, raw-text browser, chat control,
or model-answer page. Intake is a closed background workflow: it dispatches only a workflow UUID,
reloads the case tenant-safely in the worker, persists default-deny state/node projections, and
returns only allowlisted preliminary classification/risk/routing signals. Prompt content, case text,
provider bodies, confidence numbers, trace data, and final approval decisions remain unavailable.

## Required tools

- Node.js 24.x
- pnpm 11.8.x (the root `package.json` pins the selected package-manager release)
- Python 3.12.x
- uv 0.11.x
- Docker Engine or Docker Desktop with Compose v2

Use one primary workflow per ecosystem. Do not add npm, Yarn, Poetry, pipenv, or a second lockfile
without an explicit architectural decision.

## Install

From the repository root:

```bash
pnpm install --frozen-lockfile
uv sync --all-packages --locked
```

`pnpm` installs JavaScript quality tooling. `uv` creates the local Python environment and installs
the locked API skeleton dependencies plus Python quality tools for the workspace.

## Local Docker lifecycle

Start the standard local stack from a clean checkout:

```bash
pnpm dev:up
```

The stack first waits for long-running services, then launches the one-shot private-container
initializer separately so Compose does not mistake its successful exit for a failed health check:

```bash
docker compose --env-file .env.example up --build --wait --detach web api worker postgres redis azurite
docker compose --env-file .env.example up --detach azurite-init
```

It creates named `postgres_data`, `redis_data`, and `azurite_data` volumes. Normal shutdown retains
those volumes:

```bash
pnpm dev:down
```

Only use this explicit reset command when removing all local database and object-storage data is
intended:

```bash
docker compose --env-file .env.example down --volumes --remove-orphans
```

The default published ports bind to `127.0.0.1`: web 3000, API 8000, PostgreSQL 5432, Redis 6379,
and Azurite blob 10000. The parser worker has no public port. Containers use Compose DNS names such
as `postgres`, `redis`, and `azurite`; they must never use host `localhost` to reach each other.

To customize a local port or default local value, copy the template and leave the copy untracked:

```bash
cp .env.example .env
docker compose up --build --wait --detach
```

`.env.example` contains intentionally public local defaults. They are not production credentials and
must not be reused outside this local stack. The verifier automatically prefers `.env` when it
exists; for another environment-file path, run
`COMPOSE_ENV_FILE=path/to/file pnpm verify:local-stack`.

## Verify and inspect the local stack

```bash
pnpm verify:local-stack
docker compose --env-file .env.example ps
pnpm dev:logs
```

`verify:local-stack` is non-destructive. It waits for all long-running services to become healthy,
checks the real Next.js web shell plus API/Azurite HTTP contracts through their loopback ports,
verifies the Celery worker broker/consumer ping, verifies the API OpenAPI schema and Swagger
documentation respond, runs `pg_isready`, checks that pgvector is available without enabling it,
verifies Redis `PONG`, and confirms that the private configured Azurite blob container exists. It
neither creates business data nor runs migrations, queue tasks, or external calls.

The API exposes health endpoints plus local API documentation. The worker is an internal Celery
consumer, and Compose marks it healthy only when `celery inspect ping` reaches its named worker:

| Process | Interface                                                                           |
| ------- | ----------------------------------------------------------------------------------- |
| API     | `GET /health/live`, `GET /health/ready`, `GET /openapi.json`, `GET /docs`, `/redoc` |
| Worker  | Internal Celery parser/index consumers and periodic reconciliation                  |

The web root redirects to `/nb` and includes a stable `nordic-app-shell` marker used only for local
stack verification. Its server-side `API_ORIGIN` is `http://api:8000` inside Compose, preserving
same-origin browser `/api/...` calls and the HTTP-only cookie. For host web development, set
`API_ORIGIN=http://127.0.0.1:8000` when starting the web package; never expose this as
`NEXT_PUBLIC_*`.

Liveness is dependency-free. Readiness checks PostgreSQL, Redis, and Azurite and returns `503` with
only safe dependency identifiers when a local dependency is unavailable; it never returns passwords,
connection strings, exception details, or stack traces.

### API and authentication behavior

- **Configuration**: typed `AppSettings` read from the environment with the `NORDIC_API_` prefix
  (see [.env.example](../.env.example)); database URLs are secret values and are never logged or
  exposed, while local Compose derives its connection from `POSTGRES_*` variables.
- **Logging**: `structlog`-based structured logs carrying only safe context (`service`,
  `environment`, request id, method, route template, status, duration). Request bodies, headers,
  query values, and raw exceptions are never logged.
- **Request correlation**: every response carries an `X-Request-ID` header. A client-supplied id is
  reused only when it passes a conservative character/length policy; otherwise a new id is
  generated.
- **Error contract**: all error paths return a single JSON envelope —
  `{"error": {"code", "message", "request_id", "details"}}` — with neutral English messages for this
  backend phase (Norwegian UI localization is Phase 7). Validation, unknown-route,
  method-not-allowed, explicit API errors, and unexpected errors all use this shape and never leak
  internals.
- **Sessions and passwords**: local passwords use Argon2id and are never logged, returned, or
  written to audit metadata. Login sets a finite HTTP-only, `SameSite=Lax` opaque cookie; its
  identity is resolved from Redis and revalidated against active PostgreSQL identity/roles on every
  protected request. Cookies are secure by default outside explicit local/test settings.
- **Rate limiting**: `POST /api/auth/login` limits normalized-email and client-origin counters
  through atomic Redis operations with HMAC-derived keys. It returns `429` and `Retry-After` when
  blocked; a Redis failure fails the login closed with a safe `503`.
- **Route boundaries**: Phase 12 exposes `POST /api/auth/login`, `POST /api/auth/logout`,
  `GET /api/auth/me`, `GET/POST /api/users`, `GET/PATCH /api/users/{user_id}`,
  `PUT /api/users/{user_id}/roles`, `GET /api/roles`, `POST/GET /api/cases`,
  `GET/PATCH /api/cases/{case_id}`, `POST /api/cases/{case_id}/archive`, and the minimal Case-read
  `GET /api/cases/assignees` option view. `POST /api/documents/upload` is an authenticated
  `multipart/form-data` operation that attaches one validated raw document or pasted email to an
  active current-organization case. `GET /api/documents/{document_id}` returns safe parser/indexing
  metadata, `GET /api/documents?case_id={uuid}` returns a bounded case-scoped metadata page, and
  `PATCH /api/documents/{document_id}/source-status` changes only the source-governance label for
  Admin/Compliance Reviewer roles. `GET /api/documents/{document_id}/context?chunk_id={uuid}` is a
  purpose-specific bounded source-context read with Phase 13 retrieval policy.
  `POST /api/documents/{document_id}/reprocess` requests another asynchronous parse, and
  `POST /api/documents/{document_id}/reindex` requests an authorized index replacement. User
  operations are Admin-only; Case and document operations derive organization solely from the
  authenticated principal and enforce backend RBAC. `POST /api/retrieval/search` is a protected,
  case-contextual hybrid source search that returns bounded governed excerpts only.
  `POST /api/retrieval/answer` is a protected direct RAG operation that uses approved sources only,
  emits validated inline citation labels, or returns a normal safe refusal. All other product groups
  remain operation-free until their own phases.

### Secure document upload and private storage

Use `POST /api/documents/upload` in local Swagger (`http://127.0.0.1:8000/docs`) only after the
normal migration and synthetic-password seed workflow. Admin, Case Worker, and Manager roles may
upload. Supply an active current-tenant `case_id` and exactly one of `file` or `email_text`, plus
optional `title`, `source_status`, and `confidentiality_level` form fields. The endpoint accepts
PDF, DOCX, TXT, Markdown, CSV, XLSX, EML, and pasted email text, with a configured 25 MiB hard cap.

The API validates extension, claimed type, content signature/UTF-8 structure, and OOXML package
structure before private storage. It calculates a SHA-256 checksum from the exact stored bytes,
persists only document metadata in PostgreSQL with parsing status `pending`, and appends one safe
`document.uploaded` audit event. Responses deliberately omit the checksum, blob key, blob URL,
credentials, and raw content. A rejected upload creates no successful document or audit record.

### Asynchronous parsing, chunking, and re-indexing

Every durable upload is dispatched after its database transaction commits. The Celery payload is the
document UUID only; the worker obtains tenant ownership, private storage key, checksum, and file
type from PostgreSQL. It reads raw bytes privately with a hard size cap, verifies size and SHA-256,
parses PDF, DOCX, TXT, Markdown, CSV, XLSX, EML, and pasted-email EML, and stores normalized
extracted text only in `document_texts`. On a successful parse commit, the document becomes pending
for a UUID-only indexing task. That task tokenizes only the canonical text inside trusted parser
spans, generates validated 1536-dimensional embeddings, and atomically replaces the document's chunk
rows. The public API never returns text, spans, chunks, vectors, blob keys, checksums, task ids,
broker URLs, or parser/provider exceptions.

Use `/docs` for a safe local verification after migration and synthetic login provisioning:

1. Create or select a synthetic active Case and upload a harmless supported file through
   `POST /api/documents/upload`.
2. Poll `GET /api/documents/{document_id}` until `parsing_status` becomes `parsed` or `failed`.
3. Poll the same safe metadata view until `indexing_status` becomes `indexed` or `failed`. Confirm
   it includes only lifecycle fields (`language`, optional `page_count`, timestamps, and neutral
   errors), never content, locations, chunks, vectors, storage keys, or provider information.
4. Request `POST /api/documents/{document_id}/reprocess`; it returns `202` unless a worker is
   actively processing the document, in which case it returns `409`.
5. Once parsing is `parsed` and indexing is terminal, request
   `POST /api/documents/{document_id}/reindex`. It returns `202`, retains the prior complete chunks
   until replacement succeeds, and returns `409` while an index job is pending or active.

The worker retries transient private-storage/database failures with bounded exponential delay. A
periodic reconciler resubmits pending parser/index work and releases expired leases. Failed parsing
never deletes the last-good `document_texts` record; failed indexing never deletes the last-good
chunk set. Configure OpenAI or Azure OpenAI credentials only through environment variables. For a
clearly labelled local/test plumbing check, `NORDIC_API_EMBEDDING_PROVIDER=deterministic` is allowed
and gives repeatable non-semantic vectors only. It is not an embedding-quality or retrieval test.
Case Detail now exposes safe document metadata and authorized source-governance/re-index
affordances. Once a synthetic document has `parsing_status=parsed` and `indexing_status=indexed`, an
authorized retrieval role can use the Evidence Panel or call `POST /api/retrieval/search` with a
readable case id and query. Omitted `source_statuses` searches approved sources only; explicit
draft/deprecated sources receive status warnings, while restricted/archived selection is
backend-authorized. The context route applies the same policy and returns one fixed server-bounded
window only after explicit user action. Physical archives and noncurrent index states are always
excluded. `POST /api/retrieval/answer` uses that same governed service with no caller-owned source,
provider, prompt, score, or context control. It selects bounded approved excerpts, records a
tenant-scoped `rag_answer` run and terminal content-free audit event, then returns a cited answer or
localized `needs_more_evidence` refusal. It is API-only and does not create a workflow-node record,
case-status transition, or frontend answer UI. No endpoint or UI returns a raw document, vector,
generic chunk list, download link, provider payload, or prompt.

With the Compose stack running, this opt-in host-side adapter test provides live Azurite
write/delete evidence without a cloud account (it creates and removes one synthetic object):

```bash
AZURITE_HOST=127.0.0.1 NORDIC_RUN_AZURITE_TEST=1 \
  uv run pytest apps/api/tests/integration/test_azurite_storage.py
```

### Database foundation workflow

The PostgreSQL schema is owned by Alembic and is never mutated by normal API or worker startup. The
`vector` extension and `pgcrypto` UUID generation are enabled by the baseline migration. Document
chunk embeddings use a fixed `vector(1536)` contract; a future embedding model must use that
dimension or introduce a reviewed dimensional migration.

Start the normal stack first, then run all database commands explicitly inside the API container:

```bash
docker compose --env-file .env.example exec api alembic -c apps/api/alembic.ini upgrade head
docker compose --env-file .env.example exec api python scripts/check_migrations.py
docker compose --env-file .env.example exec api python scripts/seed_local.py
```

`scripts/check_migrations.py` reports only current and expected revision identifiers. It
deliberately does not print a database URL or raw database errors. Settings prefer a secret
`NORDIC_API_DATABASE_URL` with the `postgresql+asyncpg://` scheme when supplied; otherwise local
Compose derives an internal URL from its `POSTGRES_*` variables. Alembic privately converts that URL
to psycopg for migrations. Neither setting is logged or exposed through OpenAPI.

`seed_local.py` creates a single fake Norwegian fixture organization, all five canonical role
records, and fake `demo.invalid` identities. The default invocation remains password-free and
creates no functional accounts. For a disposable local database, enter a synthetic password silently
and pass only its environment-variable name to the command; the script never prints the value or its
hash:

```bash
read -r -s NORDIC_LOCAL_SEED_PASSWORD
export NORDIC_LOCAL_SEED_PASSWORD
docker compose --env-file .env.example exec -e NORDIC_LOCAL_SEED_PASSWORD api \
  python scripts/seed_local.py --password-env NORDIC_LOCAL_SEED_PASSWORD
unset NORDIC_LOCAL_SEED_PASSWORD
```

The seed rejects this password-provisioning mode outside local/test environments. Never use a real
or production password.

On a disposable local database only, a current-baseline rollback and replay is:

```bash
docker compose --env-file .env.example exec api alembic -c apps/api/alembic.ini downgrade base
docker compose --env-file .env.example exec api alembic -c apps/api/alembic.ini upgrade head
```

This operation removes project tables and their data. It intentionally retains `pgcrypto` and
`vector`, since either extension may predate the project schema or be used by an operator-managed
schema. Azurite may contain synthetic raw uploads from local verification, and the worker consumes
only document UUID jobs from the internal Redis queue.

### Internal repository and service layer

The Phase 5 modules under `apps/api/src/app/db/repositories/` own SQLAlchemy statements and receive
an existing `AsyncSession`; they never create engines/sessions, commit, or roll back. The matching
modules under `apps/api/src/app/services/` compose repository calls, validate typed internal
commands, and use a narrow savepoint for safe persistence-conflict translation. Phase 6 route
handlers parse/format HTTP while authentication and administration services coordinate the trusted
identity, session, audit, and password operations.

Every tenant-scoped repository operation requires an explicit `organization_id` and includes it in
its SQL predicate. An id in another organization follows the same not-found path as an absent id.
Cases and documents exclude soft-archived records unless internal code explicitly asks for archived
rows. List operations use immutable bounded pagination, model-owned sort allowlists, and
deterministic UUID tie breakers. Never pass a user-supplied field name, direction, or SQL fragment
to a repository.

`audit_events` are append-only. The Case Management service writes exactly one minimal case audit
row for each successful submit, patch, or archive; the Document service writes exactly one
`document.uploaded` event only after an object, metadata row, and audit row can all succeed in the
caller-owned transaction. Reads and rejected commands write none. Event metadata contains only
operational facts—never case descriptions, filenames, titles, document content, checksums, storage
keys, credentials, authorization tokens, cookies, password data, raw request bodies, or raw
exception text. Authentication dependencies derive organization only from a persisted principal. The
tenant guard and repository predicates together hide cross-organization resources; role checks are
backend policy, not frontend or OpenAPI-only behavior. The high-risk approval policy is a pure
service rule for the future approval phase, but no approval route exists.

### Troubleshooting

- If startup fails before containers run, use
  `docker compose --env-file .env.example config --quiet` to find interpolation or Compose-version
  errors.
- If a host port is already in use, copy `.env.example` to `.env`, change the corresponding
  `*_HOST_PORT`, and start with `docker compose up --build --wait --detach`.
- Use `docker compose ps` and `docker compose logs <service>` to inspect a service. When using a
  custom `.env`, omit `--env-file .env.example` so Compose loads that file automatically.
- If a previous local volume is masking an initialization change, use the destructive reset command
  above only after accepting that it removes local data.

## Quality commands

```bash
pnpm check:workspace
pnpm format
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test:web
pnpm test:api
```

`pnpm test:web` runs the deterministic Vitest/Testing Library shell tests without Docker or a live
API. `pnpm test:api` runs the full backend test suite (`apps/api/tests`). `pnpm test:health` runs
only the Phase 2 health-compatibility tests. The aggregate commands run both language toolchains
where applicable. Equivalent direct Python checks are:

```bash
uv run ruff format --check apps services packages scripts
uv run ruff check apps services packages scripts
uv run mypy apps services packages scripts
uv run pytest apps/api/tests
```

The database contract tests use an isolated `pgvector/pgvector:0.8.0-pg16` Testcontainers instance;
Docker must be available for those PostgreSQL-specific assertions to execute. The focused suite also
covers Phase 5 repository/service behavior plus Phase 6 password, session, rate-limit,
authentication, RBAC, and OpenAPI contracts using synthetic `demo.invalid` data:

```bash
uv run pytest apps/api/tests/unit apps/api/tests/integration
```

Run `pnpm format` before committing formatting changes. All checks must pass before a phase is
marked complete.

### Browser smoke test

The independent `pnpm test:e2e` command covers login, Case submission, inbox search, and Case Detail
navigation against a running local Compose stack. Install its project-managed browser once:

```bash
pnpm --filter @nordic-regulated-ai-agent-platform/web exec playwright install --with-deps chromium
```

On Linux, this command may ask for `sudo` to install browser libraries. Start Compose with
`NORDIC_API_EMBEDDING_PROVIDER=deterministic` for this local-only plumbing test. After migrations
and password provisioning, export `NORDIC_E2E_CASE_WORKER_EMAIL` with a synthetic seeded Case Worker
address and retain `NORDIC_LOCAL_SEED_PASSWORD` in the shell. The spec rejects missing setup without
printing values, creates/indexes one synthetic document through the API setup boundary, and disables
traces, video, and screenshots. Run `unset NORDIC_E2E_CASE_WORKER_EMAIL NORDIC_LOCAL_SEED_PASSWORD`
after the test.

## Working agreements

- Keep application behavior within the roadmap phase that owns it. Phase 15 owns direct,
  approved-source-only RAG answering. Phase 16 owns the generic LangGraph runtime, provider/prompt
  ports, safe snapshots, and node persistence. Phase 17 owns only Intake's preliminary
  classification/routing and low-confidence correction; evidence, final risk, approval, traces, and
  evaluation remain later-phase work.
- Use typed Python and strict TypeScript settings for new code.
- Never commit `.env` files, secrets, production connection values, or personal data.
- Keep public demo material synthetic, public, anonymized, or otherwise safe as described in
  [sample-data guidance](../sample-data/README.md).
- Record an architecture-impacting change in a new ADR or by updating the relevant ADR before
  implementation.
