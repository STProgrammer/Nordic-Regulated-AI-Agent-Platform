# Nordic Regulated AI Agent Platform

A planned, production-style AI workflow platform for Norwegian organizations with regulated,
document-heavy work. The finished platform will support source-grounded assistance, structured
workflows, human approval, auditability, privacy-aware handling, and Norwegian Bokmål as its default
interface language.

## Current status

Phases 1–33 are complete: the repository includes the authenticated Norwegian/English web
application, document ingestion and governed retrieval, RAG citations, LangGraph workflows, human
approval, trace/audit views, deterministic evaluation, observability, security hardening, CI, and
production-image validation. Phase 34 adds a polished local portfolio walkthrough using only safe
synthetic data. Follow the [Bokmål local demo and video guide](docs/local-demo-video-guide.md) to
prepare the repeatable case, cited RAG request, workflow trace, reviewer approval, audit, and
evaluation views. The local deterministic RAG mode demonstrates only grounding/citation plumbing; it
does not make an external model or quality claim.

## Repository map

```text
apps/          API and Next.js web applications
services/      Agent orchestration, retrieval, document, and evaluation services
packages/      Future shared schemas
docs/          Developer guidance and architecture decision records
infra/         Local Docker assets plus future Azure and CI/CD boundaries
sample-data/   Safe-data policy and future synthetic-data domain boundaries
scripts/       Dependency-free repository checks
specs/         Canonical product, architecture, and roadmap specifications
phases/        Phase implementation plans
```

## Toolchain

- JavaScript tooling: Node.js 24.x and pnpm 11.8.x.
- Python tooling: Python 3.12 and uv 0.11.x.

Install the development tools from a fresh checkout:

```bash
pnpm install --frozen-lockfile
uv sync --all-packages --locked
```

Run the workspace checks:

```bash
pnpm check:workspace
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test:web
pnpm test:api
```

See [developer guidance](docs/development.md) for the full workflow. The canonical
[specifications](specs/), [Phase 3 plan](phases/phase3.md), and
[architecture decisions](docs/adr/README.md) define the intended direction. See the
[security policy](SECURITY.md) and [security guide](docs/security.md) for the current application
boundary, repository scans, and public-demo restrictions.

## Local Docker stack

Docker Engine/Desktop with Compose v2 is required. From a clean checkout with the toolchain
installed, start the local runtime with:

```bash
pnpm dev:up
```

This is equivalent to the documented direct command:

```bash
docker compose --env-file .env.example up --build --wait --detach
```

The default services are deliberately local-only: all published ports bind to `127.0.0.1`.

| Service    | Local endpoint                                | Current role                                                           |
| ---------- | --------------------------------------------- | ---------------------------------------------------------------------- |
| Web        | http://127.0.0.1:3000/                        | Next.js application shell; `/` redirects to Norwegian Bokmål           |
| API        | http://127.0.0.1:8000/docs and `/health/live` | Health, local auth/session, user/role, and Case APIs; OpenAPI          |
| Worker     | Internal Compose service only                 | Celery consumer for private parser/index jobs; health uses broker ping |
| PostgreSQL | `127.0.0.1:5432`                              | PostgreSQL 16 with pgvector; schema changes are explicit               |
| Redis      | `127.0.0.1:6379`                              | Opaque session and failed-login rate-limit state                       |
| Azurite    | http://127.0.0.1:10000/                       | Local Azure Blob Storage emulator (account `devstoreaccount1`)         |

## Production image validation

Phase 32 adds portable, non-root production images for the web, API, and worker. They are validated
locally without Azure resources, registry access, real model credentials, or external model calls:

```bash
pnpm release:build
pnpm release:validate
```

The release Compose stack is separate from development (`docker-compose.production.yml`), uses
loopback ports 3100 and 8100 by default, and cleans up its isolated volumes after validation.
`infra/docker/production-local.env.example` is safe only for this local check.
`infra/docker/production.env.template` documents the later deployment configuration contract; it
contains placeholders only and must be copied outside source control. Azure provisioning, registry
pushes, and deployment remain intentionally deferred.

