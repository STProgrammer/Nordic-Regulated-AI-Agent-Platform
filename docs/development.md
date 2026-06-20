# Developer Guide

## Scope of the current workspace

This is the Phase 6 authentication, sessions, and RBAC implementation, built on the Phase 5 service
layer, Phase 4 database schema, Phase 3 API shell, and Phase 2 local runtime. Docker Compose starts
infrastructure and health/worker processes: a static web readiness page, the API process, the worker
readiness process, PostgreSQL, Redis, Azurite, and an Azurite container initializer.

The API process has typed configuration, structured logging, request correlation, a consistent JSON
error contract, local OpenAPI documentation, typed SQLAlchemy models, an Alembic database baseline,
and internal repository/service modules. It now provides local Argon2id authentication, opaque
server-side sessions, failed-login rate limiting, `me`/logout, and Admin-only user/role management.
It does not provide a Next.js frontend, cases, documents, approvals, audit reads, background jobs,
retrieval, or model-provider integration; those arrive in later phases.

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

The underlying command is:

```bash
docker compose --env-file .env.example up --build --wait --detach
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

The default published ports bind to `127.0.0.1`: web 3000, API 8000, worker 8001, PostgreSQL 5432,
Redis 6379, and Azurite blob 10000. Containers use Compose DNS names such as `postgres`, `redis`,
and `azurite`; they must never use host `localhost` to reach each other.

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
checks the web/API/worker/Azurite HTTP contracts through their loopback ports, verifies the API
OpenAPI schema and Swagger documentation respond, runs `pg_isready`, checks that pgvector is
available without enabling it, verifies Redis `PONG`, and confirms that the empty configured Azurite
blob container exists. It neither creates business data nor runs migrations, queue tasks, or
external calls.

The API exposes health endpoints plus local API documentation; the worker remains health-only:

| Process | Endpoints                                                                           |
| ------- | ----------------------------------------------------------------------------------- |
| API     | `GET /health/live`, `GET /health/ready`, `GET /openapi.json`, `GET /docs`, `/redoc` |
| Worker  | `GET /health/live`, `GET /health/ready`                                             |

Liveness is dependency-free. Readiness checks PostgreSQL, Redis, and Azurite and returns `503` with
only safe dependency identifiers when a local dependency is unavailable; it never returns passwords,
connection strings, exception details, or stack traces. The static web page explicitly says that the
actual frontend begins in Phase 7.

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
- **Route boundaries**: Phase 6 exposes only `POST /api/auth/login`, `POST /api/auth/logout`,
  `GET /api/auth/me`, `GET/POST /api/users`, `GET/PATCH /api/users/{user_id}`,
  `PUT /api/users/{user_id}/roles`, and `GET /api/roles`. The Users operations are Admin-only and
  derive organization solely from the authenticated principal. All remaining product groups stay
  operation-free until their own phases.

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
schema. Azurite still contains only its empty local blob container, and the worker consumes no jobs.

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

`audit_events` are append-only. `AuditService.record_event` is explicit: reads and generic
persistence operations do not manufacture audit rows. Event metadata must be JSON-safe and minimal;
never include credentials, authorization tokens, cookies, password data, raw request bodies, raw
exception text, or storage keys. Authentication dependencies now derive organization only from a
persisted principal. The tenant guard and repository predicates together hide cross-organization
resources; role checks are backend policy, not frontend or OpenAPI-only behavior. The high-risk
approval policy is a pure service rule for the future approval phase, but no approval route exists.

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
pnpm test:api
```

`pnpm test:api` runs the full backend test suite (`apps/api/tests`). `pnpm test:health` runs only
the Phase 2 health-compatibility tests. The aggregate commands run both language toolchains where
applicable. Equivalent direct Python checks are:

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

## Working agreements

- Keep application behavior within the roadmap phase that owns it. Phase 6 is limited to
  authentication/sessions/RBAC and Admin identity management. Cases, documents, approvals, audit
  reads, document processing, retrieval, and AI workflows belong to later phases.
- Use typed Python and strict TypeScript settings for new code.
- Never commit `.env` files, secrets, production connection values, or personal data.
- Keep public demo material synthetic, public, anonymized, or otherwise safe as described in
  [sample-data guidance](../sample-data/README.md).
- Record an architecture-impacting change in a new ADR or by updating the relevant ADR before
  implementation.
