# Phase 6 — Authentication, Sessions, and RBAC

## Phase objective

Deliver the first protected product APIs: secure local email/password login,
logout, current-user lookup, server-side session handling, failed-login rate
limiting, and backend-enforced role-based access control (RBAC). The result must
bind the explicit organization context established in Phase 5 to a verified,
active user on every protected request. It must never accept an organization ID,
role, or identity from a request body, header, cookie payload, or frontend claim
as authorization evidence.

Phase 6 also completes the authentication-related PRD requirement that
administrators can manage users and role assignments within their own
organization. It establishes reusable authorization policy/dependency
primitives for the later case, document, approval, audit, and admin endpoints.
It does **not** implement the feature endpoints owned by those later phases.

## How this phase fits the final product

The platform handles regulated, organization-scoped information. Authentication
and RBAC are therefore a system boundary, not a frontend convenience: the API
must derive the organization from the authenticated account, then pass that
trusted context to the Phase 5 tenant-scoped repositories and services. The
Next.js login UI arrives in Phase 7; Phase 6 supplies the documented API it will
call. Case, document, workflow, approval, audit, and evaluation operations will
adopt the reusable current-principal and authorization dependencies in their
own phases.

The Phase 4 schema already contains `users`, global `roles`, and tenant-bound
`user_roles`, including `password_hash`, `is_active`, `organization_id`, and
`last_login_at`. Phase 5 introduced `IdentityService`, tenant-safe user lookup,
role assignment persistence, append-only `AuditService`, a request-owned
database transaction, safe errors, and stable route groups. This phase extends
those foundations rather than introducing a second identity store, a global
current-user variable, or unscoped queries.

## Relevant specification context and constraints

- PRD `FR-AUTH-001` requires email/password or enterprise-ready login,
  non-plaintext password storage, secure cookies or tokens, and failed-login
  rate limiting. This phase implements local email/password authentication;
  the existing identity-provider fields remain a future extension point, not an
  OIDC/SAML implementation.
- PRD `FR-AUTH-002` requires the roles **Admin**, **Compliance Reviewer**,
  **Case Worker**, **Manager**, and **Read-only Auditor**; backend role checks;
  admin user/role management; read-only audit access; and separation of duties
  so a case worker cannot approve their own high-risk case.
- PRD `FR-AUTH-003` and architecture §§10–11 require organization isolation.
  A protected request gets one organization only from its authenticated user;
  the identity and organization are passed to repository/service calls, which
  retain their database-level tenant predicates.
- Architecture §13.1 specifies Argon2id through `argon2-cffi`, session
  expiration, secure session/token handling, and failed-login rate limiting.
  Architecture §13.2 requires backend RBAC, admin-only user management,
  reviewer-only approval decisions, and audit-only read access. `Redis` is
  already part of the local deployment and is the appropriate volatile store
  for opaque sessions and rate-limit counters; PostgreSQL remains the system of
  record for users, roles, and audit records.
- API endpoints must use typed Pydantic request/response schemas and the
  existing `SuccessResponse` / safe `ErrorResponse` envelopes. They must expose
  real operations only on `/api/auth` and `/api/users` as owned by this phase;
  no placeholder feature CRUD may be added to other route groups.
- All client-visible failures must be generic and must not reveal whether an
  email exists, whether an account is disabled, role names not held by the
  caller, session values, Redis details, database details, password hashes, or
  raw exception text. Passwords, session IDs, cookies, authorization material,
  raw request bodies, and Redis keys must never be logged or written to audit
  event data.
- Keep audit events append-only and minimal. Record successful login/logout,
  known-account failed login where an organization can be determined, and
  administrator-driven user/role changes. Do not manufacture an organization
  for an unknown account merely to audit an invalid login.
- The Phase 4 migration already has the required user and role fields. Do not
  add a PostgreSQL session table or migration solely for this phase: sessions
  and counters are short-lived Redis state. Add a migration only if an actual
  schema defect is discovered and document why.