The API serves `/health/live`, `/health/ready`, `/openapi.json`, `/docs`, and `/redoc`. It exposes
`POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`, `GET/POST /api/users`,
`GET/PATCH /api/users/{user_id}`, `PUT /api/users/{user_id}/roles`, `GET /api/roles`, and the
protected `POST/GET /api/cases`, `GET/PATCH /api/cases/{case_id}`, and
`POST /api/cases/{case_id}/archive`, plus the Case-read-only `GET /api/cases/assignees`,
`POST /api/documents/upload`, case-scoped `GET /api/documents`, `GET /api/documents/{document_id}`,
`PATCH /api/documents/{document_id}/source-status`, bounded
`GET /api/documents/{document_id}/context`, `POST /api/documents/{document_id}/reprocess`,
`POST /api/documents/{document_id}/reindex`, `POST /api/retrieval/search`, and
`POST /api/retrieval/answer`, `POST /api/cases/{case_id}/workflows/run`,
`GET /api/workflows/{workflow_run_id}`, and
`POST /api/workflows/{workflow_run_id}/intake/correction`, and the protected read-only
`GET /api/cases/{case_id}/draft`. Case dates use ISO calendar dates (`YYYY-MM-DD`); the frontend
localizes them for display. User and role operations require the persisted **Admin** role in the
current organization; Case actions use their documented server-enforced RBAC policy. The closed
workflow selectors are closed and server-owned, including `{"workflow":"intake"}` and
`{"workflow":"evidence"}`; none accepts browser-owned model, prompt, state, tool, queue, retry,
query, or source controls. Evidence is a source-gathering workflow that persists a safe citation
package or `needs_more_evidence`; it does not answer, draft, approve, or expose a trace.

The closed `{"workflow":"extraction"}` operation uses only a completed eligible Evidence package for
that case. It produces bounded source-linked structured observations and permits typed edits to the
latest Extraction result; it never starts a new search, changes case risk/lifecycle, drafts text,
or approves an output.

The closed `{"workflow":"drafting"}` operation also requires that Evidence package and may accept
only `output_language` as `nb` or `en`. It produces a protected, immutable original AI draft only
when its `[S#]` citations validate against that run's approved sources; otherwise it returns a safe
`needs_more_evidence` state. Draft display is read-only and explicitly awaits later human review;
approval, final text, risk decisions, and edits remain out of scope.

The closed `{"workflow":"risk_compliance"}` operation accepts no risk score, source, policy,
provider, or override input. It revalidates the completed protected Draft, current approved Evidence
provenance, and Intake signals in the worker. Its fixed policy matrix routes missing or stale
prerequisites to `needs_more_evidence`; PII, sensitive-domain, high-impact, policy-conflict, and
prompt-injection signals produce high risk; low confidence produces a review-required medium result.
Every high-risk result requires later human approval, but this phase adds no approval, reviewer
queue, interrupt, or final text. The safe assessment read is
`GET /api/cases/{case_id}/risk-assessment`.

Document list/detail responses are always metadata-only. A source-status update accepts only the
closed source-governance label and is restricted to Admin and Compliance Reviewer roles; `archived`
does not physically archive or delete a document. The bounded context operation reuses retrieval
role, tenant, lifecycle, source-status, and restricted-confidentiality checks before returning one
server-limited window. `POST /api/retrieval/search` is case-contextual and returns only bounded,
tenant-governed source excerpts using deterministic hybrid rank fusion. Approved sources are the
default; non-approved selection is backend-authorized and may return a source warning.
`POST /api/retrieval/answer` accepts only `case_id`, `question`, and optional `answer_language`
(`nb` or `en`), and always retrieves approved evidence only. It returns either a cited answer with
run-local `[S#]` labels or a normal `needs_more_evidence` refusal; it never returns raw chunks,
provider configuration, prompt content, scores as confidence, or non-approved evidence. A completed
answer stores a tenant-scoped RAG run, selected excerpts, assistant output, and model accounting;
terminal audit data remains content-free. A real OpenAI/Azure OpenAI completion credential is needed
for manual answering. Deterministic embedding mode is plumbing only, not answer-quality validation.

For local plumbing verification only, explicitly set `NORDIC_API_EMBEDDING_PROVIDER=deterministic`
in an untracked local environment file. Those stable vectors are non-semantic and must not be used
as a claim of embedding or retrieval quality. Use an explicit OpenAI or Azure OpenAI configuration
for real embedding behavior; keys and endpoints stay out of tracked files.

`azurite-init` is a one-shot helper, not a long-running service. It provisions the configured empty
local blob container idempotently and then exits successfully.

Verify an already-running stack without adding business data:

```bash
pnpm verify:local-stack
```

