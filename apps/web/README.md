# Web application

The Next.js web application is the browser surface for the Nordic Regulated AI Agent Platform. It
uses strict TypeScript, Tailwind CSS, next-intl, TanStack Query, React Hook Form, Zod, Vitest, and
Testing Library.

Norwegian Bokmål (`/nb`) is the default locale; English is available at `/en`. Protected browser
requests use relative, same-origin `/api/...` routes. The API owns the opaque HTTP-only session,
organization scope, and RBAC policy, so this application never reads, stores, decodes, or issues a
session identifier.

## Current user surface

Authenticated users can work with cases, safe document metadata and governance, evidence/retrieval,
workflow traces, human approval, audit history, evaluation runs/results, and administrator controls
for users, roles, and controlled memory. Each screen receives only the bounded, role-authorized
projection supplied by the API; raw private documents, prompts, credentials, provider settings, and
unbounded workflow state remain server-side.

## Commands

From the repository root:

```bash
pnpm --filter @nordic-regulated-ai-agent-platform/web lint
pnpm --filter @nordic-regulated-ai-agent-platform/web typecheck
pnpm test:web
API_ORIGIN=http://127.0.0.1:8000 pnpm --filter @nordic-regulated-ai-agent-platform/web dev
```

For the full local stack, use `pnpm dev:up`; Compose provides the internal API origin. See the
[developer guide](../../docs/development.md) for migrations, fixture rules, and local URLs.

## Browser tests

The Playwright suite covers focused accessible user journeys across the implemented application. Run
it only against a migrated, explicitly seeded local stack with synthetic credentials and local test
providers:

```bash
pnpm --filter @nordic-regulated-ai-agent-platform/web exec playwright install --with-deps chromium
pnpm test:e2e
```

Follow the environment setup in the
[developer guide](../../docs/development.md#validation-workflows). The tests use synthetic data and
retain no browser screenshot, video, or trace artifacts in normal runs.