- The local seed currently deliberately contains password-free identities.
  Update it only through an explicit local-development-only password input so
  production secrets and a functional credential are never committed. Tests
  must create their own synthetic accounts and hashes.

## In-scope deliverables

1. A typed password-security module using Argon2id to hash, verify, and, when
   needed, rehash passwords. It must validate a bounded password input before
   hashing and provide a precomputed/dedicated dummy-hash verification path so
   unknown-email attempts do not create a simple timing oracle.
2. An injectable, typed Redis-backed auth-state abstraction with an opaque,
   cryptographically random session identifier, expiration, explicit
   invalidation, and an index or equivalent safe mechanism to invalidate a
   user's sessions when their password changes or their account is disabled.
   The raw session identifier must be cookie-only and must not be persisted in
   PostgreSQL, audit payloads, or logs.
3. A Redis-backed login-rate-limit abstraction that atomically limits both a
   normalized-email-derived key and a client-origin key within a configured
   rolling/fixed window. It must emit a safe `429` response with `Retry-After`
   (when known), fail closed on a limiter outage for the login endpoint, and
   never expose or log the email/address-derived keys.
4. Auth configuration for the Redis connection, cookie name/path, TTL,
   SameSite policy, local/test secure-cookie behavior, production-secure-cookie
   enforcement, password limits, and login rate-limit window/attempt settings.
   Validate settings without rendering secrets. Extend Compose and
   `.env.example` only with safe local configuration—not production URLs,
   passwords, tokens, or demo credentials.
5. Authentication service commands/results that use the existing
   `IdentityService`/repositories and `AuditService` to:
   - locate a user by normalized email without treating an input organization as
     trusted;
   - reject unknown, inactive, passwordless/identity-provider-only, and
     incorrect-password accounts with the same public invalid-credentials
     result;
   - update `last_login_at` only after successful verification;
   - create a fresh session only after successful verification;
   - resolve an active current user and current role names from an opaque
     session on every protected request; and
   - clear a session on logout, expiration, account disablement, or invalid
     backing user/organization state.
6. A typed immutable `Principal` (user ID, organization ID, display metadata,
   preferred language, and role set) plus centralized role constants and
   authorization policy helpers. Implement least-privilege checks for the five
   required roles and a reusable tenant guard that rejects a target
   organization unequal to `principal.organization_id` without revealing a
   cross-tenant resource.
7. A reusable high-risk approval policy for Phase 22. It must require the
   Compliance Reviewer role and reject an approval when a high-risk (or
   `requires_approval`) case was submitted by the same principal. The policy
   should accept only trusted IDs/risk flags loaded by the future approval
   service; it must not create approval routes or workflow behavior now.
8. Auth dependencies and OpenAPI security documentation:
   - public `POST /api/auth/login`;
   - protected `POST /api/auth/logout` and `GET /api/auth/me`;
   - an HTTP-only session-cookie security scheme shown on protected operations;
   - reusable `CurrentPrincipalDependency`, role-requirement factory, and
     tenant-resource guard for later routes; and
   - consistent `401`, `403`, `422`, `429`, and safe `500` response contracts.
9. Minimal administrator user/role management endpoints in the already-reserved
   Users route group, all restricted to Admin within the caller's organization:
   `GET /api/users`, `POST /api/users`, `GET /api/users/{user_id}`,
   `PATCH /api/users/{user_id}`, `GET /api/roles`, and
   `PUT /api/users/{user_id}/roles`. Use typed DTOs, bounded existing
   pagination/sorting, and server-derived organization scope. Creation may set
   an initial local password; password replacement and deactivation must
   invalidate sessions. Do not return a password hash or credential material.
10. Explicit audit events for successful authentication, logout, known-account
    failed authentication, and administrator identity/role changes. Ensure an
    expected login failure can produce its durable minimal audit event without
    being rolled back merely because the response status is `401`.