The web container has a server-only `API_ORIGIN=http://api:8000` and proxies browser requests from
same-origin `/api/...`; no browser-visible environment variable, token, or cookie handling is added
by the frontend. For host-only web development with the API running on its loopback port, use:

```bash
API_ORIGIN=http://127.0.0.1:8000 pnpm --filter @nordic-regulated-ai-agent-platform/web dev
```

Open `http://127.0.0.1:3000/`. The application defaults to `/nb`; the language selector preserves
the current route when switching to `/en`. The Case Inbox is available at `/nb/cases`, with
submission at `/nb/cases/new`; other authenticated destinations remain placeholders. Use the
synthetic local-account workflow below before testing login; do not use a personal or production
password.

## Database migrations and synthetic local fixtures

Database setup is always explicit; normal API and worker startup never migrates or seeds data. With
the local stack running, execute the commands inside the API container so the Compose-only
PostgreSQL hostname is used without writing a connection string anywhere:

```bash
docker compose --env-file .env.example exec api alembic -c apps/api/alembic.ini upgrade head
docker compose --env-file .env.example exec api python scripts/check_migrations.py
docker compose --env-file .env.example exec api python scripts/seed_local.py
```

The default seed provisions one clearly synthetic Norwegian organization, the five canonical role
records, and fake `demo.invalid` identities without passwords. It is safe to run again because it
uses stable organization, role, and email keys.

For a disposable local database only, opt in to credentials without putting a password in source,
committed configuration, or command history. Read a synthetic password silently into the current
shell, then pass only its environment-variable name to the seed command:

```bash
read -r -s NORDIC_LOCAL_SEED_PASSWORD
export NORDIC_LOCAL_SEED_PASSWORD
docker compose --env-file .env.example exec -e NORDIC_LOCAL_SEED_PASSWORD api \
  python scripts/seed_local.py --password-env NORDIC_LOCAL_SEED_PASSWORD
unset NORDIC_LOCAL_SEED_PASSWORD
```

To run the optional browser smoke test after the stack has been migrated and seeded, start the local
stack with the deterministic local/test-only embedding provider, install the project-managed
Chromium binary once, then provide the synthetic case-worker email and the same local-only password
variable without printing the password:

```bash
pnpm --filter @nordic-regulated-ai-agent-platform/web exec playwright install --with-deps chromium
NORDIC_API_EMBEDDING_PROVIDER=deterministic pnpm dev:up
pnpm test:e2e
```

On Linux, the browser dependency installation may require an interactive `sudo` prompt.
`pnpm test:e2e` requires `NORDIC_LOCAL_SEED_PASSWORD`. It registers a unique synthetic case directly
in the completed-drafting, approval-required risk, and pending-human-review state, then verifies
only the reviewer approval and the case worker's terminal-state view. It establishes browser
sessions through the local API instead of exercising login UI, and disables browser screenshots,
video, and tracing.

This provisions local passwords for the synthetic `demo.invalid` fixtures only. Login sets an opaque
HTTP-only cookie; use the same client/cookie jar for `/api/auth/me` and `/api/auth/logout`. Wrong
credentials always receive the same generic `401`; repeated attempts eventually receive `429` with
`Retry-After`. Do not use a personal or production password.

For a disposable local database only, rollback and replay the current baseline with:

```bash
docker compose --env-file .env.example exec api alembic -c apps/api/alembic.ini downgrade base
docker compose --env-file .env.example exec api alembic -c apps/api/alembic.ini upgrade head
```

This removes project tables and data. PostgreSQL extensions are intentionally retained because they
may be shared with operator-managed schemas.

Inspect or stop it normally:

```bash
docker compose --env-file .env.example ps
pnpm dev:logs
pnpm dev:down
```

Normal shutdown retains the named PostgreSQL, Redis, and Azurite volumes. The following is
destructive and removes all local database and object-storage data; run it only when that removal is
intended:

```bash
docker compose --env-file .env.example down --volumes --remove-orphans
```

## Safe demo data and configuration

Only synthetic, public, anonymized, or otherwise demonstrably safe content may be added under
`sample-data/`. Never commit real personal data, customer documents, credentials, tokens, connection
strings, or production configuration. Use [.env.example](.env.example) only as a safe template.

The PostgreSQL and Azurite values in `.env.example` are intentionally public local-development
defaults, not deployable credentials. Copy that file to the ignored `.env` only when local port or
value changes are needed.

## Licence

No licence has been selected yet. A project owner must make that decision before any public release
or reuse terms are asserted.
