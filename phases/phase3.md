# Phase 3 — Backend API Skeleton

## Phase objective

Turn the Phase 2 health-only FastAPI process into the durable backend API foundation for the Nordic Regulated AI Agent Platform. Establish structured application configuration, JSON-safe structured logging, centralized dependency wiring, a consistent API success/error contract, local OpenAPI documentation, and explicit route-module boundaries for every future API domain.

The result must be a professional, testable API shell that later phases can extend without changing public infrastructure behavior or inventing temporary patterns. It is intentionally **not** a product API implementation: persistence, authentication, authorization, business operations, and AI workflows remain in their roadmap phases.

## How this phase fits the final product

The PRD requires typed APIs with OpenAPI documentation, safe error handling, structured logs, authenticated and organization-scoped product routes, and health checks. The architecture assigns the API service responsibility for authentication, RBAC, case, document, workflow, approval, retrieval, evaluation, audit, and administrative endpoints, while also requiring clear frontend/backend/service boundaries.

Phase 2 created the local Compose runtime and a narrow FastAPI health contract. Phase 3 makes the API application itself production-shaped: configuration is centralized and injectable, startup behavior is explicit, errors are safe and predictable, and stable route ownership is visible in the repository. Phase 4 then adds database models and migrations; Phases 5–6 add repositories, services, authentication, and authorization; the feature phases add real operations to the route modules created here.

## Relevant specification context and constraints

- Use Python 3.12, FastAPI, Pydantic v2, and the existing `uv` workspace. Continue to meet the root Ruff and strict mypy configuration.
- Keep the existing factory/import contract (`app.main:create_api_app` and module-level `app`) so the Phase 2 Docker API service continues to start. Preserve `GET /health/live` and `GET /health/ready` response bodies and safe failure behavior exactly unless a backward-compatible improvement is both necessary and tested.
- FastAPI must expose accurate local OpenAPI/Swagger documentation. The API metadata must describe the current Phase 3 skeleton honestly; do not claim authentication, CRUD, workflow execution, or AI capability is implemented.
- The future route groups are: auth, users, cases, documents, workflows, approvals, retrieval, evaluations, audit, and admin. Their prefixes/tags/modules must be established now as stable ownership boundaries.
- API configuration, logging, errors, and dependency construction belong in reusable `app.core` / `app.api` modules, not inside route handlers. Routes must stay thin.
- Logs and error payloads must never expose passwords, connection strings, authorization values, raw request bodies, stack traces, or unexpected exception text. Structured log records must carry enough safe context for later observability work.
- All current product routes are still unauthenticated only because Phase 6 owns authentication/RBAC. Do not add dummy security mechanisms or imply that the endpoint boundaries are protected yet.
- PostgreSQL, Redis, and Azurite are available to the health probes only. Do not add database sessions, ORM models, Alembic, repositories, cache clients, queues, object-storage clients, or business persistence in this phase.
- Follow the architecture's REST/OpenAPI and Pydantic boundary conventions. Keep the Phase 2 worker readiness app health-only; do not turn it into a task worker in this phase.

## In-scope deliverables

1. A configurable FastAPI application factory and module-level ASGI app with clear metadata, lifecycle handling, the existing health router, local `/docs`, `/redoc`, and `/openapi.json` endpoints, and a deliberate API URL prefix.
2. Typed, injectable application settings for safe non-secret runtime configuration such as environment name, application metadata, log level/format, request-ID behavior, API prefix, and documentation availability.
3. Structured logging configuration using the architecture-selected `structlog`, including safe static context (`service`, `environment`) and request correlation context. No sensitive values or payloads may be automatically logged.
4. A centralized, versionable API response/error schema and exception-handler layer for expected API errors, request validation failures, HTTP 404/405-style failures, and unexpected server errors.
5. Central dependency providers for settings and request context, designed for FastAPI overrides in tests and later service/repository dependencies.
6. A route registry and route modules for auth, users, cases, documents, workflows, approvals, retrieval, evaluations, audit, and admin, all mounted by the application factory with stable prefixes and OpenAPI tags.
7. Backend unit/API tests for application creation, configuration injection, health-contract compatibility, OpenAPI/docs availability, router registry, response/error serialization, validation handling, request IDs, and safe unexpected-error behavior.
8. Updated locked dependencies, local-stack verification where useful, and developer documentation that accurately explains the Phase 3 API shell and its validation commands.