11. Synthetic test fixtures, developer documentation, and local-seed guidance
    that describe the real login flow, safe local-only credential provisioning,
    session invalidation, rate-limit behavior, RBAC matrix, and test commands.

## Out of scope

- A Next.js login screen, browser session UX, navigation guards, locale UI, or
  any frontend work (Phase 7).
- OIDC, SAML, SCIM, MFA, password-reset email, account recovery, production
  identity-provider provisioning, or social login. Keep the database/provider
  fields and service boundary ready for a future enterprise integration.
- Case submission/list/detail HTTP endpoints, document endpoints, retrieval,
  workflows, evaluation, exports, or UI. Their phases must apply the reusable
  authorization dependencies when the actual resources exist.
- Approval queue operations, approval persistence, workflow interruption, or
  risk evaluation (Phase 22/21). Only the policy primitive and its tests belong
  here.
- Full security hardening such as general API rate limits, CORS restrictions,
  CSP/security headers, upload protection, dependency scanning, and CSRF
  defenses beyond secure cookie defaults. Phase 29 owns the comprehensive
  hardening pass.
- PostgreSQL row-level security, production database accounts, long-term
  session analytics, retention jobs, or migrations for an auth-session table.
- Changing the five canonical global role names, making authorization decisions
  in the frontend, allowing an Admin to cross organization boundaries, or
  granting a default role to a user with no assignment.
- Marking the roadmap/progress status as complete during plan generation.

## Likely files, folders, modules, and services affected

### Core security, configuration, and volatile state

- `apps/api/pyproject.toml` and `uv.lock` — add the Argon2id dependency; retain
  the existing async-capable Redis dependency rather than adding a second
  client library.
- `apps/api/src/app/core/config.py` — typed auth, Redis, cookie, password, and
  login-limit settings with production-safe validation.
- `apps/api/src/app/core/security.py` — password hashing/verification and safe
  password input policy.
- `apps/api/src/app/core/rate_limit.py` — typed atomic login-limit policy and
  safe error translation.
- `apps/api/src/app/core/session_store.py` (or focused `services/auth` storage
  module) — Redis session store/client lifecycle and a test-double protocol.
- `apps/api/src/app/core/errors.py` — only add stable, safe auth/forbidden/
  rate-limit API errors if the shared error contract needs named helpers.
- `apps/api/src/app/main.py` and `apps/api/src/app/db/session.py` — only for
  safe Redis lifecycle disposal or injected-test wiring; preserve request-owned
  database transaction behavior.

### Identity, authorization, audit, and API surface

- `apps/api/src/app/db/repositories/identity.py` — scoped identity helpers for
  email lookup and deterministic role-name loading; no unscoped generic user
  access API.
- `apps/api/src/app/services/identity/service.py` — password-aware admin user
  creation/update, role replacement semantics if needed, and explicit session
  invalidation integration while retaining Phase 5 transaction rules.
- `apps/api/src/app/services/auth/__init__.py`, `service.py`, `principal.py`,
  `policy.py`, and `store.py` — authentication command handling, principal
  resolution, canonical roles, RBAC/action checks, tenant guard, and the
  high-risk separation-of-duties policy.
- `apps/api/src/app/services/audit/service.py` — reuse `AuditEventCreate`; only
  narrow supporting changes necessary for the documented auth event sequence.
- `apps/api/src/app/api/dependencies.py` — current-principal, session store,
  role guard, and tenant guard dependencies that derive scope from the session.
- `apps/api/src/app/api/schemas/auth.py`, `users.py`, and `__init__.py` —
  typed request/response DTOs that never serialize hashes or session values.
- `apps/api/src/app/api/routes/auth.py` — real login/logout/me handlers.
- `apps/api/src/app/api/routes/users.py` — minimal Admin-only user/role
  administration operations.
- `apps/api/src/app/api/schemas/common.py` and `apps/api/src/app/api/router.py`
  — only if shared response/OpenAPI descriptions need a narrow update; retain
  all other route groups as operation-free.

