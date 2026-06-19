# Phase 1 — Repository and Workspace Foundation

## Phase objective

Create the durable monorepo foundation for the Nordic Regulated AI Agent Platform. The result of this phase is a clean, documented, tool-validated workspace with clear ownership boundaries for the web application, API, AI-oriented services, shared schemas, infrastructure, documentation, scripts, and safe sample data.

This phase establishes project conventions and architectural decisions. It does **not** implement a runnable product, Docker environment, API, database, frontend, or AI workflow.

## How this phase fits the product

The final product is a Norwegian Bokmål-first, regulated-workflow platform whose AI actions must be source-grounded, auditable, privacy-aware, and subject to human approval. That requires a repository that can grow without mixing business logic, AI orchestration, infrastructure, or public demo data.

The architecture defines a Next.js/TypeScript frontend, a FastAPI/Python API, separate agent-orchestration, retrieval, document-processing, and evaluation boundaries, PostgreSQL with pgvector, Redis-backed workers, Docker, GitHub Actions, and Azure deployment. Phase 1 creates the workspace and configuration boundaries for those choices; later phases introduce their runtime behavior in roadmap order.

## Relevant constraints from the specifications

- Default user-facing language will be Norwegian Bokmål, with English available later. Documentation and identifiers may remain English, but sample-data guidance must call out safe Norwegian demo content.
- The platform is an enterprise workflow system, not a generic chat demo. Keep the repository structure suitable for typed APIs, source-grounded retrieval, LangGraph workflow traces, approval controls, auditability, evaluation, and deployment.
- Python targets version 3.12 and must use type hints, Pydantic at system boundaries, Ruff, and mypy. TypeScript must use strict mode, ESLint, and Prettier.
- PostgreSQL with pgvector is the default data and vector-search direction. Qdrant and OpenSearch are optional later additions, not baseline dependencies in this phase.
- Azure Container Apps is the default cloud target; AKS is only an optional future path. Do not add cloud resources or deployment code in this phase.
- The public demo must use only synthetic, public, anonymized, or otherwise safe data. No credentials, real personal data, or secret-bearing configuration may enter the repository.
- Phase 1 validation is explicitly limited to a workspace structure review plus successful format, lint, and type-check commands on an empty workspace.

## In scope

1. A tracked monorepo directory layout matching the architectural boundaries.
2. Root workspace manifests and developer-tool configuration for Python and TypeScript quality checks.
3. Initial package metadata and empty package/module boundaries where needed to make the workspace topology explicit.
4. Repository hygiene and editor-consistency files, including ignores, line-ending rules, and an example environment file containing no secrets.
5. A concise root README and workspace/developer guidance that accurately describes the current foundation without claiming unimplemented features.
6. Four accepted Architecture Decision Records (ADRs): architecture style, LangGraph workflows, PostgreSQL with pgvector, and Azure deployment target.
7. A small, deterministic workspace-structure validation script or equivalent checked-in validation command.
8. A safe-data policy/readme for `sample-data/` and placeholders for the required business domains and future evaluation data.

## Out of scope

- Dockerfiles, Docker Compose, container builds, local services, health endpoints, or real environment wiring (Phase 2).
- FastAPI application code, API routes, OpenAPI output, logging implementation, workers, or error models (Phase 3).
- Database models, migrations, seed records, or database connectivity (Phase 4).
- Next.js initialization, UI components, API client, routing, authentication UI, or localization implementation (Phase 7).
- LangGraph code, model-provider code, LangMem, RAG, document parsing, embeddings, vector search, background jobs, or evaluation execution (Phases 10–27).
- CI workflows, dependency/security scanning, container scanning, cloud infrastructure definitions, staging, or production deployment (Phases 29–35).
- Real customer, citizen, employee, credential, or other sensitive material in documentation, samples, or configuration.
- A legal licence selection without an explicit project-owner decision. Do not invent a licence text; record the unresolved choice in the README if it has not been supplied.

## Target repository layout

Create and track the following boundaries. Empty folders should be kept intentionally (for example, with a narrowly placed `.gitkeep` or a local README) so a fresh clone communicates the intended architecture.