## Out of scope

- SQLAlchemy models, database sessions, Alembic configuration/migrations, pgvector extension creation, seed data, repositories, and integration tests against a database (Phases 4–5).
- Login/logout/current-user behavior, password hashing, sessions/tokens, rate limiting, RBAC, organization isolation, or separation-of-duties enforcement (Phase 6).
- Case, user, document, workflow, approval, retrieval, evaluation, audit, or admin business endpoints and their persistence (Phases 5, 8, 10–28).
- Returning fake `501 Not Implemented` CRUD/auth endpoints or placeholder data. A route module is a code ownership boundary, not a claim that a feature works.
- Celery/Dramatiq/Arq task execution, worker jobs, LangGraph, model providers, LangMem, document parsing, RAG, evaluations, or external enterprise integrations.
- CORS policy, CSRF, secure-header hardening, dependency/security scanning, production deployment settings, CI workflows, cloud resources, or production Dockerfiles (Phases 29 and 31–35).
- Frontend API client work, frontend screens, localization UI, or browser end-to-end tests (Phase 7 onward).

## Likely files, folders, modules, and services affected

### API application and core infrastructure

- `apps/api/pyproject.toml`
- `apps/api/src/app/main.py`
- `apps/api/src/app/health.py` (compatibility review only; retain the Phase 2 health contract)
- `apps/api/src/app/core/__init__.py`
- `apps/api/src/app/core/config.py`
- `apps/api/src/app/core/logging.py`
- `apps/api/src/app/core/errors.py`
- `apps/api/src/app/api/__init__.py`
- `apps/api/src/app/api/dependencies.py`
- `apps/api/src/app/api/router.py`
- `apps/api/src/app/api/schemas/__init__.py`
- `apps/api/src/app/api/schemas/common.py`
- `apps/api/src/app/api/routes/__init__.py`
- `apps/api/src/app/api/routes/auth.py`
- `apps/api/src/app/api/routes/users.py`
- `apps/api/src/app/api/routes/cases.py`
- `apps/api/src/app/api/routes/documents.py`
- `apps/api/src/app/api/routes/workflows.py`
- `apps/api/src/app/api/routes/approvals.py`
- `apps/api/src/app/api/routes/retrieval.py`
- `apps/api/src/app/api/routes/evaluations.py`
- `apps/api/src/app/api/routes/audit.py`
- `apps/api/src/app/api/routes/admin.py`
- `apps/api/src/app/workers/readiness.py` (do not change behavior; only adjust a shared import if needed to preserve the existing health contract)

### Tests, configuration, and documentation

- `apps/api/tests/api/test_health.py`
- `apps/api/tests/api/test_app_factory.py`
- `apps/api/tests/api/test_error_handlers.py`
- `apps/api/tests/api/test_openapi.py`
- `apps/api/tests/unit/test_config.py`
- `apps/api/tests/unit/test_logging.py` when logging setup has deterministic unit-test seams
- `pyproject.toml` and `uv.lock`
- `package.json` (only if a clearer root API-test/OpenAPI command is needed)
- `scripts/verify_local_stack.sh` (extend non-destructively to verify the API documentation/schema endpoint, if practical)
- `README.md`
- `docs/development.md`
- `.env.example` only if new safe, clearly documented application-level configuration values are necessary

Do not create database, service, worker-job, frontend, or cloud files merely to resemble the full target folder tree.

## API skeleton design contract

### 1. Application factory and lifecycle