### Local setup, documentation, and tests

- `apps/api/src/app/db/seed.py` and `scripts/seed_local.py` — explicit,
  idempotent local-only login seed option; no committed functional password.
- `.env.example`, `docker-compose.yml`, `README.md`, and
  `docs/development.md` — safe Redis/auth configuration and truthful API/local
  credential instructions.
- `apps/api/tests/unit/test_security.py`, `test_auth_policy.py`,
  `test_rate_limit.py`, `test_session_store.py`, and `test_config.py`.
- `apps/api/tests/integration/test_auth_service.py` and existing integration
  fixtures — PostgreSQL identity/audit/session-invalidation behavior with two
  synthetic organizations.
- `apps/api/tests/api/test_auth.py`, `test_users.py`, `test_openapi.py`,
  `test_router_registry.py`, and test helpers — HTTP cookie, RBAC, error, and
  OpenAPI contracts using injected Redis/session/rate-limit fakes where that
  makes tests deterministic.

Avoid altering the Phase 4 models/migration, repository base tenant mechanism,
unrelated route groups, frontend, workers, infrastructure, or future feature
services unless a narrow compatibility change is necessary and recorded.

## Implementation tasks

### 1. Freeze the auth boundary and configuration contract

1. Define one canonical role type/constant set matching the five seeded global
   role names exactly. Avoid free-form role strings throughout handlers.
2. Add typed configuration for Redis, opaque-session cookie behavior, TTL,
   rate-limit thresholds/windows, and password bounds. Treat Redis URLs and any
   passwords/tokens as `SecretStr`-like values so configuration representations
   and validation errors cannot serialize them.
3. Make cookie security environment-aware and fail startup/configuration for a
   production setting that would issue an insecure cookie. Use `HttpOnly`,
   restrictive path/domain defaults, `SameSite=Lax` (or stricter where
   compatible), a finite max age, and `Secure` outside explicit local/test use.
   Do not put a bearer token in a JavaScript-readable cookie or response body.
4. Reuse the existing Compose Redis host/port defaults through typed settings;
   add only documented, public local values to `.env.example`. Keep external
   production configuration secret-injected and do not print Redis connection
   strings.
5. Extend application shutdown to close any lazily created Redis client once,
   as the existing database pools do. Imports, health checks, OpenAPI
   generation, and configuration construction must remain network-free.

### 2. Implement password handling without credential leakage

1. Add a small Argon2id adapter backed by `argon2-cffi`; centralize hashing,
   verification, malformed-hash handling, and `check_needs_rehash` behavior.
   Never write a custom password hash or depend on a reversible scheme.
2. Define input validation at the API boundary (trim policy, sensible minimum
   and maximum length, no password in a response). Keep the raw password local
   to the request/service call and never place it in command reprs, logs,
   exceptions, audit metadata, or test assertion text.
3. On login, normalize the email according to an explicit, limited policy
   (trim and casefold for lookup while preserving the stored display value as
   appropriate). Perform password verification with a dummy Argon2id hash when
   no eligible local-password user exists, then return the same generic invalid
   credentials outcome for unknown, inactive, external-only, and wrong-password
   accounts.
4. When a valid legacy Argon2id parameter set needs rehashing, replace only the
   stored hash in the existing request transaction after successful verification.
   Never create plaintext password columns or store passwords in seeds.

### 3. Add volatile session and rate-limit adapters

1. Define narrow protocols for `SessionStore` and `LoginRateLimiter` so unit/
   API tests can use deterministic fakes and production uses Redis. Do not let
   route modules issue Redis commands directly.
2. Create a cryptographically random opaque session ID after a successful
   password verification. Store only the trusted user ID, organization ID,
   issue/expiry metadata, and a bounded schema version in Redis with a TTL.
   The cookie is merely the opaque handle; do not trust claims from it.
