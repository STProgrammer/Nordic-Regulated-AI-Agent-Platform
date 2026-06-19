# Phase 2 — Local Docker Development Environment

## Phase objective

Create a repeatable, safe local Docker Compose environment for the Nordic Regulated AI Agent Platform. A developer must be able to start the web entry point, API health service, worker readiness service, PostgreSQL with pgvector, Redis, and MinIO with one documented command, then verify that every required dependency is reachable and healthy.

This phase establishes the durable local-runtime contract that later API, frontend, database, document, workflow, and deployment phases will build upon. It does **not** implement product features, data models, authentication, a real frontend, background jobs, or cloud deployment.

## How this phase fits the product

The product must be a deployable, traceable enterprise AI workflow platform rather than a collection of disconnected services. The PRD requires local Docker Compose support, health checks for API and worker services, asynchronous/background processing, PostgreSQL, Redis, object storage, secure configuration, and no committed secrets. The architecture selects PostgreSQL 16 with pgvector, Redis, MinIO for local object storage, FastAPI, and Docker Compose as the local development baseline.

Phase 1 deliberately created only repository boundaries and static tooling. Phase 2 makes those boundaries runnable without prematurely implementing the Phase 3 API skeleton, Phase 4 database schema, Phase 7 Next.js UI, or later AI/document workflows. The health endpoints added here are a narrow infrastructure contract explicitly required by this phase; later phases extend those processes rather than replacing the local-service interface.

## Relevant specification context and constraints

- Local development uses Docker Compose and must include `frontend`, `api`, `worker`, `postgres`, `redis`, and `minio`. Qdrant, OpenSearch, and mock notification services are optional architecture components and are not needed in this phase.
- PostgreSQL is the system of record and pgvector is the default vector-search direction. Use a PostgreSQL 16 image with pgvector available, but defer extension creation, schema definition, migrations, seeds, and application data to Phase 4.
- Redis is the future queue, cache, lock, and worker-coordination dependency. Do not introduce Celery tasks, queues, retries, or application jobs yet.
- MinIO is the local S3-compatible object-storage implementation. It must be reachable and provisioned with a known local development bucket, but no upload endpoint, document persistence, or sample document ingestion belongs here.
- The API technology is FastAPI/Python 3.12. Public health endpoints are permitted by the PRD; all product routes, OpenAPI boundaries, structured configuration, logging, and error handling belong to Phase 3.
- The real frontend is a Next.js/TypeScript application in Phase 7. Until then, the `web` container may only serve a clearly labelled static local-readiness page. It must not claim that a user interface, login, or product workflow exists.
- Health output must not expose credentials, connection strings, stack traces, object-storage keys, or other sensitive implementation details. A failed readiness check may name an unavailable dependency but must return only a safe summary.
- Use only local, deliberately non-secret development defaults in `.env.example`. Values needed by local PostgreSQL or MinIO must be visibly non-production and documented as public local defaults, never as reusable credentials.
- Bind host ports to `127.0.0.1` by default so the local data services are not exposed on the developer's network. Containers communicate over the Compose network using service DNS names, never host `localhost`.

## In-scope deliverables

1. A root `docker-compose.yml` that defines the required local services, named persistent volumes, a private default network, dependency ordering, and Docker health checks.
2. Local-only development container definitions for the API and worker readiness processes, with reproducible, lockfile-backed Python dependencies and no production-image claim.
3. A static, explicitly temporary web readiness page served by the `web` Compose service until the Phase 7 Next.js application replaces it.
4. Minimal FastAPI health-only applications for the API and worker services, providing liveness and dependency-aware readiness endpoints.
5. PostgreSQL 16 with pgvector available, Redis, MinIO, and a one-shot MinIO bucket-provisioning helper using known local-only values.
6. An expanded `.env.example` containing documented local ports, service names, database/object-store defaults, and no real secrets.
7. Local-development documentation, lifecycle commands, endpoint table, cleanup guidance, and troubleshooting notes that accurately describe the current Phase 2 capabilities.
8. Automated health-contract tests plus a script that verifies a running Compose stack without creating business data or relying on external services.
9. Root convenience commands for bringing the local stack up/down, viewing logs, validating the Compose configuration, and verifying a running stack.

## Out of scope