1. Keep `create_api_app()` as the testable construction entry point and keep a module-level `app` for Uvicorn/Compose.
2. Allow tests to inject an `AppSettings` instance (or an equally typed settings dependency) without changing process environment variables. Production construction must read configuration lazily and deterministically from the environment.
3. Configure application title, description, version, contact/license fields only when known, OpenAPI tags, and URLs from settings. Default local routes must include:
   - `GET /health/live`
   - `GET /health/ready`
   - `GET /openapi.json`
   - `GET /docs`
   - `GET /redoc`
4. Use an explicit FastAPI lifespan (even if startup/shutdown currently only configures safe runtime resources) so later database/worker resources have one clear place to join the lifecycle. Do not open database/cache connections during startup in this phase.
5. Register middleware, exception handlers, the health router, and the aggregate product API router in one predictable order. The existing liveness/readiness behavior must remain dependency-free/safe as documented in Phase 2.

### 2. Typed configuration

1. Add a compact `AppSettings` model using Pydantic Settings. Use a project-specific environment prefix and validation for values such as:
   - `environment` (`local`, `test`, `staging`, or `production`);
   - application/service name and non-secret release/version label;
   - log level and local-vs-JSON log rendering choice;
   - API prefix, defaulting to `/api`;
   - documentation/OpenAPI enablement, enabled by default for local development; and
   - request-ID header name and bounded validation rules if configurable.
2. Read real environment variables first. If supporting a local `.env` file, make it opt-in or use the already ignored local file only; never load `.env.example` as runtime secret configuration and never put credentials in the settings model.
3. Provide a cached `get_settings()` dependency plus a test reset/override seam. Validation errors at process startup must be clear to operators but must not expose values.
4. Keep database, Redis, Azurite, object-storage, model-provider, auth, CORS, and security-policy settings out of the new general settings class unless they are already required by the existing health probes. Those concerns have assigned later phases.

### 3. Structured logs and request context

1. Add one idempotent logging configuration function called during application creation/lifespan. Use `structlog` with the standard-library logging bridge as appropriate for Uvicorn/FastAPI.
2. Bind safe process context to every application event: timestamp, log level, service name, environment, and event name. In request handling, bind a generated or validated correlation/request ID; return it in the configured response header.
3. Accept a client-supplied request ID only when it meets a conservative length/character policy; otherwise replace it with a generated UUID-like identifier. Do not reflect untrusted values blindly into logs or headers.
4. Log method, route template/status, duration, and safe error code. Do not log request bodies, authorization/cookie headers, query values by default, response bodies, exception strings, secrets, or connection URLs.
5. Ensure tests can configure or observe logging without accumulating duplicate handlers/context between application factories.

### 4. Common API response and error contract

1. Define reusable Pydantic v2 schemas for future API responses, including a typed success envelope/metadata model and a single error envelope. Keep identifiers/metadata optional only when that is a deliberate contract decision.
2. The error body must be stable and machine-readable. It should include a public error code, a Norwegian-or-neutral safe public message policy selected consistently for this backend phase, the correlation/request ID, and structured field-level validation details only when safe to disclose. Do not include exception class names, traceback text, internal paths, or secret-bearing input.
3. Define an `ApiError`/domain-exception base type carrying a deliberate status, error code, safe message, and optional safe details. Centralize FastAPI handlers for:
   - application `ApiError` instances;
   - Pydantic/FastAPI request validation errors (`422`);
   - Starlette HTTP errors, including unknown routes and unsupported methods; and
   - unexpected exceptions (`500`) with a generic response and a structured server-side error event.
4. Document all reusable error responses in OpenAPI via shared `responses` constants/helpers. Apply them only to real endpoints as they are implemented; do not fabricate feature endpoints just to populate docs.
5. Preserve the Phase 2 health response models. They are infrastructure contracts and must stay unwrapped; error handlers may only affect error paths where doing so is compatible with their documented safe readiness output.

### 5. Dependencies and stable route ownership