3. Support `get`, `delete`, and `delete_all_for_user` (or equivalent indexed
   invalidation). Delete expired/malformed/stale sessions and invalidate all
   user sessions after a password replacement or account deactivation. Role
   assignments are loaded from PostgreSQL per protected request so role changes
   take effect immediately without trusting stale cookie claims.
4. Implement rate limits using an atomic Redis operation/script, separate keys
   derived from a one-way digest of normalized email and client origin, TTL
   bound to the rate window, and no plaintext address/email/key logging.
   Apply the limiter before expensive Argon2 verification and record success or
   reset only according to a documented anti-brute-force policy.
5. Treat a Redis failure as an unavailable security control on login, returning
   a safe failure rather than silently allowing unlimited attempts. Do not make
   health endpoints depend on Redis auth-state initialization.

### 4. Extend identity and audit services deliberately

1. Add the minimum identity repository queries required to find a user by
   normalized email, load their organization-bound role names deterministically,
   and update allowed identity fields. Global email uniqueness may be used for
   lookup, but the resulting organization comes only from the database row.
2. Build an `AuthenticationService` with typed login/logout/current-principal
   commands and result types. It composes `IdentityService`, the existing audit
   writer, the password adapter, and injected volatile stores; repositories
   remain session-owned and never commit independently.
3. Successful login must verify the account, refresh/re-hash when appropriate,
   update `last_login_at`, stage a minimal `auth.login_succeeded` event, and
   create a new session. Logout must invalidate the presented session and stage
   `auth.logout` with no session/cookie data.
4. For an expected credential failure, record only a minimal failure event when
   the verified database user/organization is known. Arrange the handler/service
   result so that this explicit audit write can commit while the client receives
   the standard safe `401` envelope; do not let a raised expected error force
   the request transaction to roll back the event. Unknown-account attempts
   still receive the same response but have no invented tenant audit row.
5. Administrator create/update/deactivate/password-reset/role-change actions
   must emit minimal identity audit events. Validate every target user through
   the caller's organization-scoped service query; a UUID from another
   organization follows the same not-found response as a missing UUID.

### 5. Centralize authentication and authorization rules

1. Define `Principal` only from an active user resolved through the server-side
   session record and database. Include `user_id`, `organization_id`,
   `display_name`, `preferred_language`, and immutable canonical role values;
   do not include or expose password/session material.
2. Add `get_current_principal` that reads the HTTP-only cookie, resolves the
   session, validates the persisted user is active and belongs to the session's
   organization, loads current roles, deletes stale state, and returns `401`
   for every unauthenticated/invalid session variant.
3. Add a composable `require_roles` dependency/policy that defaults to denial
   and returns `403` only for a valid authenticated principal lacking the
   required role. Use it for Admin user/role management and make it available
   to later feature routes. Do not rely on OpenAPI security metadata as actual
   authorization.
4. Add a tenant guard accepting a trusted resource organization ID obtained by
   an owning service/repository. It must reject a mismatch before a response can
   disclose another organization’s resource. Future resources must still use
   Phase 5 database predicates; this guard does not replace them.
5. Add `authorize_approval`/equivalent pure policy for future trusted approval
   input: require Compliance Reviewer, require matching tenant, and prohibit a
   principal from approving their own high-risk or `requires_approval` case.
   Keep approval decision endpoints and data writes out of this phase.
6. Document the initial access matrix: Admin manages users/roles in its own
   tenant; Compliance Reviewer is eligible for approval policy; Case Worker is
   eligible for case-work policies later; Manager is eligible for management
   views later; Read-only Auditor is eligible only for future audit reads. A
   principal may hold multiple roles; having no role grants no protected action.

### 6. Expose only Phase 6 HTTP operations

1. Add typed auth schemas for login input and a current-user safe view. Login
   returns a `SuccessResponse` with safe user/principal data, sets the opaque
   HTTP-only cookie, and never returns a session/token value. Logout clears the
   cookie using matching attributes and returns a typed success/empty response.
   `GET /api/auth/me` returns the resolved safe principal.