```text
.
├── apps/
│   ├── api/                         # Future FastAPI application (Phase 3)
│   └── web/                         # Future Next.js application (Phase 7)
├── services/
│   ├── agent_orchestrator/          # Future LangGraph and approval workflows
│   ├── retrieval/                   # Future hybrid retrieval boundary
│   ├── document_processor/          # Future secure parsing/indexing boundary
│   └── evaluation/                  # Future deterministic and quality evaluation
├── packages/
│   └── shared_schemas/              # Future cross-service Python schemas
├── docs/
│   └── adr/
├── infra/
│   ├── azure/                       # Future Bicep/Terraform location
│   ├── docker/                      # Future service Dockerfiles
│   └── github-actions/              # Future workflow definitions/documentation
├── sample-data/
│   ├── public-sector/
│   ├── banking/
│   ├── energy/
│   ├── internal-policy/
│   └── evaluation/
├── scripts/
├── phases/
└── specs/
```

Within the future Python workspaces, establish the expected `src/`, test, and module-boundary folders without adding business behavior. The intended later locations are:

- `apps/api/src/app/{api,core,db,services,workers}` and `apps/api/tests/{unit,integration,api,contract}`;
- `services/agent_orchestrator/src/agent_orchestrator/{graphs,state,nodes,tools,memory,prompts,model_providers}` and its `tests/{unit,graph,regression}`;
- `services/retrieval/src/retrieval/{chunking,embeddings,hybrid_search,reranking,citations,evaluation}`;
- `services/document_processor/src/document_processor/{parsers,validators,metadata,pii}`;
- `services/evaluation/src/evaluation/{datasets,metrics,runners,reports}`; and
- `packages/shared_schemas/src/shared_schemas/`.

Do not create named route, graph, model, database, parser, or UI implementation files merely as empty promises. Create only package markers and directories necessary for a valid workspace; later phases own functional modules.

## Likely files and folders affected

### Root configuration and repository hygiene

- `README.md`
- `CONTRIBUTING.md` or `docs/development.md`
- `.gitignore`
- `.gitattributes`
- `.editorconfig`
- `.env.example`
- `package.json`
- `pnpm-workspace.yaml` (if pnpm is selected for the JavaScript workspace)
- `tsconfig.base.json`
- `eslint.config.mjs`
- `.prettierrc.json` and `.prettierignore`
- `pyproject.toml`
- `uv.lock` (if uv is selected and available)
- `.pre-commit-config.yaml` only if its hooks can be installed and run deterministically in the documented toolchain

### Workspace metadata and structural markers

- `apps/web/package.json` as an empty workspace package only; do not add Next.js configuration or application code.
- Python workspace metadata for `apps/api`, each service, and `packages/shared_schemas`, coordinated from the root Python workspace configuration.
- Minimal package markers and tracked directory markers needed for `src/` and test trees.
- `scripts/check_workspace_structure.sh` (or a documented equivalent) to verify required paths and baseline files.

### Documentation and architectural decisions

- `docs/adr/0001-architecture-style.md`
- `docs/adr/0002-langgraph-for-agent-workflows.md`
- `docs/adr/0003-postgresql-and-pgvector.md`
- `docs/adr/0004-azure-deployment-target.md`
- `docs/README.md` or equivalent documentation index
- `sample-data/README.md`
- Local README files in intentionally empty infrastructure/script folders only where they clarify ownership and future phase boundaries.

## Implementation tasks

### 1. Inspect and preserve the starting state

1. Read the current `AGENTS.md`, PRD, architecture, roadmap, and this phase plan before changing files.
2. Inspect existing files and uncommitted changes. Preserve user-owned content and do not overwrite any existing phase plan or configuration without reviewing its intent.
3. Confirm the repository is currently a foundation-only workspace. If an existing implementation is discovered, reconcile the plan with it rather than deleting or replacing working code.

### 2. Establish the monorepo topology