1. Create `app.api.dependencies` for typed settings/request-context providers and shared future dependency placeholders. Dependencies must not perform database I/O, create clients, or enforce authentication yet.
2. Create an aggregate API router, conventionally mounted at `/api`, which owns and includes the ten feature-group routers. Keep one source-of-truth registry containing each group name, tag, module, and prefix so implementation and tests cannot drift.
3. Create an importable module for each group with a correctly configured `APIRouter` and an accurate tag/description:
   - `auth`
   - `users`
   - `cases`
   - `documents`
   - `workflows`
   - `approvals`
   - `retrieval`
   - `evaluations`
   - `audit`
   - `admin`
4. Do **not** add pretend endpoints, empty data responses, or `501` operations. The route modules and registry establish stable code boundaries now; actual route operations are added only by their owning phases. Make this limitation explicit in application/docs metadata.
5. Use only documented, plural REST prefixes (for example `/users`, `/cases`, `/documents`, `/workflows`, `/approvals`, `/evaluations`) and architecture-aligned singleton/action prefixes (`/auth`, `/retrieval`, `/audit`, `/admin`) in the registry. Confirm later feature implementations use this registry rather than inventing competing top-level paths.

## Implementation tasks

### 1. Inspect and preserve the current foundation

1. Read `AGENTS.md`, this phase plan, the canonical specifications, Phase 1/Phase 2 plans, current API code, Docker configuration, documentation, and `git status` before editing.
2. Confirm `apps/api/src/app/main.py` currently exports both `create_api_app()` and `app`, and that Compose still points to the same import. Preserve that external process contract.
3. Run the existing health tests before making changes. Treat their direct health JSON bodies and no-secret failure checks as compatibility tests, not implementation details to remove.

### 2. Add only the dependencies the skeleton needs

1. Add bounded compatible versions of `pydantic-settings` and `structlog` to `apps/api/pyproject.toml`; retain existing FastAPI, HTTP, Redis, and asyncpg dependencies required for Phase 2 readiness.
2. Update `uv.lock` through the documented `uv` workflow. Do not hand-edit lockfile package metadata.
3. Do not add SQLAlchemy, Alembic, authentication libraries, Celery, OpenTelemetry SDKs, testcontainers, model SDKs, or storage clients; their phases own those dependencies.

### 3. Implement configuration and logging foundations

1. Add `app.core.config` with typed, validated settings and cached dependency construction.
2. Add `app.core.logging` with one idempotent configuration API, safe structlog processors/renderers, and context helpers used by request middleware and exception handlers.
3. Add focused tests for defaults, allowed environment/log-level values, invalid configuration handling, injected settings, request-ID normalization, and logging setup idempotence. Keep tests independent of the developer machine's environment.
4. Introduce only safe, documented configuration variables into `.env.example`; use visibly local/non-secret defaults and update documentation at the same time.

### 4. Add common API contracts and exception handling

1. Add `app.api.schemas.common` for the shared success/error Pydantic models and reusable documented error-response declarations.
2. Add `app.core.errors` for explicit API exception types and handler registration. Ensure handler code has access to the request correlation ID but never serializes raw exceptions.
3. Add middleware that creates/binds a request ID, measures duration, emits one safe completion event, and places the ID on every response. Ensure it does not interfere with health probe timeouts or readiness JSON.
4. Register handlers in the application factory. Test validation, unknown-route, explicit-domain-error, and unexpected-error cases through a temporary test-only route or focused app fixture; do not add production placeholder routes merely to make handlers testable.

### 5. Establish the API router registry

1. Add the aggregate router, route registry, and all ten feature router modules listed above.
2. Assign distinct, user-comprehensible OpenAPI tags and descriptions that state each group is an API boundary whose operations arrive in later phases.
3. Mount the aggregate router through `create_api_app()` while preserving health outside `/api`.
4. Add unit tests that assert the registry is complete, prefixes are unique and architecture-aligned, router modules are importable, and the application registers the aggregate boundary without defining deceptive business operations.

