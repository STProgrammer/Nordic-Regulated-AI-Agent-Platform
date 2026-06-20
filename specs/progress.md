# Progress

Implementation status for each roadmap phase. A phase is `DONE` only when its
implementation, tests, and validation checks pass within its defined scope.

| Phase | Title                              | Status |
| ----- | ---------------------------------- | ------ |
| 1     | Repository and Workspace Foundation | DONE   |
| 2     | Local Docker Development Environment | DONE   |
| 3     | Backend API Skeleton               | DONE   |
| 4     | Database Foundation and Migrations | DONE   |
| 5     | Backend Repository and Service Layer | DONE   |
| 6     | Authentication, Sessions, and RBAC | DONE   |
| 7+    | See `specs/roadmap.md`             | TODO   |

## Phase 3 — Backend API Skeleton (DONE)

Completed on 2026-06-20.

Delivered the durable FastAPI application foundation:

- Typed, injectable application settings (`app.core.config`) read from the
  `NORDIC_API_` environment prefix, with a cached `get_settings` provider and a
  test reset/override seam. No secrets and no database/Redis/Azurite values are part
  of this settings class.
- Safe structured logging (`app.core.logging`) via `structlog`, with idempotent
  configuration, static service/environment context, and request-correlation
  helpers. Request bodies, headers, query values, and raw exceptions are never
  logged.
- Request-correlation middleware (`app.api.middleware`) that assigns/validates an
  `X-Request-ID`, binds it to the log context, returns it on every response, and
  emits one safe completion event.
- A single JSON success/error contract (`app.api.schemas.common`) and centralized
  exception handlers (`app.core.errors`) for explicit API errors, request
  validation (422), unknown routes/method errors (404/405), and unexpected errors
  (500). Error responses never expose internals or secrets.
- A source-of-truth route registry (`app.api.router`) mounting ten operation-free
  product route boundaries under `/api`: auth, users, cases, documents, workflows,
  approvals, retrieval, evaluations, audit, admin.
- Truthful OpenAPI metadata plus local `/docs`, `/redoc`, and `/openapi.json`.
- The worker readiness app and the `/health/live` + `/health/ready` endpoint
  contract are preserved; the readiness storage dependency was later renamed from
  `minio` to `azurite` (see the storage-emulator migration below).

Validation: `pnpm format:check`, `pnpm lint`, `pnpm typecheck`, and
`uv run pytest apps/api/tests` (62 tests) all pass. The local Docker stack
(`pnpm dev:up`) serves health and documentation endpoints, `pnpm verify:local-stack`
passes, and live logs contain only safe context with no secrets.

## Storage emulator migration — MinIO → Azurite

The local object-storage emulator was migrated from MinIO to Azurite (the Azure
Blob Storage emulator) to match the Azure deployment target before any storage code
is built, when the change surface is smallest. This touched only local
infrastructure and the health probe: the Compose `azurite` and `azurite-init`
services, `.env.example` (`AZURITE_*` values using Azurite's well-known public dev
account), the API/worker readiness probe (the `minio` dependency became `azurite`),
the local-stack verifier, and docs. No application storage code exists yet; real
Azure Blob SDK integration still arrives in Phase 10.

## Phase 4 — Database Foundation and Migrations (DONE)

Completed on 2026-06-20.

Delivered the PostgreSQL 16 + pgvector persistence baseline:

- Typed SQLAlchemy 2 models for all Architecture §10.2 entities, with PostgreSQL UUIDs, JSONB,
  INET, arrays, numerics, conservative foreign keys, tenant-reference constraints, soft-archival
  fields, and `lazy="raise"` relationships.
- One Alembic baseline migration enabling `pgcrypto` and `vector`, creating all tables, named
  indexes and constraints, a `vector(1536)` HNSW cosine index, a language-neutral GIN full-text
  index, and database triggers for UTC `updated_at` values. The downgrade/replay path retains
  shared PostgreSQL extensions safely.
- Secret-safe runtime/Alembic database configuration, lazy async engine/session construction, a
  migration status checker, and explicit pool disposal during API shutdown.
- Explicit, idempotent synthetic local fixtures: one fake Norwegian organization, the five future
  RBAC roles, and `demo.invalid` identities without password hashes or a login path.
