# Deployment readiness and data modes

## Current status

The repository is deployment-ready in the limited sense that it has validated production images,
environment configuration contracts, migration checks, health endpoints, and a clean-data release
gate. It is **not** deployed to Azure: no Azure resources, registry images, domains, credentials, or
production data are provisioned by this version.

## Clean/deployment-ready mode

Migration-only startup is the default. It never seeds runtime data. A clean database has zero rows
in all application-data tables, including identities, prompts, cases, documents, workflow/audit
history, approvals, evaluation data, and memory data.

For a deterministic local proof, use the disposable local stack:

```bash
pnpm dev:reset
pnpm dev:up
docker compose --env-file .env.example exec api alembic -c apps/api/alembic.ini upgrade head
docker compose --env-file .env.example exec api python scripts/check_migrations.py
docker compose --env-file .env.example exec api python scripts/check_clean_deployment_mode.py
pnpm verify:local-stack
pnpm dev:down
```

`pnpm dev:reset` deletes this Compose project's PostgreSQL, Redis, and Azurite volumes. Use it only
when removing local data is intended. Initial administrator provisioning and operational data setup
are deployment-runbook responsibilities; no default account, password, or demo tenant is packaged.

## Explicit demo and test mode

`scripts/seed_local.py`, E2E fixture scripts, and `scripts/seed_phase34_demo.py` remain available
for local/test use only. They are never invoked by Compose startup, migrations, production image
startup, or release validation. The Phase 34 demo guide requires `pnpm dev:reset` after recording so
the synthetic case, document, workflow, approval, audit history, and evaluation run cannot persist
into normal local use.

Repository fixtures, safe sample files, automated tests, and documentation remain tracked. They do
not create runtime records until an explicit command or test invokes them.

## Planned Azure deployment path

Azure Container Apps is the primary planned target for the web, API, and worker containers; App
Service for Containers remains an acceptable later alternative where its operational model fits. The
intended deployment uses Azure Container Registry, Azure Database for PostgreSQL, Azure Blob
Storage, Azure Key Vault, Application Insights/Azure Monitor, and Azure Cache for Redis where the
session and rate-limit workloads require it.

A later deployment implementation will use managed identities and Key Vault references, build and
push immutable images to ACR, run migrations as a controlled one-shot operation without any seed,
configure HTTPS and health probes, enable database backups plus restore testing, and run
post-release smoke tests. CI/CD secret values, database URLs, storage keys, model credentials, and
production administrator credentials must stay outside the repository and be injected by the target
platform.

This is an operational plan, not a claim that cloud deployment has occurred.