- Product API route groups, OpenAPI documentation beyond FastAPI's unavoidable default metadata, application configuration framework, structured logging, dependency wiring, error model, authentication, RBAC, rate limiting, CORS policy, or database session management (Phase 3 onward).
- Database extensions enabled by migration, tables, Alembic, ORM models, data retention, seed records, tenant scoping, or database integration tests (Phase 4 onward).
- Celery/Dramatiq/Arq setup, task definitions, queue processing, workflow execution, document parsing, embedding, retrieval, evaluation, or model-provider integration (later phases).
- A Next.js application, user-facing localization, UI components, API client, browser tests, or authentication screens (Phase 7 onward).
- Object-storage upload/download APIs, document metadata, antivirus/file validation, or parsing pipelines (Phases 10–11).
- Qdrant, OpenSearch, Mailpit, or other optional local support services. Add them only in the phase that creates a concrete need and documents the operational cost.
- Production Dockerfiles, image publishing, image scanning, CI workflows, Azure resources, staging, production deployment, or real credentials (Phases 31–35).
- Sample cases, local seed data, evaluation datasets, customer data, personal data, or any real secrets.

## Local service contract

| Service | Local purpose in this phase | Host endpoint/default port | Health/readiness contract |
| --- | --- | --- | --- |
| `web` | Clearly labelled static readiness page; not the Phase 7 UI | `http://127.0.0.1:3000/` | Docker health check confirms HTTP 200 from the static server |
| `api` | Health-only FastAPI process; no product routes | `http://127.0.0.1:8000/health/live` and `/health/ready` | `live` confirms process health; `ready` verifies PostgreSQL, Redis, and MinIO are available |
| `worker` | Health-only worker-process contract; no jobs consumed | `http://127.0.0.1:8001/health/live` and `/health/ready` | `live` confirms process health; `ready` verifies its required coordination dependencies without revealing credentials |
| `postgres` | Future relational system of record; pgvector-capable | `127.0.0.1:5432` | Compose health check uses `pg_isready`; no schema or migration is applied |
| `redis` | Future queue/cache/lock broker | `127.0.0.1:6379` | Compose health check requires `redis-cli ping` to return `PONG` |
| `minio` | Local S3-compatible object storage | API: `http://127.0.0.1:9000`; console: `http://127.0.0.1:9001` | Compose health check calls MinIO's documented local health endpoint |
| `minio-init` | One-shot local bucket provisioning helper | No host port | Waits for MinIO health, idempotently creates the configured local bucket, then exits successfully |

All services use explicitly versioned image tags or digests; never use `latest`. Persistent state uses named Compose volumes, so it is not accidentally created inside the repository. The documented destructive reset command must be separate from the normal shutdown command and warn that it removes local database and object-storage data.

## Likely files, folders, modules, and services affected

### Compose and container infrastructure

- `docker-compose.yml`
- `.dockerignore`
- `infra/docker/api.dev.Dockerfile`
- `infra/docker/worker.dev.Dockerfile` (or one shared local-only Python development Dockerfile with distinct Compose commands)
- `infra/docker/web-readiness.html`
- Optional narrowly scoped entrypoint or healthcheck helper scripts under `infra/docker/` only when required by Compose; avoid shell scripts that duplicate application behavior.

### API and worker health-only bootstrap

- `apps/api/pyproject.toml`
- `apps/api/src/app/main.py`
- `apps/api/src/app/health.py` (shared safe health models and dependency probes)
- `apps/api/src/app/workers/readiness.py`
- `apps/api/tests/api/test_health.py`
- `apps/api/tests/api/test_worker_readiness.py` if the worker app has a distinct response contract
- Root `pyproject.toml` and `uv.lock` for only the runtime/test dependencies needed by these health contracts

### Developer commands, configuration, and documentation

- `.env.example`
- `.gitignore` if additional local Docker artifacts need exclusion
- `package.json`
- `scripts/verify_local_stack.sh`
- `README.md`
- `docs/development.md` (or a linked `docs/local-development.md` if the guide becomes clearer)
- `scripts/check_workspace_structure.sh` if the repository contract should also require the new Compose/doc files

## Implementation tasks

### 1. Review the existing foundation and preserve its conventions

