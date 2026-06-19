# Developer Guide

## Scope of the current workspace

This is the Phase 3 backend API skeleton, built on the Phase 2 local runtime. Docker Compose still
starts only infrastructure and health/worker processes: a static web readiness page, the API
process, the worker readiness process, PostgreSQL, Redis, MinIO, and a MinIO bucket initializer.

The API process is now a durable FastAPI application with typed configuration, structured logging,
request correlation, a consistent JSON error contract, local OpenAPI documentation, and stable route
boundaries for every future product domain. Only the health endpoints are functional. It does not
provide product operations, a Next.js frontend, database schema, migrations, authentication,
background jobs, document handling, or model-provider integration; those arrive in later phases.

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

It creates named `postgres_data`, `redis_data`, and `minio_data` volumes. Normal shutdown retains
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
Redis 6379, MinIO API 9000, and MinIO Console 9001. Containers use Compose DNS names such as
`postgres`, `redis`, and `minio`; they must never use host `localhost` to reach each other.

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
checks the web/API/worker/MinIO HTTP contracts through their loopback ports, verifies the API
OpenAPI schema and Swagger documentation respond, runs `pg_isready`, checks that pgvector is
available without enabling it, verifies Redis `PONG`, and confirms that the empty configured MinIO
bucket exists. It neither creates business data nor runs migrations, queue tasks, or external calls.

The API exposes health endpoints plus local API documentation; the worker remains health-only:

| Process | Endpoints                                                                           |
| ------- | ----------------------------------------------------------------------------------- |
| API     | `GET /health/live`, `GET /health/ready`, `GET /openapi.json`, `GET /docs`, `/redoc` |
| Worker  | `GET /health/live`, `GET /health/ready`                                             |

Liveness is dependency-free. Readiness checks PostgreSQL, Redis, and MinIO and returns `503` with
only safe dependency identifiers when a local dependency is unavailable; it never returns passwords,
connection strings, exception details, or stack traces. The static web page explicitly says that the
actual frontend begins in Phase 7.

### API skeleton behavior

- **Configuration**: typed `AppSettings` read from the environment with the `NORDIC_API_` prefix
  (see [.env.example](../.env.example)); no secrets and no database/Redis/MinIO values live in it.
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
- **Route boundaries**: product groups (`auth`, `users`, `cases`, `documents`, `workflows`,
  `approvals`, `retrieval`, `evaluations`, `audit`, `admin`) are mounted under `/api` but expose no
  operations yet. They are stable ownership boundaries; later phases add real endpoints to them.

At this phase PostgreSQL has no project schema or migration, pgvector is not enabled, MinIO contains
only its empty local bucket, and the worker consumes no jobs.

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

Run `pnpm format` before committing formatting changes. All checks must pass before a phase is
marked complete.

## Working agreements

- Keep application behavior within the roadmap phase that owns it. Phase 3 is limited to the API
  skeleton (configuration, logging, errors, docs, and route boundaries); product operations,
  persistence, authentication, and AI workflows belong to later phases.
- Use typed Python and strict TypeScript settings for new code.
- Never commit `.env` files, secrets, production connection values, or personal data.
- Keep public demo material synthetic, public, anonymized, or otherwise safe as described in
  [sample-data guidance](../sample-data/README.md).
- Record an architecture-impacting change in a new ADR or by updating the relevant ADR before
  implementation.
