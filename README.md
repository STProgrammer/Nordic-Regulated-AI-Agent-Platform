# Nordic Regulated AI Agent Platform

A planned, production-style AI workflow platform for Norwegian organizations with regulated,
document-heavy work. The finished platform will support source-grounded assistance, structured
workflows, human approval, auditability, privacy-aware handling, and Norwegian Bokmål as its default
interface language.

## Current status

This repository is at **Phase 6: Authentication, Sessions, and RBAC**. The API now supports local
email/password login with Argon2id, opaque HTTP-only Redis-backed sessions, failed-login rate
limiting, current-user lookup, logout, and backend-enforced organization-scoped Admin user/role
management. PostgreSQL remains the source of truth for identities, roles, and append-only audit
events; each protected request reloads the active user and current roles.

Only authentication and user/role APIs are product operations at this stage. Cases, documents,
workflows, approvals, audit reads, retrieval, AI workflows, and frontend session UX remain owned by
later phases.

## Repository map

```text
apps/          Future API and web application boundaries
services/      Future agent orchestration, retrieval, document, and evaluation services
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
pnpm test:api
```

See [developer guidance](docs/development.md) for the full workflow. The canonical
[specifications](specs/), [Phase 3 plan](phases/phase3.md), and
[architecture decisions](docs/adr/README.md) define the intended direction.

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

| Service    | Local endpoint                                        | Current role                                                   |
| ---------- | ----------------------------------------------------- | -------------------------------------------------------------- |
| Web        | http://127.0.0.1:3000/                                | Static readiness page, not the Phase 7 UI                      |
| API        | http://127.0.0.1:8000/docs and `/health/live`         | Health, local auth/session APIs, Admin user/role APIs, OpenAPI |
| Worker     | http://127.0.0.1:8001/health/live and `/health/ready` | Health-only worker-process contract; no jobs run               |
| PostgreSQL | `127.0.0.1:5432`                                      | PostgreSQL 16 with pgvector; schema changes are explicit       |
| Redis      | `127.0.0.1:6379`                                      | Opaque session and failed-login rate-limit state               |
| Azurite    | http://127.0.0.1:10000/                               | Local Azure Blob Storage emulator (account `devstoreaccount1`) |

The API serves `/health/live`, `/health/ready`, `/openapi.json`, `/docs`, and `/redoc`. Phase 6 adds
`POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`, `GET/POST /api/users`,
`GET/PATCH /api/users/{user_id}`, `PUT /api/users/{user_id}/roles`, and `GET /api/roles`. All user
and role operations require the persisted **Admin** role in the current organization. The remaining
`/api` route groups are still operation-free.

`azurite-init` is a one-shot helper, not a long-running service. It creates the configured empty
local blob container idempotently and then exits successfully.

Verify an already-running stack without adding business data:

```bash
pnpm verify:local-stack
```

## Database migrations and synthetic local fixtures

Database setup is always explicit; normal API and worker startup never migrates or seeds data. With
the local stack running, execute the commands inside the API container so the Compose-only
PostgreSQL hostname is used without writing a connection string anywhere:

```bash
docker compose --env-file .env.example exec api alembic -c apps/api/alembic.ini upgrade head
docker compose --env-file .env.example exec api python scripts/check_migrations.py
docker compose --env-file .env.example exec api python scripts/seed_local.py
```

The default seed creates one clearly synthetic Norwegian organization, the five canonical role
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