1. Create the `apps`, `services`, `packages`, `docs`, `infra`, `sample-data`, and `scripts` boundaries listed above.
2. Add tracked placeholders only where Git would otherwise omit an essential empty directory. Prefer a scoped README over a broad collection of unexplained placeholder files.
3. Create empty Python `src` package roots and tests directories that express the architecture's future ownership boundaries. A package marker is acceptable; it must contain no runtime behavior.
4. Add a minimal workspace manifest for every future deployable Python component and shared Python package. Use unique, predictable distribution names and Python 3.12 compatibility. Do not introduce application dependencies such as FastAPI, LangGraph, SQLAlchemy, Celery, or document parsers yet; those belong to their implementation phases.
5. Add a minimal web workspace package manifest only to make the JavaScript workspace explicit. Do not initialize a Next.js application until Phase 7.

### 3. Configure deterministic developer tooling

1. Select one JavaScript workspace/package manager and one Python package/environment manager, record the choice and required version in the README, and avoid duplicate lockfiles or competing configuration systems. Recommended baseline: pnpm for JavaScript workspaces and uv for Python 3.12 workspaces.
2. Add a root TypeScript base configuration with `strict: true`, modern module settings suitable for a later Next.js app, and no application-specific aliases until the web app exists.
3. Add a flat ESLint configuration and Prettier configuration that cover tracked JavaScript/TypeScript/configuration files while excluding generated files, virtual environments, dependencies, coverage output, and future build artifacts.
4. Add Python tooling configuration for Ruff formatting/linting and mypy. Require Python 3.12, enable a strict or near-strict baseline appropriate for new typed packages, and target only the established Python source roots so empty workspaces pass without suppressing future code defects.
5. Provide root scripts with clear, stable names, at minimum:

   - `format` and `format:check`;
   - `lint`;
   - `typecheck`; and
   - `check:workspace`.

   If language-specific commands are clearer, expose both grouped commands (for example, `lint:python`, `lint:web`) and a root aggregate command. Aggregate commands must return a non-zero status if a constituent check fails.
6. Do not add test frameworks merely to produce an empty test run. The Phase 1 test requirement is a deterministic topology check plus format/lint/type-check validation. Introduce pytest, Vitest, and Playwright configurations with their respective implementation phases unless their addition is necessary for the selected tooling to function.

### 4. Add safe configuration, Git hygiene, and editor consistency

1. Create `.gitignore` covering local `.env` files while preserving `.env.example`, Python virtual environments and caches, Node dependencies and build output, coverage, logs, OS/editor artifacts, local object-storage data, and Terraform state/override files. Never ignore source, ADRs, lockfiles, or safe sample-data documentation by default.
2. Add `.gitattributes` and `.editorconfig` to standardize UTF-8, LF line endings, final newlines, indentation, and Markdown/YAML/JSON formatting expectations across operating systems and editors.
3. Add `.env.example` with only non-secret safe defaults or explanatory placeholders. At this phase, it must not imply that Docker services already exist. State that Phase 2 will add service-specific local variables.
4. Document a simple rule: real `.env` files, credentials, tokens, connection strings, production values, and personal data are never committed. Keep all placeholders visibly non-production.
5. If pre-commit hooks are added, configure only hooks that are available through the documented package managers and include an explicit non-interactive run command in the developer guide. Do not make the phase dependent on an undocumented globally installed tool.

### 5. Create truthful repository documentation

1. Add a concise root README that:

   - identifies the product as a planned, production-style Norwegian regulated AI workflow platform;
   - describes the current Phase 1 status honestly as workspace foundation only;
   - shows the top-level repository map;
   - records the selected Node/Python toolchain and quality commands;
   - links to `specs/`, the current phase plan, and ADR index;
   - states the synthetic/safe-data-only rule; and
   - avoids claiming an API, UI, Docker stack, authentication, RAG, or deployed demo exists.

2. Add contributor/developer guidance with supported runtime versions, dependency-install commands, commands for formatting/linting/type checking, and the rule that architecture-impacting changes require an ADR or ADR update.
3. Add a documentation index that distinguishes source-of-truth specifications in `specs/` from implementation documentation that will be added in later phases. Do not duplicate the PRD or architecture files into `docs/` at this stage; duplication would create drift.
4. Add `sample-data/README.md` that makes the safety policy practical: only synthetic/public/anonymized data, no real PII, no secrets, no customer documents, and no deceptive demo claims. Briefly describe the future domain folders without adding example cases yet.
5. If no licence decision exists, say so plainly in the README as a release/documentation follow-up. Do not add fabricated legal language.

