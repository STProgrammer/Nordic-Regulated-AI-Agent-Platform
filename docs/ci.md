# Continuous integration

The repository runs the validation-only **CI** workflow for every pull request and every push to
`main`. It does not publish images, access GitHub Environments, use cloud credentials, or deploy
any service.

## Required checks

The workflow exposes these stable GitHub status checks:

| Status check | Validation |
| --- | --- |
| `Backend quality` | Ruff format/lint and strict mypy |
| `Backend unit tests` | API unit tests |
| `Backend integration tests` | PostgreSQL/pgvector Testcontainers integration tests |
| `API contract tests` | API and OpenAPI contract coverage |
| `Frontend quality` | Web lint and TypeScript check |
| `Frontend unit tests` | Vitest component/unit tests |
| `AI deterministic regression` | LangGraph/evaluation tests and canonical evaluation runner |
| `Security checks` | Bandit, locked Python audit, production Node audit, and secret scan |
| `Container build check` | Compose validation and development image builds |
| `Migration, OpenAPI, and browser smoke` | Compose migration/status, OpenAPI export, local-stack verification, and the approval Playwright smoke journey |

The last check uploads only the generated OpenAPI JSON as a seven-day CI artifact. It does not
track generated schemas in Git and does not upload application logs, browser traces, screenshots,
or videos.

## Provider and credential policy

CI sets the API embedding provider and non-container agent test provider to `deterministic`. The
Compose smoke test also receives the deterministic embedding provider. The workflow has no
`secrets.*` references, does not set an OpenAI or Azure credential, and does not make an external
model call. Its `NORDIC_LOCAL_SEED_PASSWORD` value is an ephemeral, synthetic fixture password;
it is not a user, production, or reusable credential.

The workflow has read-only repository permission. Image publishing, container scanning, registry
logins, GitHub Environments, cloud infrastructure, and deployments are intentionally deferred to
later phases.

## Main branch protection

A repository administrator should protect `main` in GitHub after the workflow has completed at
least once. Configure the following expectations:

1. Require a pull request before merging, with at least one approval.
2. Require every status check listed above, and require the branch to be current before merging.
3. Require conversation resolution before merging.
4. Prevent force pushes and branch deletion; do not permit bypasses for normal contributors.

These settings are documented rather than changed by the workflow, because branch rules are a
repository-administration decision.

## Local reproduction

Start from a clean checkout and use the locked dependency graphs:

```bash
pnpm install --frozen-lockfile
uv sync --all-packages --locked
```

Run the non-browser checks individually:

```bash
uv run ruff format --check apps services packages scripts
uv run ruff check apps services packages scripts
uv run mypy apps services packages scripts
uv run pytest apps/api/tests/unit
uv run pytest apps/api/tests/integration
uv run pytest apps/api/tests/api
pnpm --filter @nordic-regulated-ai-agent-platform/web lint
pnpm --filter @nordic-regulated-ai-agent-platform/web typecheck
pnpm test:web
uv run pytest services/agent_orchestrator/tests services/evaluation/tests
uv run python scripts/run_evals.py --dataset nordic-regulated-core-v1 --check
pnpm security:check
docker compose --env-file .env.example config --quiet
docker compose --env-file .env.example build web api worker
```

Run the migration, OpenAPI, and browser smoke check with local synthetic data only:

```bash
export NORDIC_API_EMBEDDING_PROVIDER=deterministic
export NORDIC_AGENT_ENVIRONMENT=test
export NORDIC_AGENT_PROVIDER=deterministic
export NORDIC_LOCAL_SEED_PASSWORD=ci-synthetic-password-not-a-secret

pnpm --filter @nordic-regulated-ai-agent-platform/web exec playwright install --with-deps chromium
pnpm dev:up
docker compose --env-file .env.example exec -T api alembic -c apps/api/alembic.ini upgrade head
docker compose --env-file .env.example exec -T api python scripts/check_migrations.py
curl --fail --silent --show-error http://127.0.0.1:8000/openapi.json >/tmp/openapi.json
uv run python -m json.tool /tmp/openapi.json >/dev/null
pnpm verify:local-stack
pnpm --filter @nordic-regulated-ai-agent-platform/web exec playwright test e2e/case-management.spec.ts
docker compose --env-file .env.example down --volumes --remove-orphans
unset NORDIC_API_EMBEDDING_PROVIDER NORDIC_AGENT_ENVIRONMENT NORDIC_AGENT_PROVIDER NORDIC_LOCAL_SEED_PASSWORD
```

If the focused browser smoke fails twice after one Phase 31 fix attempt, stop and report the
blocker instead of repeatedly rerunning it. A manual browser fallback requires explicit approval
before the phase can be marked complete.
