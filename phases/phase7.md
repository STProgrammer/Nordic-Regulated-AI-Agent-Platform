# Phase 7 — Frontend Application Shell

## Phase objective

Build the durable Next.js frontend foundation for the Nordic Regulated AI Agent
Platform. The result is a typed, tested, localized application shell that lets a
user authenticate against the Phase 6 API, maintains the opaque server-side
session through the browser, and provides accessible authenticated navigation
to the future Case Inbox, Approval Queue, Evaluation, Admin, and Audit areas.

This phase delivers the application framework and authentication UX, not the
business features behind the destination areas. It must replace the current
static Compose web readiness page with a real Next.js development service,
while retaining an explicit, health-checkable local web contract.

## How this phase fits the final product

The PRD positions the product as a Norwegian-language enterprise workflow
system, not a generic chat interface. A professional web shell is the shared
surface on which later phases add case management (Phase 9), documents and
evidence (Phase 14), approval (Phase 22), traces/audit (Phase 23), and
evaluation reporting (Phase 26). Establishing routing, localization, data
fetching, forms, safe API errors, and layout conventions now prevents each of
those feature phases from inventing incompatible frontend infrastructure.

Phase 6 is the only currently implemented product API. It exposes:

- `POST /api/auth/login`, which accepts email/password and sets an opaque,
  HTTP-only session cookie;
- `POST /api/auth/logout`; and
- `GET /api/auth/me`, which returns the current safe principal in the standard
  success envelope.

The frontend must integrate with those endpoints as they exist. It must not
attempt to decode, store, manufacture, or inspect a session identifier; the
FastAPI backend remains the authorization authority. Later API endpoints are
not available yet and must not be mocked as product behavior merely to fill
pages in this phase.

## Relevant specification context and constraints

- Roadmap Phase 7 requires **Next.js**, TypeScript, routing, layout, shared UI
  components, API client, form handling, server-state management, Norwegian
  Bokmål by default, optional English, authenticated navigation, and passing
  lint/type/component/local-connectivity/language-switch validation.
- PRD `FR-UI-001` requires Norwegian Bokmål for primary labels, navigation,
  workflow statuses, and user messages, with an English option. Norwegian
  date/number/currency formatting must have a shared foundation now; the
  complete UX-polish and accessibility pass remains Phase 30.
- PRD `FR-UI-005` requires keyboard navigation, field labels, clear errors,
  readable contrast, semantic HTML, and non-colour-only important states.
  Apply these as baseline shell standards, without claiming that the dedicated
  Phase 30 accessibility audit is complete.
- Architecture §§4.1, 6.1, 12, 17.4, and 18.2 select Next.js, React,
  TypeScript strict mode, Tailwind CSS, shadcn/ui-style components, TanStack
  Query, React Hook Form, Zod, next-intl, Vitest, and Testing Library. Follow
  the documented `apps/web/src/app/[locale]`, `components`, `lib`, and `tests`
  boundaries.
- Architecture §§11 and 13 require the REST/OpenAPI API boundary and secure
  cookie handling. Use the API's `SuccessResponse` and `ErrorResponse` JSON
  envelopes and its `X-Request-ID` response header. Do not introduce a second
  auth protocol or a frontend-only authorization decision.
- The browser must call same-origin `/api/...` paths. Configure a server-side
  Next.js rewrite/proxy to the API service so the existing HTTP-only cookie is
  issued and sent on the web origin. Use an internal origin such as
  `http://api:8000` in Compose and a host-development override such as
  `http://127.0.0.1:8000`; never expose it as a `NEXT_PUBLIC_*` secret or place
  a session token in JavaScript-readable storage. Do not add broad API CORS or
  security-hardening work; Phase 29 owns that work.
- All visible data is still synthetic. Do not add demo credentials, personal
  data, browser persistence of password values, or client-side secrets.

## In-scope deliverables

1. A real `apps/web` Next.js App Router application, configured for strict
   TypeScript, Tailwind CSS, reusable shadcn/ui-style primitives, linting,
   formatting, build, and component-test execution through the existing pnpm
   workspace.
2. Locale-aware routes with Norwegian Bokmål as the default (`nb`) and English
   (`en`) as the optional alternative, backed by `next-intl` message catalogs
   and a shared locale/formatting module.
3. A responsive, semantic application layout with a skip link, header/sidebar
   or compact mobile navigation, account area, language switcher, and clear
   active-route treatment. It must expose authenticated destinations for Cases,
   Approvals, Evaluations, Admin, and Audit.