1. Read `AGENTS.md`, this phase plan, the PRD, architecture, roadmap, Phase 1 documentation, and the current working-tree status before editing.
2. Preserve the selected toolchain: Python 3.12 with uv, Node 24 with pnpm, strict static checks, existing workspace paths, and Phase 1 safe-data guidance.
3. Keep the current dirty Phase 1 changes intact. Do not rename package workspaces, replace the lockfiles, or delete intentional empty-directory markers.
4. Update documentation truthfully from “no Docker environment” to “Phase 2 local runtime available”; do not claim an implemented API, frontend, authentication flow, database schema, or worker jobs.

### 2. Define the Compose topology and lifecycle

1. Add root `docker-compose.yml` using a stable project name and a single private default network. Define `web`, `api`, `worker`, `postgres`, `redis`, `minio`, and `minio-init` exactly once.
2. Use `postgres` based on a PostgreSQL 16 image with pgvector installed/available. Configure a named database volume, a non-production database/user/password supplied through local environment variables, and a `pg_isready` health check. Do **not** run `CREATE EXTENSION`, migrations, or seed SQL in this phase.
3. Configure Redis with a named volume where persistence is enabled and a `redis-cli ping` health check. Do not configure task queues or application cache behavior.
4. Configure MinIO with named storage, explicit API and console ports, known non-secret local-only root values, and an HTTP health check. Add `minio-init` using the official MinIO client to create the configured bucket idempotently after MinIO becomes healthy. Do not place object data or credentials in the repository.
5. Expose the documented ports only on `127.0.0.1`. Set `restart` behavior appropriate for developer services, keep images version-pinned, and use `depends_on` conditions so API/worker start only after the infrastructure services are healthy.
6. Add health checks for `web`, `api`, and `worker` with bounded start periods, retries, and timeouts. Health checks must not depend on a host-installed `curl`; use tooling available in each container image or a small, reviewed application-level probe.
7. Provide a single documented startup command that works from a clean checkout after tool installation:

   ```bash
   docker compose --env-file .env.example up --build --wait --detach
   ```

   Developers may copy `.env.example` to untracked `.env` to customize ports or local values, then use `docker compose up --build --wait --detach`. The normal shutdown command must preserve named volumes; document a separate, explicitly destructive reset command.

### 3. Add narrowly scoped health-only processes

1. Add a minimal FastAPI application factory/entry point for the `api` service. Its only HTTP behavior in this phase is:

   - `GET /health/live` returns HTTP 200 when the process is alive.
   - `GET /health/ready` returns HTTP 200 only when PostgreSQL, Redis, and MinIO can be safely contacted; otherwise return HTTP 503 with a stable, non-sensitive dependency-status summary.

2. Add a separate worker readiness entry point under `app.workers` and run it in the `worker` container. It exposes the same liveness/readiness shape on its own local port, but it must not define tasks, consume jobs, or present itself as a functional workflow worker.
3. Share health response schemas/probing code where it avoids duplicated behavior, while keeping the code intentionally small and typed. Dependency probes must use Compose DNS names inside containers, strict short timeouts, and no credentials in responses or logs.
4. Do not add the Phase 3 route modules, application settings architecture, database session layer, global middleware, auth, error-handling framework, or business-service layer. FastAPI and Uvicorn are permitted only because the phase explicitly needs API/worker health endpoints and they remain the selected final framework.
5. Make readiness dependency-aware rather than merely reporting a process as healthy. Keep liveness dependency-free so an unhealthy database does not make the process look crashed.

### 4. Build reproducible local images without claiming production readiness

1. Add a local API/worker development Dockerfile (or a shared one) under `infra/docker/`. Base it on Python 3.12, install dependencies from `pyproject.toml` and `uv.lock` using a locked uv command, and run the requested health-only entry point.
2. Configure Docker build context and `.dockerignore` so `.env` files, virtual environments, dependency directories, caches, Git metadata, local data, and editor files never enter images. Do not exclude source, lockfiles, or required workspace manifests.
3. Mount the relevant API source tree in Compose only when it supports local iteration without making the image non-reproducible. The health endpoint must work both from the image alone and with the documented development mount.
4. Serve `web` with a minimal pinned static-server image and a repository-owned readiness page. The page must state that the frontend begins in Phase 7; no branding, fake login, mock product data, or misleading functionality is allowed.
5. Keep these files unambiguously local/development oriented. Phase 32 owns production-hardening, release tagging, image scanning, and registry publishing.

### 5. Add safe local configuration and developer commands