2. Apply `CurrentPrincipalDependency` to logout and me. Make login deliberately
   public, rate-limited, and documented as such. Ensure all responses retain
   the existing request ID and safe envelope behavior.
3. Add the six administrator-only Users operations listed in scope. All user
   fields derive organization from the current principal, use Phase 5 bounded
   pagination/allowlisted sort, prohibit cross-tenant ID access, and exclude
   hashes/identity subjects from views unless a later explicitly authorized
   feature requires them.
4. For role updates, accept only a validated role identifier/name from the
   canonical global-role set, replace/add assignments using explicit service
   semantics, prevent accidental duplicate assignment, and audit the change.
   Do not allow an API client to submit arbitrary role labels or organization
   IDs. Preserve a safe administrator continuity rule (for example, do not let
   the sole active Admin remove/deactivate itself) if role replacement makes
   that state possible; document the exact rule and test it.
5. Update `/docs` OpenAPI to show the cookie security scheme, operation-level
   protection, tags, real request/response schemas, and safe `401`/`403`/`429`
   errors. Replace Phase 3 tests that assert no product routes/security with
   precise assertions that only Phase 6 routes now exist; all future route
   groups remain operation-free.

### 7. Make safe local authentication usable without committing a password

1. Preserve the idempotent synthetic organization, role, and `demo.invalid`
   seed identities. Add an explicit opt-in local-only seed password source
   (command option or environment value intentionally absent from committed
   defaults), hash it through the same Argon2id adapter, and refuse production
   use.
2. The default seed invocation must remain safe and password-free unless the
   documented local login option is supplied. Never echo the supplied password
   or hash in the script output.
3. Update README/development instructions to state the real API endpoints,
   cookie behavior, local-seed option, synthetic-account names, safe credential
   handling, Redis dependency, rate-limit reset expectations, and all required
   validation commands. Remove prior claims that there are no product routes,
   authentication, or password hashes only where Phase 6 makes them stale.

### 8. Test the security contract before completion

1. Add focused unit tests for Argon2 hashing/verification/rehash, malformed
   hashes, password bounds, role parsing, role requirements, tenant guard,
   high-risk self-approval denial, and no-role default denial.
2. Test the Redis adapters with fakes and, where practical, integration coverage
   against the local/ephemeral Redis contract: expiry, explicit logout,
   stale-session rejection, user-wide invalidation, atomic rate-limit boundary,
   `Retry-After`, hashed keys/no sensitive key exposure, and fail-closed login
   behavior.
3. Add PostgreSQL integration tests using two synthetic organizations to prove
   email/password login resolves the stored organization, inactive and
   passwordless users cannot authenticate, role assignments load from the
   correct tenant, `last_login_at` updates only on success, and every auth/admin
   audit event has safe minimal data. Assert a failed known-account event is
   retained while an unknown account does not leak an organization.
4. Add API tests covering login, me, logout, cookie flags/clearing, expired or
   forged/stale session handling, disabled user, generic invalid credentials,
   rate limiting, and no token/hash/cookie leakage in body/log/error output.
5. Add API RBAC tests for anonymous `401`, authenticated-but-forbidden `403`,
   Admin success, no-role denial, current-role refresh after role change,
   cross-organization user UUID denial, all protected user routes, and
   admin-change audit events. Exercise the future approval policy independently
   with high-risk same-user and reviewer/different-user cases.
6. Assert OpenAPI declares the cookie security scheme and required protected
   operations while no case/document/workflow/approval/audit/admin operations
   are prematurely introduced. Retain health and existing safe-error tests.

## Required tests and validation

Run checks from the repository root with locked dependencies installed. Fix all
failures before marking the phase complete.

### Focused authentication and authorization validation