### 6. Finish the application factory and OpenAPI contract

1. Replace the Phase 2 health-only metadata in `main.py` with truthful Phase 3 API-skeleton metadata, retaining the health router and module-level app.
2. Configure OpenAPI generation consistently with common error schemas and route-tag metadata. Do not document security schemes until Phase 6 actually enforces them.
3. Add tests that fetch and validate `/openapi.json`, assert the selected title/version/description and health paths, verify `/docs` and `/redoc` render locally, and confirm schema generation does not expose secrets or nonexistent feature claims.
4. Keep `create_worker_app()` health-only. Its behavior need not gain product routers, API docs metadata, settings, or lifecycle side effects in this phase.

### 7. Update local validation and truthful documentation

1. Extend `scripts/verify_local_stack.sh` only if it can non-destructively check the API OpenAPI JSON and Swagger page while retaining all Phase 2 health/dependency checks. Do not start services, migrate databases, or create data in the verifier.
2. Update `README.md` and `docs/development.md` from “health-only API” to the accurate Phase 3 state: documented API skeleton, health endpoints, common error contract, and future route ownership—but no product operations/auth/database schema.
3. Document exact commands for unit/API tests, static checks, OpenAPI validation, and local Compose verification. Do not claim that an API group is functional just because its module is present.
4. Review the diff for secret values, overly broad environment logging, generated files, unnecessary scope expansion, and changed Phase 2 health semantics.

## Required tests and validation

Run all checks from the repository root after installing locked Node/Python dependencies. Resolve failures before considering the phase complete.

### Automated API/unit tests

```bash
uv run pytest apps/api/tests
```

At minimum, tests must prove all of the following:

- the API factory builds with default and injected settings without global-state leakage;
- Phase 2 `/health/live` and `/health/ready` behavior remains compatible, including safe `503` responses;
- every required feature route module appears in the source-of-truth registry with a unique, expected prefix/tag;
- `/openapi.json` is valid OpenAPI JSON and `/docs` plus `/redoc` respond successfully in a local/test configuration;
- the common success/error schemas serialize predictably;
- explicit API errors, request validation failures, unknown routes, and unexpected exceptions use the safe, consistent error envelope and correct HTTP status;
- error responses contain the correlation ID and never contain a deliberate secret/connection-string sentinel, exception class name, or traceback;
- request IDs are generated when absent, safely propagated when valid, and replaced/rejected when malformed;
- structured logging configuration is idempotent and request/error logging does not serialize sensitive test inputs.

### Static quality checks

```bash
pnpm format:check
pnpm lint
pnpm typecheck
```

Also run the direct Python commands when diagnosing failures:

```bash
uv run ruff format --check apps services packages scripts
uv run ruff check apps services packages scripts
uv run mypy apps services packages scripts
```

All new Python code must satisfy the existing strict mypy configuration with no broad `ignore_errors`, `Any` escapes, or untyped exception-handler shortcuts.

### Local OpenAPI and runtime validation

1. Start the existing local stack:

   ```bash
   pnpm dev:up
   ```

2. Verify the unchanged health contract and the new API documentation endpoints:

   ```bash
   curl --fail http://127.0.0.1:8000/health/live
   curl --fail http://127.0.0.1:8000/health/ready
   curl --fail http://127.0.0.1:8000/openapi.json
   curl --fail http://127.0.0.1:8000/docs
   curl --fail http://127.0.0.1:8000/redoc
   ```

3. Run the non-destructive stack verifier if updated:

   ```bash
   pnpm verify:local-stack
   ```

4. Confirm logs are structured and include only safe context. Exercise an invalid request and an unknown path; verify the response has the documented error envelope and request-ID header without disclosing internal details.
5. Stop the stack normally after manual verification:

   ```bash
   pnpm dev:down
   ```

### Manual architecture/scope review