4. A login page implemented with React Hook Form and Zod, plus an authenticated
   session provider/guard built on TanStack Query and the existing auth API.
   It must support login, initial current-user lookup, logout, redirect to the
   localized login screen when unauthenticated, and a safe loading/error state.
5. A typed, framework-independent API client for the current auth contract,
   including standard-envelope parsing, safe typed failures, request-id
   preservation, and credentialed same-origin requests.
6. Honest authenticated placeholder pages for the future feature areas. Each
   page identifies the pending capability without fabricating case, approval,
   evaluation, admin, or audit data.
7. Local Docker Compose integration for the Next.js web service, including
   replacement of the static readiness page and an updated local verifier.
8. Vitest/Testing Library coverage for the shell's critical behavior and
   documentation/tooling updates that make the Phase 7 workflow reproducible.

## Out of scope

- Case addition, inbox data, filtering, detail views, case status changes, or
  case API implementation (Phases 8–9).
- Document upload, document display, evidence rendering, retrieval, RAG,
  LangGraph workflows, risk decisions, workflow traces, approvals, audit data,
  evaluation data, exports, or model settings. The navigation destinations are
  shell placeholders only until their owning phases.
- A self-service user-preference API or LangMem persistence for the selected
  locale. Locale choice is route-based in this phase; controlled preference
  memory is Phase 24.
- OIDC/SAML/MFA/account recovery, password reset, user administration UI, role
  management UI, or changes to the Phase 6 authentication contract.
- Frontend route middleware that treats an unverified cookie as authorization,
  client-side RBAC as a security boundary, or changes to backend tenant/RBAC
  enforcement. UI role data may be displayed as account context only.
- Playwright feature smoke flows (Phase 9), full axe-core accessibility testing
  and Norwegian UX polish (Phase 30), production web image hardening (Phase
  32), and CORS/security-header hardening (Phase 29).
- New backend feature routes, database migrations, shared-schema code
  generation, or an OpenAPI client generation pipeline.

## Likely files, folders, modules, and services affected

### Web application and tooling

- `apps/web/package.json`, `apps/web/tsconfig.json`, `apps/web/next.config.ts`,
  Tailwind/PostCSS configuration, and the pnpm lockfile — establish the Next.js
  application and its locked frontend dependencies.
- `apps/web/src/app/[locale]/layout.tsx`, `page.tsx`, `login/page.tsx`, and
  `cases/`, `approvals/`, `evaluations/`, `admin/`, and `audit/` route folders
  — localized App Router layout, login, and authenticated shell destinations.
- `apps/web/src/middleware.ts` (or the equivalent next-intl routing entrypoint
  required by the selected compatible Next.js version), `src/i18n/`, and
  `apps/web/messages/` — locale detection, routing, type-safe message catalogs,
  and Norwegian/English copy.
- `apps/web/src/components/layout/`, `components/auth/`, `components/ui/`, and
  `components/providers/` — shell, account/navigation controls, login form,
  query provider, and small reusable UI primitives.
- `apps/web/src/lib/api/`, `lib/auth/`, `lib/formatting/`, and
  `lib/validation/` — typed auth client/contracts, query keys/hooks/session
  helpers, locale-aware formatting, and Zod form schemas.
- `apps/web/src/tests/unit/` plus Vitest setup/configuration — deterministic
  component and API-client test support.

### Local runtime and repository workflow

- `infra/docker/web.dev.Dockerfile` (new) and `docker-compose.yml` — replace
  the nginx placeholder with the Next.js development service, expose port 3000,
  set a container-only API origin, and retain a web health check.
- `infra/docker/web-readiness.html` — remove once no longer referenced.
- `scripts/verify_local_stack.sh` — assert the real web shell's stable local
  readiness marker rather than the removed Phase 2 static-page text.
- Root `package.json`, `eslint.config.mjs` only if required for App Router
  linting, `pnpm-lock.yaml`, `.env.example` only for documented non-secret web
  configuration, `README.md`, `docs/development.md`, and `apps/web/README.md`
  — add truthful web scripts, local startup/test instructions, and updated
  current-scope documentation.

Do not modify database models/migrations, authentication services/routes,
worker services, or unimplemented product APIs unless a narrow compatibility
defect is discovered and separately justified.

## Implementation tasks

### 1. Establish the Next.js workspace without weakening existing standards

1. Replace the Phase 1 placeholder web package with a Next.js App Router
   application compatible with the repository's Node 24 and pnpm 11.8
   constraints. Keep the workspace package private and retain the existing
   `apps/web` boundary.