```bash
uv run pytest \
  apps/api/tests/unit/test_security.py \
  apps/api/tests/unit/test_auth_policy.py \
  apps/api/tests/unit/test_rate_limit.py \
  apps/api/tests/unit/test_session_store.py \
  apps/api/tests/integration/test_auth_service.py \
  apps/api/tests/api/test_auth.py \
  apps/api/tests/api/test_users.py \
  apps/api/tests/api/test_openapi.py
```

If exact test module names are consolidated differently, run the equivalent
focused unit, PostgreSQL integration, and API groups. The PostgreSQL tests must
use PostgreSQL 16 + pgvector through the established Testcontainers fixture, not
SQLite. Redis-dependent tests must use a deterministic fake or isolated Redis
instance and must not depend on a shared developer Redis database.

### Full backend and static validation

```bash
uv run pytest apps/api/tests
pnpm format:check
pnpm lint
pnpm typecheck
uv run ruff format --check apps services packages scripts
uv run ruff check apps services packages scripts
uv run mypy apps services packages scripts
```

All new Python must satisfy strict mypy. Do not use broad `Any`, `type: ignore`,
or catch-all exception suppression to force a session/Redis/security library
through type checks.

### Local stack and manual API validation

1. Start the local stack and explicitly migrate the database:

   ```bash
   pnpm dev:up
   docker compose --env-file .env.example exec api alembic -c apps/api/alembic.ini upgrade head
   ```

2. Provision a local-only synthetic login through the documented explicit seed
   option; do not paste a production or personal password into shell history,
   source, docs, or committed configuration.

3. Verify the existing stack and health routes:

   ```bash
   pnpm verify:local-stack
   curl --fail http://127.0.0.1:8000/health/live
   curl --fail http://127.0.0.1:8000/health/ready
   curl --fail http://127.0.0.1:8000/openapi.json
   ```

4. With an intentionally synthetic local password, manually verify that login
   receives an HTTP-only cookie, `GET /api/auth/me` requires it, logout clears
   it and invalidates it server-side, wrong credentials are generic, and repeat
   failed logins reach the documented `429` response. Inspect the returned
   OpenAPI schema to confirm cookie security and the Phase 6-only operations.

5. Confirm no connection string, password, hash, raw cookie/session ID,
   authorization header, or personal data appears in responses, logs, audit
   event data, docs, or seed output. Confirm no case/document/workflow/approval
   product endpoint was added.

6. Stop the stack normally after validation:

   ```bash
   pnpm dev:down
   ```

## Completion criteria

Phase 6 is complete only when all of the following are true:

- Email/password login uses Argon2id and the system never stores, returns, logs,
  audits, or seeds plaintext passwords.
- Session cookies are opaque, HTTP-only, finite-lived, and production-secure;
  server-side session state is validated on every protected request, and logout,
  expiry, deactivation, and password replacement invalidate access correctly.
- Failed login attempts are atomically rate-limited by non-sensitive derived
  keys; the public response is safe, has `Retry-After` when applicable, and a
  rate-limit-store outage does not silently remove login protection.
- `/api/auth/login`, `/api/auth/logout`, and `/api/auth/me` work with the
  declared typed response and safe error contracts. Login is public; logout and
  me are protected in both runtime behavior and OpenAPI.
- The five required canonical roles have centralized, tested backend policy;
  Admin-only user/role management cannot cross organization boundaries;
  non-admin/no-role callers are denied; and role updates take effect on the
  next protected request.
- Every authenticated request derives organization scope from the persisted
  principal. The reusable tenant guard and Phase 5 scoped repository contracts
  block cross-organization data access without existence leakage.
- The high-risk separation-of-duties policy is tested: a case worker cannot
  approve their own high-risk/requires-approval case, while an eligible
  reviewer in the same organization can progress to the future approval
  service. No Phase 22 endpoints are added.
- Auth and administrator identity changes append safe, minimal audit events;
  audit data contains no credentials, session identifiers, cookies, raw request
  bodies, or secrets.