- PostgreSQL Testcontainers integration coverage for migration/index contracts, all representative
  entity persistence, tenant and uniqueness constraints, seed idempotence, and downgrade/re-upgrade.

Validation: all static checks pass; the focused database suite (`uv run pytest apps/api/tests/unit
apps/api/tests/integration`) passes 36 tests and the complete API suite passes 68 tests. A rebuilt
local Compose stack passed explicit migration/status/seed, rollback and replay, local-stack
verification, health, readiness, and OpenAPI checks. The stack was shut down normally after
validation.

## Phase 5 — Backend Repository and Service Layer (DONE)

Completed on 2026-06-20.

Delivered the internal FastAPI data-access boundary on top of the Phase 4
PostgreSQL schema:

- Explicit async SQLAlchemy repositories for organization roots, tenant-scoped
  users and user-role assignments, cases, document metadata, workflow runs, and
  append-only audit events. Tenant queries require `organization_id` in every
  get, list, update, archive, and count predicate; a cross-organization UUID is
  indistinguishable from a missing record.
- Typed, bounded offset pagination, stable page metadata, model-owned sort
  allowlists, deterministic UUID tie breakers, and explicit archive inclusion
  for cases/documents only. No caller-controlled SQL field or direction is used.
- Thin typed internal services that validate tenant-bound references, retain the
  outer request transaction owner, and translate known `IntegrityError` failures
  through a narrow savepoint to stable safe service errors.
- Explicit `AuditService.record_event` support with JSON-safe metadata
  validation and forbidden secret/request-body fields. Audit reads do not emit
  events; the repository intentionally has no update, delete, or archive API.
- Shared PostgreSQL/pgvector integration fixtures and unit/integration coverage
  for isolation, CRUD persistence, archives, pagination/sorting, savepoint
  recovery, role-assignment scoping, and append-only audit access. Product routes
  remain operation-free, and authentication/RBAC is still deferred to Phase 6.

Validation: `uv run pytest apps/api/tests` passes 85 tests, including PostgreSQL
Testcontainers coverage. `pnpm format:check`, `pnpm lint`, `pnpm typecheck`,
`uv run ruff format --check apps services packages scripts`, `uv run ruff check
apps services packages scripts`, and `uv run mypy apps services packages scripts`
all pass. A rebuilt local Compose stack passed explicit migration/status checks,
`pnpm verify:local-stack`, and live/readiness/OpenAPI curl checks, then was
stopped normally.

## Phase 6 — Authentication, Sessions, and RBAC (DONE)

Completed on 2026-06-20.

Delivered the first protected product APIs and their security boundary:

- Argon2id local-password handling with bounded input validation, malformed-hash
  safety, rehash support, and dummy verification for non-eligible accounts.
- Opaque, HTTP-only, finite Redis sessions with user-wide invalidation on
  password replacement/deactivation, current active-user validation, and current
  role loading from PostgreSQL on every protected request.
- Atomic Redis failed-login limits keyed by HMAC-derived normalized-email and
  client-origin digests, safe `429`/`Retry-After` handling, and fail-closed login
  behavior when the security store is unavailable.
- Cookie-secured `/api/auth/login`, `/api/auth/logout`, and `/api/auth/me`, plus
  OpenAPI cookie security documentation and consistent safe response envelopes.
- Canonical backend RBAC for Admin, Compliance Reviewer, Case Worker, Manager,
  and Read-only Auditor; reusable role/tenant dependencies; and a tested future
  high-risk self-approval separation-of-duties policy.
- Admin-only, organization-scoped `/api/users` and `/api/roles` operations with
  bounded user listing, canonical role replacement, password/deactivation session
  invalidation, safe cross-tenant not-found behavior, sole-active-Admin continuity,
  and minimal append-only audit events.
- Explicit local-only synthetic password provisioning through an environment
  variable name, never a committed credential; updated developer/API guidance.

Validation: focused security/auth/API coverage plus the full backend suite pass
(`108 passed`). `pnpm format:check`, `pnpm lint`, `pnpm typecheck`, Ruff format/
lint, and strict mypy all pass. A rebuilt Compose stack passed migrations,
local-stack verification, health/readiness/OpenAPI checks, and manual login,
cookie, logout, rate-limit, and log-leakage checks before normal shutdown.