1. Expand `.env.example` with comments and variables for the Compose project name, all bound ports, PostgreSQL database/user/local-only password, Redis host/port, MinIO endpoint/console port/local-only root values, and the bucket name. Use values that are obviously development-only and safe to disclose; include no token, cloud URL, production DSN, or real password.
2. Do not add future application configuration such as model-provider credentials, JWT secrets, Azure settings, production CORS origins, or real object-storage keys. Later phases must extend this file deliberately.
3. Add root pnpm scripts with stable names, for example:

   - `dev:up` — starts the stack from `.env.example` with `--build --wait --detach`;
   - `dev:down` — stops the stack without deleting named volumes;
   - `dev:logs` — follows Compose logs; and
   - `verify:local-stack` — runs the non-destructive local verification script against an already-running stack.

4. Add `scripts/verify_local_stack.sh` with `set -euo pipefail`, bounded retries/timeouts, clear failures, and no external network dependency. It must verify Compose reports the required long-running services healthy, confirm the web/API/worker endpoints, run `pg_isready`, run Redis `PING`, call MinIO health, and verify the configured bucket exists. It must not seed data, alter schemas, delete volumes, print secrets, or tear down the stack.
5. Add a focused `test:health` command (or equally clear direct uv command) for the health-contract test suite. Introduce only the test dependencies necessary for this scope, lock them with uv, and avoid adding frontend test tooling before Phase 7.

### 6. Document operation and troubleshooting honestly

1. Update the root README with the Phase 2 status, local-stack prerequisites (Docker Engine/Desktop with Compose v2), the one-command startup path, service URL table, verification command, normal shutdown, and explicit destructive reset warning.
2. Update developer guidance with:

   - required local tools and version expectations;
   - the choice between default `.env.example` values and an untracked customized `.env`;
   - port-collision troubleshooting;
   - how to inspect `docker compose ps` and service logs;
   - named-volume persistence behavior; and
   - the rule that local defaults are public convenience values, not deployable credentials.

3. State plainly that PostgreSQL is empty except for its system database, pgvector is not yet enabled by migration, MinIO contains only the empty local bucket, and the worker does not process jobs. This guards against Phase 2 being mistaken for a functional product demo.
4. Ensure the project ignores any new local data paths and continues to ignore `.env` while retaining `.env.example` in version control.

### 7. Test and review the infrastructure contract

1. Add API-level tests for liveness response shape and readiness success/failure behavior using controllable/fake probes rather than live Docker dependencies. Assert that failed responses use HTTP 503, name only safe dependency identifiers, and never include configured credentials or raw exception details.
2. Add equivalent coverage for the worker readiness process if it has a distinct app/port configuration. Reuse common assertions rather than copy-pasting tests.
3. Validate the Compose file with environment interpolation before startup:

   ```bash
   docker compose --env-file .env.example config --quiet
   ```

4. From a clean local Docker state, start the stack using the documented one-command path, wait for health checks, run `scripts/verify_local_stack.sh`, and inspect `docker compose ps` for the expected healthy services plus successful `minio-init` completion.
5. Run the existing workspace/static checks after all edits and review the final diff for accidental credentials, generated container data, and product claims ahead of their roadmap phase.

## Required tests and validation

Run from the repository root after installing the Phase 2 dependencies and Docker Compose v2.

1. **Static workspace checks**

   ```bash
   pnpm check:workspace
   pnpm format:check
   pnpm lint
   pnpm typecheck
   ```

2. **Health-contract tests**

   ```bash
   pnpm test:health
   ```

   The tests must cover API liveness, API readiness success, API readiness failure, and safe failure output. Cover the worker readiness contract separately if it differs from the API contract.

3. **Compose configuration validation**

   ```bash
   docker compose --env-file .env.example config --quiet
   ```

   This must succeed without unresolved variables or unsupported service references. During the same review, confirm every external image has an explicit versioned tag or digest and none uses `latest`.

4. **End-to-end local stack smoke validation**

   ```bash
   docker compose --env-file .env.example up --build --wait --detach
   pnpm verify:local-stack
   docker compose --env-file .env.example ps
   ```

   Verify all of the following:

   - `web`, `api`, `worker`, `postgres`, `redis`, and `minio` are running and healthy;
   - `minio-init` completed successfully and the configured bucket exists;
   - the web readiness page returns HTTP 200 and clearly identifies its temporary Phase 2 role;
   - API and worker liveness/readiness endpoints return HTTP 200 only after their dependencies are ready;
   - PostgreSQL accepts `pg_isready`, Redis answers `PONG`, and MinIO answers its health endpoint;
   - bound host ports are loopback-only; and
   - logs and endpoint bodies contain no local password, connection string, token, stack trace, or host-specific path.