### 6. Record the initial ADRs

Use a consistent ADR template with: title, status (`Accepted`), date, context, decision, consequences, alternatives considered, and links to the architecture/roadmap sections that motivated it.

1. **ADR 0001 — Architecture style**
   - Decide on a modular monorepo with explicit frontend, API, AI-service, shared-schema, infrastructure, and documentation boundaries.
   - Record that the repository expresses service boundaries without forcing premature network-distributed services. Explain that later deployment topology follows proven needs and roadmap phases.
   - Capture the benefit (maintainability, testing, clear ownership) and cost (cross-workspace dependency discipline).

2. **ADR 0002 — LangGraph for agent workflows**
   - Decide that future agent workflows use LangGraph with typed Pydantic state, explicit nodes and transitions, persisted workflow state, and human-approval interrupts.
   - Record why this supports inspectability, audit trails, deterministic tests, and regulated workflow requirements.
   - Explicitly limit LangMem to later, controlled, organization-scoped, auditable, non-sensitive use cases.

3. **ADR 0003 — PostgreSQL with pgvector**
   - Decide that PostgreSQL is the system of record and pgvector is the default semantic-search store, with PostgreSQL full-text/keyword capabilities supporting hybrid retrieval.
   - Record that Qdrant/OpenSearch remain optional, evidence-driven additions rather than Phase 1 dependencies.
   - Note the expected benefits (operational simplicity and strong relational governance) and trade-off (future dedicated search scale may require reevaluation).

4. **ADR 0004 — Azure deployment target**
   - Decide on Azure as the target cloud, with Azure Container Apps preferred ahead of AKS, backed by Azure Database for PostgreSQL, Blob Storage, Key Vault, Container Registry, and monitoring services.
   - Explain Norwegian enterprise/public-sector relevance and the deliberate avoidance of premature Kubernetes complexity.
   - Record that infrastructure-as-code and deployments are deferred to Phases 33–35.

### 7. Add the Phase 1 workspace-contract check

1. Add a small, dependency-free, non-destructive check under `scripts/` (shell or Python is acceptable) that verifies the required top-level workspace boundaries, root hygiene/configuration files, workspace manifests, documentation index, sample-data safety guide, and four ADRs exist.
2. The check must provide actionable missing-path messages and exit non-zero on failure.
3. It must not inspect secret contents, call external services, create files, or require Docker, a database, Node dependencies, or a network connection.
4. Wire it into the documented root `check:workspace` command (or document exactly how the aggregate command invokes it).

### 8. Keep the foundation reviewable

1. Keep configuration focused; avoid speculative dependencies and empty application modules.
2. Ensure all documentation links resolve from a fresh clone.
3. Review the final diff for secrets, accidental generated files, machine-specific paths, and claims about unimplemented features.
4. Do not mark Phase 1 as done in `specs/roadmap.md` until every validation below passes.

## Required tests and validation

Phase 1 has no business behavior to unit-test. Its required checks are the repository-contract smoke test and successful static-tool execution against the empty workspace.

Run the following from a clean checkout after installing the documented Node and Python development dependencies:

1. **Workspace contract check**

   ```bash
   ./scripts/check_workspace_structure.sh
   ```

   If a Python implementation is selected instead, document and run its equivalent command. Verify it reports each required path or fails with a clear list of missing paths.

2. **Formatting check**

   ```bash
   pnpm format:check
   uv run ruff format --check apps services packages scripts
   ```

   Equivalent documented aggregate commands are acceptable, but both Markdown/configuration formatting and Python formatting must be checked.

3. **Lint check**

   ```bash
   pnpm lint
   uv run ruff check apps services packages scripts
   ```

   The commands must complete successfully without relying on a globally installed formatter or linter.

4. **Type-check check**

   ```bash
   pnpm typecheck
   uv run mypy apps services packages scripts
   ```

   Empty package roots are acceptable in Phase 1; do not hide future type failures behind broad excludes or a blanket `ignore_errors` setting.