2. Add only the frontend dependencies required by the architecture and this
   phase: Next.js/React, next-intl, Tailwind/shadcn component support, TanStack
   Query, React Hook Form, Zod plus its resolver, Vitest, Testing Library, and
   their necessary type/test utilities. Resolve and commit all versions through
   pnpm; do not introduce npm, Yarn, a second lockfile, or unpinned download
   scripts.
3. Update the web TypeScript configuration to include Next-generated types and
   application/test source while preserving the root strict options, including
   `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes`. Keep module
   aliases explicit and type-safe.
4. Add package-level `dev`, `build`, `start`, `lint`, `typecheck`, and `test`
   scripts, then expose focused root commands such as `pnpm test:web` without
   breaking existing aggregate lint/type/format commands. If Next's ESLint
   integration requires a flat-config addition, make it scoped to web files and
   preserve the repository's zero-warning policy.
5. Configure Tailwind and a deliberately small initial component set. Use
   reusable semantic primitives (for example button, input, label, card,
   alert, menu/popover) rather than duplicating styling per route. Do not build
   case/evidence/approval-specific components in this phase.

### 2. Build locale routing and translated shell copy

1. Define exactly two supported UI locales: `nb` and `en`, with `nb` as the
   default. Use next-intl's supported routing mechanism for the selected Next
   version to normalize `/` to the Bokmål route and preserve the active route
   when switching language.
2. Add complete, type-checked Norwegian and English message catalogs for the
   Phase 7 UI: application name, login fields/actions, navigation labels,
   loading/unauthenticated/error states, account/logout controls, and each
   honest placeholder page. Norwegian text is the source/default; avoid
   scattered hard-coded UI strings in components.
3. Add a shared locale module that maps route locale to `Intl` locale (at
   least `nb-NO` and `en`) and exposes date, number, and currency formatting
   helpers for later features. Do not invent case-specific dates, numbers, or
   financial values just to exercise the helpers.
4. Add a keyboard-accessible language switcher that uses explicit text labels
   and routes rather than mutable global state. It should retain the current
   page where a localized counterpart exists. It must not claim to save the
   choice to a user profile because no self-preference API exists yet.

### 3. Add the shared accessible layout and destination routes

1. Build the locale layout with semantic landmarks, a visible-on-focus skip
   link, meaningful page title metadata, a responsive navigation pattern, and
   a clear current-page indicator that does not rely on colour alone.
2. Add the authenticated application shell with navigation for **Cases**,
   **Approvals**, **Evaluations**, **Admin**, and **Audit**, an account summary,
   language control, and logout action. The labels, page titles, empty states,
   and status text must use the locale catalog.
3. Add a compact mobile navigation equivalent that remains keyboard-operable;
   do not hide primary destinations solely because of viewport size.
4. Add localized protected placeholder pages under each route. They should
   state that the relevant product area arrives in its roadmap phase and offer
   no disabled controls that imply data or permissions exist. The root
   authenticated route may redirect to the Cases placeholder as the future
   primary workspace.
5. Keep the shell presentation role-aware only as an optional display concern
   (for example account role labels). Do not hide or enable an action as a
   substitute for backend authorization; every future data operation must still
   be enforced by FastAPI.

### 4. Add a typed, same-origin API client for the Phase 6 contract

1. Define TypeScript representations of the existing API envelopes,
   `CurrentUserData`, login request, logout response, typed error detail, and
   a domain-specific API failure that carries only safe `code`, `details`,
   `requestId`, HTTP status, and retry information. Keep the client inside
   `lib/api`; route components must not call `fetch` directly.
2. Implement a single request helper that targets relative `/api/...` paths,
   sends JSON only when appropriate, uses `credentials: 'include'`, accepts
   the response envelope, reads `X-Request-ID`, and turns malformed/non-JSON
   responses into a generic safe client error. Never log request bodies,
   passwords, cookies, or server error payloads verbatim.
3. Implement auth operations over that helper: current-user lookup, login, and
   logout. Validate response data at the frontend boundary with Zod (or an
   equivalent narrow runtime schema) so an API-contract mismatch reaches the
   UI as a safe recoverable error rather than corrupting session state.
4. Configure `next.config.ts` rewrites so browser requests remain same-origin
   while the server forwards `/api/:path*` to a non-public `API_ORIGIN`. In
   Compose set it to `http://api:8000`; for host development document a local
   override to `http://127.0.0.1:8000`. Confirm the proxy forwards API
   `Set-Cookie` and receives the existing cookie on subsequent calls.