- All focused, full backend, formatting, lint, strict type, OpenAPI, and local
  health/API validation checks pass. Documentation and local seed instructions
  accurately describe what now exists and what remains for later phases.
- The implementation remains inside this phase. Only after all criteria pass,
  mark Phase 6 `(DONE)` in `specs/roadmap.md` and update `specs/progress.md`
  consistently.

## Risks and dependencies

| Risk or dependency | Impact | Required handling in this phase |
| --- | --- | --- |
| Cookie contains a trusted identity or readable token | A forged/stolen browser value could impersonate a user. | Use a cryptographically random opaque ID, HTTP-only cookie flags, server-side Redis lookup, finite TTL, and no authorization claims in the cookie. |
| Session expiration/logout cannot be revoked | A user may retain access after logout, deactivation, or password reset. | Implement explicit delete and per-user invalidation; validate active DB identity on each protected request. |
| Password verification reveals account existence or leaks a hash | Account enumeration or credential exposure. | Use a dummy Argon2id verification path, one public invalid-credentials response, safe logs/errors, and tests for no leakage. |
| Redis rate-limit/session operations are non-atomic or unavailable | Brute-force protection can be bypassed or auth behavior becomes inconsistent. | Use an atomic counter/window operation, short TTLs, isolated test fakes, explicit lifecycle management, and fail closed for login. |
| An organization ID comes from the client | An authenticated user can try to access another tenant. | Derive organization solely from the session-resolved database user, use centralized tenant guard, and retain Phase 5 database predicates. |
| Roles are only checked in OpenAPI/frontend | Callers can invoke protected APIs directly. | Enforce role dependencies/policies in backend handlers and service boundaries; treat OpenAPI only as documentation. |
| Role assignment or password change leaves old access effective | Revoked users/roles retain inappropriate permissions. | Load current roles per request; invalidate sessions for password/deactivation; test next-request policy behavior. |
| Failed login audit event rolls back with the `401` | Required security evidence is silently absent. | Model expected invalid credentials as a controlled service result/response path that commits the minimal known-account audit event without exposing details. |
| High-risk separation rule is postponed until approval routes | Future approval implementation could accidentally allow self-approval. | Deliver a pure, tested policy now and require Phase 22 to call it with trusted case/risk data. |
| Local seed gains a committed usable password | Public demo/security hygiene is weakened. | Require an explicit local-only secret input, reject production use, use synthetic `demo.invalid` identities, and never echo it. |
| Scope expands into later feature phases | Reviewability and phased delivery are lost. | Restrict HTTP operations to auth and minimal admin user/role management; keep all other route groups operation-free. |

## Notes for the implementation agent

- Treat `phase6.md` as the scope authority and `architecture.md` §§10–13 and
  the existing Phase 4 models as the identity contract. Use the smallest
  reversible abstraction if an implementation detail is absent, and document
  the assumption in the final implementation report.
- Preserve the Phase 5 layering: handlers parse/format HTTP, dependencies
  resolve principal/policy, services coordinate application actions, and
  repositories own SQLAlchemy statements. Repositories do not commit/rollback
  and route handlers must not make raw SQL or Redis calls.
- Keep a clear distinction between authentication (`401`), authenticated but
  unauthorized (`403`), rate limited (`429`), invalid request (`422`), and a
  tenant-scoped missing resource (`404`). Never turn a cross-tenant target into
  a revealing `403` that confirms it exists.
- Use fake `demo.invalid` users and synthetic organization names in every test.
  Password values used in tests should be local literals confined to test code;
  do not write a hash, session ID, cookie, token, connection string, or raw
  request payload into documentation, audit metadata, snapshots, or logs.
- Do not weaken global authentication just because later product route groups
  are still empty. Future route handlers must opt into the provided current
  principal/role dependencies; health and documentation remain the intentional
  public endpoints for now.
- Do not mark the phase `(DONE)` or update progress until every required check
  has passed and the final report states implementation, changed files, test
  results, assumptions, and any follow-up limitation.