5. **Fresh-install reproducibility**

   - Remove only generated dependency/install artifacts (never tracked files) or use a clean clone.
   - Run the documented dependency installation commands.
   - Re-run the workspace, format, lint, and type-check commands successfully.
   - Confirm installing dependencies does not modify `.env.example`, create secret-bearing files, or generate untracked runtime data.

6. **Manual architecture review**

   - Compare the resulting directory layout with Architecture §12 and Phase 1 in the roadmap.
   - Read all four ADRs and verify they agree with Architecture §20.
   - Confirm that no Phase 2+ runtime asset has been introduced: no Compose file, Dockerfile, FastAPI app, Next.js app, migrations, CI workflow, or Azure resource definition.

## Completion criteria

Phase 1 is complete only when all of the following are true:

- The tracked repository layout includes the specified application, service, shared-package, infrastructure, documentation, scripts, and safe sample-data boundaries.
- The Python workspaces declare Python 3.12 compatibility and have coherent source/test locations; the web workspace is represented without prematurely creating the Next.js app.
- Exactly one documented primary workflow exists for installing/running JavaScript tooling and one for Python tooling; configuration is not duplicated or contradictory.
- Root format, lint, type-check, and workspace-contract commands are documented and pass from a fresh checkout.
- `.gitignore`, `.gitattributes`, `.editorconfig`, and `.env.example` exist, are internally consistent, and contain no secret or production credentials.
- The README and contributor/developer documentation accurately describe a Phase 1 foundation and link to the canonical specifications and ADRs.
- `sample-data/README.md` clearly prohibits real personal data, secrets, and unsafe document samples.
- ADRs 0001–0004 are accepted, use a consistent template, and match the chosen architecture: modular monorepo, LangGraph, PostgreSQL + pgvector, and Azure Container Apps-first deployment.
- The workspace-contract check is non-destructive, deterministic, and passes.
- No implementation work from later phases is present.
- All required validations pass and their command output/results are recorded in the implementation handoff.

## Risks and dependencies

| Risk or dependency | Impact | Required handling in this phase |
| --- | --- | --- |
| No agreed Node/Python package-manager versions | Tooling may be unreproducible across developers and CI. | Choose, pin/document supported versions, and keep a single lockfile strategy per ecosystem. |
| Tooling configuration becomes a de facto application scaffold | It can blur phase boundaries and make later work harder to review. | Configure quality tooling and manifests only; defer Next.js, FastAPI, Docker, and services to their assigned phases. |
| Empty directories disappear from Git | The intended architecture becomes invisible in a fresh clone. | Use minimal, meaningful tracked markers and verify them with the workspace-contract check. |
| Spec duplication drifts over time | PRD/architecture copies could become stale and misleading. | Keep `specs/` canonical; link from docs rather than copying them in Phase 1. |
| Placeholder configuration looks usable in production | Contributors could mistake examples for secure runtime settings. | Clearly label every placeholder, include no credentials, and defer service settings to Phase 2. |
| Unsafe public demo content is added early | It creates privacy and repository-safety risk. | Add and enforce the sample-data guidance before any actual demo data is introduced. |
| Licence choice is unknown | Adding the wrong legal terms is difficult to unwind. | Do not invent a licence; document the decision as a follow-up until the owner selects one. |

## Notes for the implementation agent

- Treat this as final-product groundwork, not a throwaway bootstrap. Names, package boundaries, scripts, and quality settings should remain useful through deployment.
- Prefer the simplest configuration that enforces the stated standards. A neat modular monorepo is more valuable here than a premature microservice runtime.
- Make all defaults truthful. The repository must never imply that authentication, AI safety, RAG, cloud deployment, or compliance controls are implemented when this phase only establishes their future homes.
- Keep command names and documentation stable because Phases 2, 3, 7, 16, and 31 will build on them.
- If an existing project convention conflicts with this plan, preserve the convention only when it still satisfies the PRD/architecture; document the deviation and rationale in the final implementation report.
- Before marking the phase done, update `specs/roadmap.md` to append `(DONE)` to the Phase 1 heading and update `specs/progress.md` only if that file exists, exactly as required by `AGENTS.md`.
