# Web application

This is the Phase 9 Case Management interface for the Nordic Regulated AI Agent Platform. It uses
strict TypeScript, Tailwind CSS, next-intl, TanStack Query, React Hook Form, Zod, Vitest, and
Testing Library.

The default user-facing locale is Norwegian Bokmål (`/nb`); English is available at `/en`. Protected
routes use only the Phase 6 auth API through relative `/api/...` requests. The backend issues and
validates the opaque HTTP-only cookie, so this application never reads, stores, decodes, or creates
a session identifier.

## Commands

From the repository root:

```bash
pnpm lint:web
pnpm typecheck:web
pnpm test:web
API_ORIGIN=http://127.0.0.1:8000 pnpm --filter @nordic-regulated-ai-agent-platform/web dev
```

For the full local stack, use `pnpm dev:up`; Docker Compose supplies the internal API origin. The
Case Inbox (`/{locale}/cases`), Case submission (`/{locale}/cases/new`), and Case Detail
(`/{locale}/cases/{caseId}`) use typed, same-origin API calls. Case Detail lists safe document
metadata and lifecycle state, supports backend-governed source-status/re-index actions where
permitted, and provides source search with explicit bounded-context opening. It does not offer
upload, download, preview, raw-text browsing, or AI answers. Workflow, extraction, risk, approval,
and audit sections remain honest placeholders; Approval, Evaluation, Administration, and Audit
routes remain placeholders.

## Browser smoke test

With the Compose stack migrated and local synthetic credentials provisioned, install Chromium once:

```bash
pnpm --filter @nordic-regulated-ai-agent-platform/web exec playwright install --with-deps chromium
```

Set `NORDIC_E2E_CASE_WORKER_EMAIL` to a synthetic seeded Case Worker and set the existing
`NORDIC_LOCAL_SEED_PASSWORD` in the shell without echoing it, then run `pnpm test:e2e` from the
repository root. The smoke suite fails clearly if either variable is missing and retains no browser
trace, video, or screenshot artifacts in normal runs.
