# Progress

Implementation status for each roadmap phase. A phase is `DONE` only when its
implementation, tests, and validation checks pass within its defined scope.

| Phase | Title                              | Status |
| ----- | ---------------------------------- | ------ |
| 1     | Repository and Workspace Foundation | DONE   |
| 2     | Local Docker Development Environment | DONE   |
| 3     | Backend API Skeleton               | DONE   |
| 4+    | See `specs/roadmap.md`             | TODO   |

## Phase 3 — Backend API Skeleton (DONE)

Completed on 2026-06-20.

Delivered the durable FastAPI application foundation:

- Typed, injectable application settings (`app.core.config`) read from the
  `NORDIC_API_` environment prefix, with a cached `get_settings` provider and a
  test reset/override seam. No secrets and no database/Redis/MinIO values are part
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
- The Phase 2 health contract and worker readiness app are preserved unchanged.

Validation: `pnpm format:check`, `pnpm lint`, `pnpm typecheck`, and
`uv run pytest apps/api/tests` (62 tests) all pass. The local Docker stack
(`pnpm dev:up`) serves health and documentation endpoints, `pnpm verify:local-stack`
passes, and live logs contain only safe context with no secrets.
