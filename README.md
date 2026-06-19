# Nordic Regulated AI Agent Platform

A planned, production-style AI workflow platform for Norwegian organizations with regulated,
document-heavy work. The finished platform will support source-grounded assistance, structured
workflows, human approval, auditability, privacy-aware handling, and Norwegian Bokmål as its default
interface language.

## Current status

This repository is at **Phase 3: Backend API Skeleton**. Building on the Phase 2 local runtime, the
API process is now a durable FastAPI application with typed configuration, structured logging,
request correlation, a consistent JSON success/error contract, local OpenAPI documentation, and
stable route boundaries for every future product domain (auth, users, cases, documents, workflows,
approvals, retrieval, evaluations, audit, admin).

Only the health endpoints are functional. The product route groups are code-ownership boundaries
whose operations are delivered by later phases. The repository does not yet contain a Next.js
application, a database schema or migrations, authentication or RBAC, jobs, retrieval, AI workflows,
or a deployment target.

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
| API        | http://127.0.0.1:8000/docs and `/health/live`         | FastAPI skeleton: health endpoints plus OpenAPI docs           |
| Worker     | http://127.0.0.1:8001/health/live and `/health/ready` | Health-only worker-process contract; no jobs run               |
| PostgreSQL | `127.0.0.1:5432`                                      | Empty PostgreSQL 16 instance with pgvector available           |
| Redis      | `127.0.0.1:6379`                                      | Future coordination dependency                                 |
| MinIO      | http://127.0.0.1:9000/                                | Local S3-compatible storage; console at http://127.0.0.1:9001/ |

The API serves `/health/live`, `/health/ready`, `/openapi.json`, `/docs`, and `/redoc`. Product
route groups are mounted under `/api` as stable boundaries but expose no operations yet.

`minio-init` is a one-shot helper, not a long-running service. It creates the configured empty local
bucket idempotently and then exits successfully.

Verify an already-running stack without adding business data:

```bash
pnpm verify:local-stack
```

Inspect or stop it normally:

```bash
docker compose --env-file .env.example ps
pnpm dev:logs
pnpm dev:down
```

Normal shutdown retains the named PostgreSQL, Redis, and MinIO volumes. The following is destructive
and removes all local database and object-storage data; run it only when that removal is intended:

```bash
docker compose --env-file .env.example down --volumes --remove-orphans
```

## Safe demo data and configuration

Only synthetic, public, anonymized, or otherwise demonstrably safe content may be added under
`sample-data/`. Never commit real personal data, customer documents, credentials, tokens, connection
strings, or production configuration. Use [.env.example](.env.example) only as a safe template.

The PostgreSQL and MinIO values in `.env.example` are intentionally public local-development
defaults, not deployable credentials. Copy that file to the ignored `.env` only when local port or
value changes are needed.

## Licence

No licence has been selected yet. A project owner must make that decision before any public release
or reuse terms are asserted.