- Compare the route registry with Architecture §11.2 and the roadmap Phase 3 route-group list.
- Verify application/core/api modules match the boundary style in Architecture §12, without prematurely adding database/service implementations.
- Confirm health routes remain public infrastructure routes and product API modules remain operation-free until their owning phases.
- Confirm docs/README describe only implemented Phase 3 behavior and clearly distinguish future boundaries from usable APIs.
- Confirm no configuration/log/error path exposes secrets, credentials, raw request content, or exception details.

## Completion criteria

Phase 3 is complete only when all of the following are true:

- The FastAPI API process retains a stable module-level ASGI application and injectable app factory compatible with the Phase 2 Compose runtime.
- Structured, typed configuration, safe structlog logging, request correlation, dependency providers, and lifecycle wiring are implemented and covered by tests.
- There is one documented Pydantic API success/error contract, and all central error paths return safe, predictable responses with correlation IDs.
- Phase 2 liveness/readiness endpoints and their safe error behavior remain passing compatibility tests.
- All ten future API route groups have clearly owned, importable, mounted router modules and a single source-of-truth registry, but no pretend product operations or placeholder data.
- Local `/openapi.json`, `/docs`, and `/redoc` work and accurately describe the Phase 3 shell without unsupported feature/security claims.
- Backend tests, format, lint, and strict type checks pass; local Compose validation succeeds for health and documentation endpoints.
- Dependencies are locked, documentation is updated truthfully, and no secret, schema/migration, authentication, business, AI, worker, or frontend work from later phases has been added.

## Risks and dependencies

| Risk or dependency | Impact | Required handling in this phase |
| --- | --- | --- |
| Breaking the Phase 2 health contract while refactoring `main.py` | Docker health checks and local startup can regress. | Keep health router/models stable; run existing tests first and retain them as compatibility tests. |
| Configuration created as global import-time state | Tests become order-dependent and environment changes require restart surprises. | Use an injectable factory/dependency with an explicit cache reset or override seam. |
| Verbose structured logs leak regulated or secret data | Violates security/privacy requirements before product data even exists. | Log only allowlisted metadata; never bind request bodies, headers, query values, or raw exceptions. Test redaction/absence explicitly. |
| Generic error handling hides readiness behavior or returns a different public shape | Operators and Compose checks cannot distinguish safe dependency failure. | Preserve health-specific models and test `503` readiness output independently. |
| Empty router modules appear to be incomplete or lead to fake endpoints | Future phases inherit misleading API contracts. | Use a documented registry/module ownership pattern and explicitly prohibit `501`/placeholder business operations. |
| OpenAPI documentation overstates delivered functionality | Portfolio/review users may believe unimplemented controls exist. | Use truthful metadata; document only health routes and structural API boundaries until actual operations are delivered. |
| Adding database/auth/security tooling early | Expands scope and creates difficult-to-remove temporary architecture. | Add only `pydantic-settings` and `structlog` if needed; defer all other dependencies to their assigned phases. |
| FastAPI/structlog integration produces duplicate handlers or context | Tests and production logs become noisy or ambiguous. | Make configuration idempotent, isolate setup in one module, and test repeated app construction. |

## Notes for the implementation agent

- This is final-product foundation work. Prefer small, composable modules with strict types over one large `main.py`, but do not fragment the API into deployable services.
- Preserve the existing route/process imports relied on by Docker. If a health refactor is useful, make it behavior-preserving and prove it with the pre-existing tests.
- Treat the route registry as the contract that prevents path drift. Feature phases should add real operations to these routers rather than inventing alternatives.
- Keep external messages conservative and truthful. Norwegian UI localization is a Phase 7 responsibility; for this backend skeleton, pick one stable safe message policy and document it rather than translating ad hoc.
- Request IDs and structured error codes are a pragmatic observability foundation, not a substitute for Phase 27 metrics/tracing or Phase 29 security hardening.
- Do not mark Phase 3 as `(DONE)` in `specs/roadmap.md` or update `specs/progress.md` during planning. The implementation agent performs those updates only after all required implementation and validation work passes.