5. Do not use localStorage, sessionStorage, URL fragments, or React state to
   persist the session identifier. The browser cookie and `/api/auth/me` are
   the only session source of truth.

### 5. Implement login, session-aware navigation, and safe UX states

1. Add a TanStack Query provider at the app root with a deliberate query-error
   policy: do not repeatedly retry `401`, `403`, `422`, `429`, or `503` auth
   failures. Establish stable auth query keys and invalidate/reset them after
   successful login or logout.
2. Implement the localized login page with React Hook Form and a shared Zod
   schema matching the public Phase 6 input bounds (valid email and a write-only
   password bounded at 512 characters). Use labelled fields, descriptive
   validation text, proper autocomplete attributes, submit disablement while
   pending, and focusable error feedback. Do not prefill, retain, or report a
   password after a request completes.
3. Translate API error codes into clear local UI messages. Preserve a server
   request id only as support/debug context when safe; show the `Retry-After`
   duration for rate limiting where available. Do not surface the API's raw
   English message as the user-facing Norwegian default and do not reveal
   account-existence details.
4. Resolve `GET /api/auth/me` once through the auth query. While that state is
   loading, render an accessible loading state; when it returns an ordinary
   unauthenticated error, redirect protected routes to the localized login page
   with a safe return-path. Treat an unexpected API/availability failure as an
   explicit retryable error, not proof that the user is logged out.
5. On login success, clear the password field, refresh the current principal,
   and redirect to the validated internal return path or Cases. On logout,
   call the API, clear/invalidate cached principal data, and route to the
   localized login page even if the user was already unauthenticated. Continue
   to rely on the backend for valid-session, tenant, and role decisions.

### 6. Replace the temporary web container and document its contract

1. Add a local-development `infra/docker/web.dev.Dockerfile` using the pinned
   Node/pnpm toolchain and workspace lockfile. It must start the web app on
   `0.0.0.0:3000` and not be presented as the Phase 32 production image.
2. Replace the nginx `web` service in `docker-compose.yml` with a build of the
   new web Dockerfile. Keep its loopback-only published port, healthcheck,
   dependency behavior appropriate to a frontend that proxies API requests,
   and the rest of the local stack unchanged. Set the container-only API origin
   in the Compose service environment rather than publishing it to browser
   JavaScript.
3. Remove the obsolete static readiness asset and change
   `scripts/verify_local_stack.sh` to check a stable, localized-independent
   web marker (for example application shell metadata) while retaining its
   non-destructive behavior and all API/worker/storage checks.
4. Update `README.md`, `docs/development.md`, and `apps/web/README.md` to
   describe the real Phase 7 shell, host versus Compose API-origin setup, test
   commands, safe local login provisioning already defined in Phase 6, and the
   fact that future product pages are placeholders. Do not write a password to
   documentation or committed environment files.

### 7. Add focused component and integration-boundary tests

1. Configure Vitest with jsdom, Testing Library, user-event, and a shared test
   setup that resets query clients/router state between tests. Use deterministic
   fetch fakes or a narrowly scoped mock-server helper; tests must never require
   live API, Redis, credentials, or Docker.
2. Test the API client against the exact current Phase 6 envelopes: successful
   login/me/logout parsing, `credentials: 'include'`, request-id/error mapping,
   rate-limit retry metadata, safe malformed-response handling, and rejection
   of invalid response shapes.
3. Test the login form for Bokmål default labels, English rendering, client-side
   validation, pending state, generic invalid-credential feedback, rate-limit
   feedback, password clearing, and successful redirect/session refresh.
4. Test authenticated-shell behavior: loading state, unauthenticated redirect,
   retryable unavailable-state handling, rendered primary navigation, logout,
   active-route semantics, and placeholder-page honesty. Test the language
   switcher from multiple routes to confirm locale/route preservation and
   Norwegian-default behavior.
5. Include a small baseline semantic/accessibility assertion in component tests
   (label associations, landmarks, skip link, current navigation state, and
   non-empty accessible names). Do not claim that this replaces the Phase 30
   axe-core audit.

## Required tests

- `pnpm format:check` — formatting remains valid across the generated frontend
  configuration and source.
- `pnpm lint:web` and `pnpm typecheck:web` — strict linting and TypeScript
  checks pass for the Next.js application.
- `pnpm test:web` — Vitest/Testing Library tests described above pass without
  external services.
- `pnpm lint` and `pnpm typecheck` — repository aggregate checks still pass.
- `pnpm test:api` — the Phase 6 API contract remains green, since the frontend
  relies on its existing behavior.

