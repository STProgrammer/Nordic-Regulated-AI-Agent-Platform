# Nordic Regulated AI Agent Platform

Production-style AI workflow software for Norwegian organizations with regulated, document-heavy
work. The platform combines source-governed document handling, RAG with citations, LangGraph
workflows, human approval, auditability, deterministic evaluation, and Norwegian Bokmål as the
default interface language.

> **Video walkthrough:** Watch the [silent product demo on YouTube](https://youtu.be/K7mHEu7hxpg).
> It uses synthetic local data and shows the English interface; the application also supports
> Norwegian Bokmål.

> **Deployment status:** the repository is locally validated and deployment-ready by design. It has
> no public cloud deployment, Azure resources, registry-published images, domain, or live
> application URL.
> See [deployment readiness and data modes](docs/deployment-readiness.md) for the exact boundary.

## What this demonstrates

- Secure, organization-scoped case and document workflows with server-enforced RBAC.
- Private object storage, asynchronous parsing/indexing, governed retrieval, and cited answers.
- Inspectable LangGraph intake, evidence, extraction, drafting, and risk/compliance workflows.
- Human approval for high-risk work, with separate AI drafts, human decisions, and audit history.
- Deterministic evaluation, cost/latency observability, accessibility-conscious Bokmål/English UI,
  CI quality gates, and credential-free production-image validation.

The project is intentionally an enterprise workflow system, not a generic chatbot or a "chat with
PDF" demo. It is designed to make the engineering and governance trade-offs visible to reviewers.

## Architecture at a glance

The runtime consists of a Next.js web application, FastAPI API, Celery worker, PostgreSQL with
pgvector, Redis, and Azure Blob-compatible object storage through Azurite locally. The browser uses
same-origin `/api/...` requests; opaque HTTP-only sessions and authorization remain server-owned.

Read the [architecture summary](docs/architecture-summary.md) for the component diagram and trusted
data flow, the [canonical architecture](specs/architecture.md) for detailed decisions, and the
[ADRs](docs/adr/README.md) for the durable choices behind the design.

## Quick local start

Prerequisites: Node.js 24.x, pnpm 11.8.x, Python 3.12, uv 0.11.x, and Docker Engine/Desktop with
Compose v2.

```bash
pnpm install --frozen-lockfile
uv sync --all-packages --locked
pnpm dev:up
docker compose --env-file .env.example exec api alembic -c apps/api/alembic.ini upgrade head
pnpm verify:local-stack
```

Open these local-only endpoints:

| Surface           | URL                                |
| ----------------- | ---------------------------------- |
| Web application   | http://127.0.0.1:3000/             |
| OpenAPI / Swagger | http://127.0.0.1:8000/docs         |
| API readiness     | http://127.0.0.1:8000/health/ready |

Startup does not migrate or seed data. The normal baseline is a migrated database with no
application data. Use the [developer guide](docs/development.md) for the clean-data check, synthetic
local fixtures, shutdown/reset guidance, and host-only web development.

## Safe local demo

The [Bokmål local demo and video guide](docs/local-demo-video-guide.md) provides a reproducible
one-minute walkthrough of login, case/document review, evidence, a cited RAG answer, workflow trace,
human approval, audit history, and evaluation results. It uses only explicit, synthetic
`demo.invalid` accounts and data. The guide also explains which steps are pre-seeded and which run
live in the local stack.

## Test and validation commands

Run the normal repository checks after installing dependencies:

```bash
pnpm check:workspace
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test:web
pnpm test:api
uv run python scripts/check_documentation_links.py
```

The focused browser journey and production-image checks have explicit local prerequisites; follow
the [developer guide](docs/development.md#validation-workflows) rather than running them against
personal data or credentials. CI runs deterministic providers only and does not call external AI
services. See [CI documentation](docs/ci.md) and
[deterministic AI evaluation](docs/ai-evaluation.md) for the exact quality boundary.

## Production-image and cloud status

Credential-free local production images for the web, API, and worker are built and verified with:

```bash
pnpm release:build
pnpm release:validate
```

That validation checks container behavior, explicit migrations, clean runtime data, health probes,
and the same-origin API proxy. It does **not** provision or deploy Azure infrastructure. The planned
path is Azure Container Apps (or App Service for Containers), PostgreSQL, Blob Storage, Key Vault,
Container Registry, monitoring, HTTPS, backups, migrations, and smoke tests. It remains a plan, not
a completed deployment.

## Screenshots

No static screenshots, placeholders, or video assets are committed yet. The synthetic local demo
guide is the current presentation path and is designed to let a reviewer reproduce the relevant UI
safely on their own machine.

## Documentation

- [Developer guide](docs/development.md)
- [Architecture summary](docs/architecture-summary.md)
- [Deployment readiness and data modes](docs/deployment-readiness.md)
- [Local demo and video guide (Bokmål)](docs/local-demo-video-guide.md)
- [Security guide](docs/security.md) and [security policy](SECURITY.md)
- [CI guide](docs/ci.md) and [deterministic evaluation guide](docs/ai-evaluation.md)
- [Product requirements](specs/PRD.md), [architecture](specs/architecture.md), and
  [roadmap](specs/roadmap.md)

## Current limitations

- The system is not publicly deployed; cloud infrastructure, registry publishing, and operational
  production runbooks are planned work.
- Public/demo material must remain synthetic, public, anonymized, or otherwise demonstrably safe.
- Deterministic local providers validate workflow plumbing and regression behavior; they do not make
  quality, semantic-retrieval, or hosted-model claims.
- File validation is defense in depth, not malware scanning. A deployment that accepts untrusted
  production documents needs a malware-scanning integration.
- No license has been selected. The project owner must choose one before asserting public reuse
  terms.

## Repository layout

```text
apps/          FastAPI API and Next.js web application
services/      Agent orchestration, retrieval, document, and evaluation services
docs/          Operational guides, architecture summary, and ADRs
infra/         Docker and planned cloud-boundary configuration
sample-data/   Safety policy plus synthetic-only fixtures
scripts/       Repository and operational validation helpers
specs/         Canonical product, architecture, roadmap, and progress records
phases/        Historical implementation plans
```