5. **Lifecycle validation**

   ```bash
   docker compose --env-file .env.example down
   ```

   Confirm normal shutdown preserves named volumes. Run the documented destructive reset command only after explicitly accepting removal of local data, then confirm a fresh `dev:up` succeeds again.

## Completion criteria

Phase 2 is complete only when all of the following are true:

1. `docker compose --env-file .env.example up --build --wait --detach` starts the required local stack from a clean checkout without manual container setup.
2. The Compose file defines and health-checks web, API, worker, PostgreSQL 16 with pgvector available, Redis, and MinIO; MinIO bucket provisioning is idempotent and succeeds.
3. API and worker each expose safe, tested liveness and readiness endpoints; readiness accurately reports unavailable dependencies with HTTP 503 and no sensitive details.
4. The web endpoint is reachable but is explicitly a Phase 2 readiness page, not a substitute for the Phase 7 frontend.
5. PostgreSQL, Redis, and MinIO are reachable through their documented loopback ports; only named volumes retain local state.
6. `.env.example`, Docker build context, documentation, and logs contain no real secret, personal data, production connection value, or misleading product claim.
7. Health-contract tests, Compose configuration validation, local-stack smoke verification, and existing format/lint/type/workspace checks all pass.
8. The README and developer guide let a new developer start, verify, inspect, stop, and—when intentionally required—reset the environment without guessing.
9. No Phase 3+ functionality is implemented, and no Phase 2 work is marked `(DONE)` in `specs/roadmap.md` until every validation above passes.

## Risks and dependencies

| Risk or dependency | Why it matters | Required mitigation |
| --- | --- | --- |
| Docker Engine/Desktop and Compose v2 availability | The local stack cannot start without a compatible Docker runtime. | Document the prerequisite and provide `docker compose config --quiet` as the fastest setup diagnostic. |
| Host-port conflicts | PostgreSQL, Redis, MinIO, and common web ports may already be in use. | Keep ports configurable in `.env.example`, bind to loopback, and document how to override them in untracked `.env`. |
| Image-tag availability or platform compatibility | Pinned images must work on supported developer architectures. | Select maintained multi-architecture versioned images, avoid `latest`, and record the exact tags/digests in Compose. |
| Scope creep into Phase 3 or 7 | Health bootstraps can easily become an API framework or a fake product UI. | Limit code to health contracts and a static readiness page; defer all product routes, configuration architecture, UI, and business logic. |
| Readiness checks that leak configuration | Connection failures often include DSNs, usernames, or stack traces. | Catch and normalize probe failures; test explicitly for safe error bodies and logs. |
| Confusing local defaults with secrets | PostgreSQL and MinIO need development credentials to start. | Use conspicuously public local-only defaults, never reuse them outside local Compose, and document that `.env` remains untracked. |
| Data persistence surprises | Named volumes survive normal shutdown and can mask startup issues. | Document normal versus destructive lifecycle commands and verify both paths. |
| Later worker implementation changes | The eventual Celery/other worker should not be constrained by a temporary endpoint. | Treat the worker readiness app/contract as infrastructure that later worker processes retain or expose through an equivalent adapter; do not add task behavior now. |

## Notes for the implementation agent

- Treat this file as the scope authority. Consult the PRD and architecture only to resolve ambiguity; do not pull work forward from later phases.
- Keep the health contract intentional and typed. A tiny health-only FastAPI entry point is allowed because the roadmap explicitly asks for API and worker readiness, but it is not authorization to build the Phase 3 application skeleton.
- Prefer small, explicit Compose configuration over broad helper frameworks. A developer should be able to read the file and understand service names, ports, volumes, dependency checks, and local-only values in a few minutes.
- Do not run `docker compose down --volumes` in an automated verifier or normal shutdown command. It is destructive and requires a clearly documented, deliberate user action.
- Avoid real networking outside Docker image pulls. The verifier and tests must work against the local Compose network and must not require cloud accounts, model keys, email, or third-party APIs.
- Do not update `specs/roadmap.md` to mark Phase 2 `(DONE)` while generating this plan. The implementation agent may do so only after the completion criteria and validation commands pass.
