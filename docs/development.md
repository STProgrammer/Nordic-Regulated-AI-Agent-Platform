# Developer guide

This guide describes the current local workflow for the Nordic Regulated AI Agent Platform. It is
for development, review, and synthetic demonstrations only; it is not a production deployment
runbook. For the architecture, start with the [architecture summary](architecture-summary.md). For
the exact cloud boundary, see [deployment readiness and data modes](deployment-readiness.md).

## Prerequisites and installation

Install Node.js 24.x, pnpm 11.8.x, Python 3.12, uv 0.11.x, and Docker Engine or Docker Desktop with
Compose v2. From the repository root:

```bash
pnpm install --frozen-lockfile
uv sync --all-packages --locked
```

Use pnpm and uv as the only package-management workflows. Do not add npm, Yarn, Poetry, pipenv, or
another lockfile without an architectural decision.

## Local stack and clean-data mode

The standard Compose stack runs the Next.js web application, FastAPI API, Celery worker,
PostgreSQL/pgvector, Redis, Azurite, and the one-shot blob-container initializer. Published ports
bind to `127.0.0.1`; the worker has no public port.

```bash
pnpm dev:up
docker compose --env-file .env.example exec api alembic -c apps/api/alembic.ini upgrade head
docker compose --env-file .env.example exec api python scripts/check_migrations.py
docker compose --env-file .env.example exec api python scripts/check_clean_deployment_mode.py
pnpm verify:local-stack
```

Normal startup does not migrate or seed. The clean/deployment-ready local baseline is a migrated
database with no organizations, identities, cases, documents, workflow history, approvals, audit
history, evaluation data, or memory data. `check_clean_deployment_mode.py` is meaningful only before
an explicit fixture or demo seed is loaded.

Useful local endpoints:

| Surface           | URL                                |
| ----------------- | ---------------------------------- |
| Web application   | http://127.0.0.1:3000/             |
| Swagger / OpenAPI | http://127.0.0.1:8000/docs         |
| API liveness      | http://127.0.0.1:8000/health/live  |
| API readiness     | http://127.0.0.1:8000/health/ready |

The web application redirects to Bokmål (`/nb`) by default, supports English at `/en`, and proxies
browser requests through same-origin `/api/...`. Session identifiers remain opaque HTTP-only
cookies; the frontend does not read, store, or create them. For host-only web development while the
API is available locally:

```bash
API_ORIGIN=http://127.0.0.1:8000 pnpm --filter @nordic-regulated-ai-agent-platform/web dev
```

Normal shutdown retains local volumes:

```bash
pnpm dev:down
```

The following command removes this project's local PostgreSQL, Redis, and Azurite volumes. Use it
only when discarding all local data is intended:

```bash
pnpm dev:reset
```

## Explicit synthetic fixtures and demo mode

Synthetic data is opt-in. Never use personal data, customer documents, real credentials, or
production connection values. For basic local identities, provide a password only through the
current shell and seed the disposable stack explicitly:

```bash
read -r -s NORDIC_LOCAL_SEED_PASSWORD
export NORDIC_LOCAL_SEED_PASSWORD
docker compose --env-file .env.example exec -e NORDIC_LOCAL_SEED_PASSWORD api \
  python scripts/seed_local.py --password-env NORDIC_LOCAL_SEED_PASSWORD
```

The seed creates only synthetic `demo.invalid` identities and safe local fixtures. Unset the
variable when finished:

```bash
unset NORDIC_LOCAL_SEED_PASSWORD
```

For the portfolio scenario, follow the exact preparation, role handoff, and cleanup steps in the
[Bokmål local demo and video guide](local-demo-video-guide.md). It uses explicit deterministic local
providers only to demonstrate plumbing and citations; it does not make a hosted-model or retrieval-
quality claim.

## Product surface

The authenticated application includes case inbox/detail workflows, document metadata and
governance, retrieval/evidence views, workflow traces, human approvals, audit views, evaluation
results, and administrator controls including controlled memory. The API owns all authorization,
organization isolation, state transitions, provider selection, and server limits. Swagger is the
current detailed operation contract.

Security and governance boundaries include:

- tenant-scoped RBAC and a separation of duties for high-risk approvals;
- private raw document storage and bounded, governed source context;
- cited retrieval/drafting paths with evidence-sufficiency gates;
- content-minimized audit, trace, and logging projections; and
- deterministic evaluation and local-only test providers without external AI credentials in CI.

Read [security.md](security.md), [ai-evaluation.md](ai-evaluation.md), and
[architecture-summary.md](architecture-summary.md) for the corresponding detail.

## Validation workflows

### Fast repository checks

Run these after typical code or documentation changes:

```bash
pnpm check:workspace
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test:web
pnpm test:api
uv run python scripts/check_documentation_links.py
```

`pnpm test:web` runs the deterministic Vitest/Testing Library suite. `pnpm test:api` runs the full
backend test suite, including API and integration coverage where Docker/Testcontainers are
available. The link checker validates repository-relative Markdown files and heading fragments in
reviewer-facing documentation.

### Deterministic evaluation and security checks

These checks do not require an external model credential:

```bash
uv run python scripts/run_evals.py --dataset nordic-regulated-core-v1 --check
pnpm security:check
```

The evaluation suite checks fixed synthetic behavior, not semantic answer quality or hosted-provider
performance. Security checks scan code and dependencies and verify the reviewed secret baseline.

### Browser and production-image validation

Browser tests need a migrated, explicitly seeded local stack, deterministic local providers, and a
synthetic password in the current shell. Install the project-managed browser once, then use the
environment setup documented in the [local demo guide](local-demo-video-guide.md):

```bash
pnpm --filter @nordic-regulated-ai-agent-platform/web exec playwright install --with-deps chromium
pnpm test:e2e
```

Browser tests retain no normal screenshot, video, or trace artifacts. If a focused browser test
fails twice after one relevant fix, stop and diagnose the concrete blocker rather than repeatedly
rerunning the suite.

Validate the credential-free production-image contract separately:

```bash
pnpm release:build
pnpm release:validate
```

This builds non-root production images, starts an isolated local Compose stack, applies migrations,
checks clean runtime data, health probes, and the same-origin API proxy, then removes the temporary
stack. It does not publish images or provision cloud infrastructure.

## Troubleshooting

- Check service state with `docker compose --env-file .env.example ps`.
- Follow safe local logs with `pnpm dev:logs`; do not copy secrets or personal data into issue
  reports.
- Re-run `pnpm verify:local-stack` only against an already-running stack; it does not create
  business data, migrate, dispatch work, or call external providers.
- If migration state is unexpected, use `scripts/check_migrations.py` before considering a reset.
- If a disposable demo leaves data behind, use `pnpm dev:reset` and restart the clean-data workflow.

## Deployment and data safety

The repository has local production-image validation and deployment configuration contracts, but no
Azure deployment. Azure Container Apps is the preferred planned target, with PostgreSQL, Blob
Storage, Key Vault, Container Registry, monitoring, HTTPS, backups, controlled migrations, and smoke
tests. Treat [deployment readiness and data modes](deployment-readiness.md) as the authoritative
status document.

Keep credentials in ignored local files, CI secret stores, or a deployed secret manager. The tracked
`.env.example` contains only intentionally public local-emulator values. Follow the
[sample-data safety policy](../sample-data/README.md) for every fixture, screenshot, log excerpt, or
demo artifact.