## Validation steps

1. From a clean checkout, run `pnpm install --frozen-lockfile` and confirm the
   web package resolves from the committed pnpm lockfile.
2. Run all required static and component test commands. Confirm no browser-only
   globals, untyped API payloads, or hard-coded locale strings evade checks.
3. Start the local stack with `pnpm dev:up`, then run the existing migration and
   synthetic local-account provisioning workflow from the README. Run
   `pnpm verify:local-stack` to verify the replacement web service plus the
   existing API/worker/storage contracts.
4. In a browser at the local web URL, verify that `/` opens in Norwegian
   Bokmål, switching to English preserves the route, and the unauthenticated
   route sends the user to localized login without exposing an API token.
5. Sign in using only a locally provisioned synthetic account. Verify that the
   session survives a reload through `/api/auth/me`, all five authenticated
   navigation destinations render their honest placeholders, logout removes
   access to the shell, and invalid credentials/rate limiting display safe
   localized feedback.
6. Inspect browser storage/network behavior: no session identifier or password
   appears in local/session storage, URLs, console logging, or UI; API requests
   are relative `/api/...` requests through the Next.js proxy; the HTTP-only
   cookie remains inaccessible to client JavaScript.

## Completion criteria

- `apps/web` contains a buildable, strict TypeScript Next.js App Router
  application with the architectural frontend stack appropriate to this phase.
- Norwegian Bokmål is the default visible UI language, English is selectable,
  localization is catalog-backed, and route-preserving language switching works.
- A user can authenticate with the real Phase 6 API through same-origin
  requests, the opaque cookie is never handled by frontend code, session lookup
  works after reload, and logout reliably returns the user to login.
- Authenticated users see accessible navigation for Cases, Approvals,
  Evaluations, Admin, and Audit; destination pages are explicitly placeholders
  and contain no fabricated feature data.
- The local Compose web service runs the real frontend, passes its health/local
  verifier contract, and can reach the API through the server-side proxy.
- Required lint, formatting, type, component, API-regression, and local-stack
  validation checks pass.
- No backend authorization architecture, database schema, or future-phase
  product feature has been expanded or bypassed.

## Risks and dependencies

- **Cookie proxy behavior:** The browser-facing web app and FastAPI service use
  different Compose services. The rewrite must be verified specifically for
  `Set-Cookie` forwarding and follow-up `me`/logout requests. If the selected
  Next version changes rewrite behavior, keep the same-origin design and make
  the smallest compatible server-side adjustment; do not fall back to
  JavaScript-held tokens.
- **Host versus container API origins:** `api` is valid only inside Compose;
  host development needs a local loopback override. Keep the origin server-only
  and document both modes to prevent a confusing blank login flow.
- **Version compatibility:** Next.js, next-intl, React, Vitest, and Tailwind
  must be selected as a mutually compatible set for Node 24 and the existing
  ESLint/TypeScript toolchain. Resolve this once in the committed lockfile.
- **No product endpoints yet:** Only auth endpoints are real. Placeholder pages
  must remain intentional so the shell does not add a misleading impression
  that case, audit, or evaluation data is available.
- **Security boundary:** Frontend redirects and navigation improve UX but do
  not authorize anything. Future routes must keep using Phase 6 backend
  dependencies and Phase 5 organization-scoped services.
- **Accessibility scope:** The shell must start with sound semantics, but full
  cross-browser/axe accessibility coverage and final Norwegian UX refinement
  are intentionally deferred to Phase 30.

## Notes for the implementation agent

- Start by reading this file, then inspect the actual Phase 6 auth schemas and
  routes before defining TypeScript contracts. Treat the current API envelope
  as the integration source of truth; do not infer future endpoint shapes.
- Keep frontend modules small and feature-boundary oriented. A route should
  compose components/hooks; fetch, locale, formatting, validation, and auth
  state belong in their dedicated `lib` or provider modules.
- Prefer relative API paths everywhere browser code executes. The API origin is
  a server/container concern. Never add `NEXT_PUBLIC_` values for sessions,
  credentials, or internal service hostnames.
- Preserve Phase 6's neutral backend errors as machine codes only. Translate
  UI copy via the locale catalog and avoid reporting raw bodies, credentials,
  cookies, or response internals.
- Do not mark Phase 7 `(DONE)` in `specs/roadmap.md` or update
  `specs/progress.md` until all implementation and validation work above has
  succeeded. At implementation completion, update both consistently and report
  the exact checks run, real endpoint integration evidence, and any narrow
  compatibility assumption.
