# Phase 4 — Database Foundation and Migrations

## Phase objective

Establish the production-quality PostgreSQL persistence foundation for the Nordic Regulated AI Agent Platform. Add typed SQLAlchemy 2 models, an Alembic migration baseline, safe database/session configuration, local seed data, and database integration tests for every entity required by the architecture.

The result is a clean, repeatable schema that supports multi-tenant cases, governed documents, later LangGraph traces, retrieval evidence, human approvals, auditability, model-cost records, evaluations, and controlled memory. It must be usable by later repository/service phases without needing a destructive schema redesign.

This is a persistence-foundation phase only. It does **not** add CRUD endpoints, repositories, business services, authentication, document ingestion, retrieval, worker jobs, LangGraph execution, or UI behavior.

## How this phase fits the final product

The PRD requires a secure organization-scoped platform where all material AI actions, source evidence, approvals, edits, evaluations, and audit events are retained and traceable. The architecture selects PostgreSQL 16 as the system of record and pgvector as the default vector store, with SQLAlchemy 2 and Alembic as the backend persistence tooling.

Phases 1–3 established the workspace, local Compose services (including `pgvector/pgvector` PostgreSQL), and a typed FastAPI application shell with operation-free route ownership. Phase 4 makes PostgreSQL a real application dependency and defines the durable storage contract. Phase 5 adds repositories/services and enforces organization scoping in data-access paths; Phase 6 adds authenticated identities and RBAC; later phases populate the tables through real case, document, retrieval, workflow, approval, evaluation, and memory features.

## Relevant specification context and constraints

- Use Python 3.12, SQLAlchemy 2, Alembic, asyncpg, PostgreSQL 16, and pgvector. Preserve the existing strict Ruff/mypy standards and the FastAPI factory/health contracts from Phase 3.
- PostgreSQL is the relational source of truth. Redis remains for future queues/locks/cache, and raw uploaded files remain in object storage; do not put raw files or blobs in relational tables.
- Use the architecture naming rules exactly: plural `snake_case` table names, UUID primary keys, `inserted_at`/`updated_at` timestamps, `organization_id` tenant keys where prescribed, and `archived_at` for soft archival where prescribed.
- All timestamps must be timezone-aware PostgreSQL `timestamptz`, generated consistently in UTC. Use server-side defaults where practical; `updated_at` must update predictably when a row changes.
- IDs must be database-generated UUIDs. Enable the PostgreSQL extension that supports the chosen UUID generation function. Do not generate identifiers from predictable case data.
- The architecture specifies text/jsonb-oriented storage for workflow state, model outputs, flexible metadata, risk reasons, evaluation expectations, and controlled memory. Preserve that flexibility with typed JSONB columns rather than prematurely encoding future graph/provider-specific schema.
- Use `numeric`/`Decimal` for scores and cost estimates; do not use binary floating point for persisted money-like values. Use `bigint` for file sizes and durations/token counts only where the architecture calls for integer values.
- Enforce referential integrity and the documented uniqueness/index requirements in the database. Default foreign-key deletion behavior must protect regulated evidence/history; do not introduce broad cascade deletes that erase audit, workflow, or approval history.
- Architecture §10 requires a vector index and a full-text index on document chunks. PostgreSQL full-text search is native; enable only extensions genuinely needed by the chosen schema (at minimum UUID support and `vector`; use `unaccent` only when the full-text expression depends on it). Do not add OpenSearch, Qdrant, or a retrieval service.
- The embedding dimension is not fixed by the PRD. For this baseline, make one explicit migration-time/configuration decision and document it: use `vector(1536)` as the local default (compatible with a common text-embedding model) and name the setting/constant clearly. Phase 12 must use a model with the same dimension or introduce a reviewed dimensional migration before changing it. Do not make a dimensionless vector column that cannot meet the required vector-index contract.
- Use a language-neutral, deterministic full-text representation for chunks (for example, `to_tsvector('simple', content)`) so both Norwegian Bokmål and English terms are retained. Query parsing/ranking behavior belongs to Phases 12–13.
- Audit rows are append-only application records: model them without mutable timestamps and do not expose mutation paths. Later repositories/RBAC enforce application-level access; do not invent an authentication system or a privileged retention workflow in this phase.
- The public/local demo data must be synthetic and safe. Never commit real personal data, real credentials, connection strings, access tokens, or model secrets. The existing local PostgreSQL/Azurite defaults are development-only convenience values, not deployable credentials.

## In-scope deliverables

1. A database package for engine/session lifecycle, declarative model base/mixins, PostgreSQL types, model registration, and test-friendly dependency seams.
2. SQLAlchemy 2 models and relationship mappings for all architecture §10 entities:
   - organizations, users, roles, user_roles;
   - cases;
   - documents, document_texts, document_chunks;
   - workflow_runs, workflow_node_runs, agent_messages, retrieved_sources, extracted_fields, risk_assessments, approvals;
   - audit_events, prompt_versions, model_usage_records;
   - eval_datasets, eval_cases, eval_runs, eval_results; and
   - memory_entries.
3. Alembic configuration and an initial, reviewed migration that adds the required PostgreSQL extensions, tables, constraints, foreign keys, indexes, vector index, and full-text index. The downgrade must reverse only objects added by this migration in dependency-safe order.
4. Safe, typed database configuration and asynchronous session/transaction construction for the API process. Configuration must support local Compose and tests without leaking the database URL/password into logs, errors, OpenAPI, or committed files.
5. An idempotent local seeding command that adds only safe synthetic organizations, the five required role records, and synthetic Norwegian demo identities/role assignments. It must not require a usable login flow or store plaintext passwords.
6. Database integration tests that add an empty PostgreSQL+pgvector database, run migrations, validate schema invariants/extensions/indexes, exercise representative persistence relationships, run the seed command, and verify downgrade/re-upgrade behavior.
7. Updated dependency lockfile, local development documentation, and migration/seed validation commands that accurately reflect the delivered database foundation.

## Out of scope

- Repository interfaces, service-layer CRUD, pagination/filtering/sorting helpers, organization-filtering queries, or audit-event helper APIs (Phase 5).
- Password hashing, login/logout/current-user flows, sessions/tokens, RBAC authorization, tenant authorization checks, separation-of-duties rules, or rate limiting (Phase 6).
- Real API operations in the existing route modules, request/response DTOs for domain entities, or frontend clients/UI.
- Case number allocation, status-transition rules, assignment behavior, case search, and case audit-event addition (Phase 8).
- File upload, blob-storage access, MIME validation, document parsing, chunk production, embeddings, re-indexing, or retrieval logic (Phases 10–13). This phase stores the future data shape only.
- LangGraph graphs/nodes, task queues, model/provider calls, prompt execution, risk calculation, approval behavior, LangMem integration, evaluation runner/dashboard, exports, observability metrics, or cloud deployment.
- Row-level security, production database roles, retention/deletion jobs, encryption-at-rest configuration, and database backup policy. Preserve data safely at schema level; the dedicated security/infrastructure phases own operational enforcement.
- New product data beyond the synthetic local seed fixture, or changes to roadmap/progress completion status. Do not mark Phase 4 done during planning or implementation until all validation passes.

## Likely files, folders, modules, and services affected

### API database and migration package

- `apps/api/pyproject.toml`
- `apps/api/alembic.ini`
- `apps/api/src/app/core/config.py`
- `apps/api/src/app/db/__init__.py`
- `apps/api/src/app/db/session.py`
- `apps/api/src/app/db/base.py` (or an equivalent explicit metadata/mixin module)
- `apps/api/src/app/db/models/__init__.py`
- `apps/api/src/app/db/models/organization.py`
- `apps/api/src/app/db/models/identity.py`
- `apps/api/src/app/db/models/case.py`
- `apps/api/src/app/db/models/document.py`
- `apps/api/src/app/db/models/workflow.py`
- `apps/api/src/app/db/models/audit.py`
- `apps/api/src/app/db/models/prompt.py`
- `apps/api/src/app/db/models/evaluation.py`
- `apps/api/src/app/db/models/memory.py`
- `apps/api/migrations/env.py`
- `apps/api/migrations/script.py.mako`
- `apps/api/migrations/versions/<revision>_database_foundation.py`

### Tests, local tooling, and documentation

- `apps/api/tests/unit/` for metadata/model configuration tests where no running database is required
- `apps/api/tests/integration/` for migration, schema, session, seed, and rollback tests
- `apps/api/tests/conftest.py` plus narrowly scoped test factories/fixtures as needed
- `scripts/seed_local.py`
- `scripts/check_migrations.py` if a small reusable migration checker is useful
- `pyproject.toml` and `uv.lock`
- `.env.example`, `docker-compose.yml`, and API Docker configuration only for safe database/migration command wiring needed by this phase
- `README.md` and `docs/development.md`

Keep models in the API persistence package. Do not add repositories/services, generic shared entity schemas, worker tasks, or service-owned database packages before their roadmap phases.

## Implementation tasks

### 1. Establish database dependencies and safe configuration

1. Add the minimum API dependencies needed for SQLAlchemy 2 ORM, Alembic, pgvector SQLAlchemy support, and PostgreSQL-backed integration testing. Keep existing FastAPI/health dependencies compatible and update `uv.lock` deliberately.
2. Extend the Phase 3 typed settings with a dedicated database settings surface. It must accept a PostgreSQL async URL for runtime sessions and derive/use a synchronous driver URL only inside Alembic tooling. Treat both URLs as sensitive values: never bind or serialize them to logs/errors/OpenAPI.
3. Support the current Compose service DNS (`postgres`) and local-only variables without hard-coding a production connection string. Document precedence and the exact non-secret setup steps. Do not read `.env.example` as runtime configuration.
4. Provide a single engine/sessionmaker construction path using SQLAlchemy async APIs and `asyncpg`, plus a request/session dependency that later services can reuse. It must be lazy/testable and must not open a database connection merely because the FastAPI app factory is imported.
5. Define explicit engine disposal/cleanup hooks for controlled process shutdown. Preserve the Phase 3 public health endpoints and worker readiness behavior; migrations/seeding must not become implicit startup side effects.

### 2. Define common SQLAlchemy conventions

1. Add one declarative metadata/base registry imported by Alembic. All model modules must be imported through one intentional registration point so autogeneration and tests see the complete schema.
2. Add reusable typed mixins/helpers for UUID IDs, UTC insertion/update timestamps, organization references where appropriate, and soft archival. Do not apply a mixin where architecture intentionally omits a field (for example, `roles`, `document_texts`, `workflow_node_runs`, `audit_events`, and evaluation result records have their explicitly specified timestamp shapes).
3. Use PostgreSQL-native types deliberately: `UUID`, `JSONB`, `INET`, `ARRAY(TEXT)`, timezone-aware timestamps, `NUMERIC`, and pgvector `Vector(1536)`. Keep identifier/status/provider/role fields as bounded text unless the architecture explicitly requires a database enum; application validation evolves in later feature phases.
4. Add explicit `ForeignKey`, `UniqueConstraint`, `CheckConstraint` only where they encode stated invariants, and named indexes/constraints so migrations and production diagnosis are stable. In particular, protect non-negative file sizes/tokens/durations/retries where applicable and constrain chunk indexes to non-negative values.
5. Use conservative `ondelete` behavior. Child data that has no regulatory value on its own may be tied to its owner only where the architecture makes that unambiguous; historical workflow, audit, approval, evaluation, and source-link records must not silently disappear through broad ORM/database cascades.

### 3. Implement the tenant, identity, and case model group

1. Implement `organizations` with unique slug, name, default language, JSONB retention policy/settings, timestamps, and nullable archival time.
2. Implement `users` with organization FK, architecture-specified unique email, display name, nullable password hash and identity-provider fields, preferred language, active flag, optional last login, and timestamps. Keep password material opaque and do not add authentication behavior.
3. Implement global `roles` and the tenant-aware `user_roles` association. Enforce the required composite uniqueness of `(user_id, role_id, organization_id)` and foreign keys so later RBAC cannot assign duplicates or cross-tenant membership accidentally.
4. Implement `cases` with all architecture fields, including organization, case number, title/description, language/domain/type, priority/status/risk, submitter/assignee, optional due date/external reference, timestamps, and soft archival. Enforce a unique `(organization_id, case_number)` identity and add the required tenant/status, tenant/risk, tenant/case-number, and tenant/insertion-time indexes.
5. Keep case status/risk/priority values as schema-supported text at this stage. Do not write transition state machines or generate case numbers yet.

### 4. Implement governed document, text, and retrieval-storage models

1. Implement `documents` with the required organization/case/uploader links; file identity, size/checksum/storage key; language/source/confidentiality/parsing fields; timestamps; and archival timestamp. Add required organization/case, organization/source-status, and checksum indexes.
2. Implement `document_texts` as extracted text plus JSONB extraction metadata and insertion timestamp. Make the document relationship one-to-one at the schema level so a parser reprocessing operation can update/replace deliberately in its owning phase rather than duplicate canonical document text.
3. Implement `document_chunks` with organization/document references, chunk index, page/section provenance, content, token count, metadata, `vector(1536)` embedding, and timestamps. Enforce unique `(document_id, chunk_index)` to preserve chunk identity.
4. In the initial migration, enable the required PostgreSQL extensions before adding dependent objects. Add a named pgvector approximate-nearest-neighbor index appropriate for cosine retrieval and a named GIN full-text index over the deterministic chunk-search expression. Choose index operations compatible with an initial empty-database migration; do not use `CONCURRENTLY` inside the transaction.
5. Do not populate extracted text/chunks/embeddings in this phase. The tables, source provenance, and indexes must simply be ready for Phases 11–13.

### 5. Implement workflow, AI-trace, risk, and approval model group

1. Implement `workflow_runs` with organization/case/initiator links, workflow name/version/status, lifecycle times/duration, aggregate tokens/cost, safe error summary, state snapshot JSONB, timestamps, and all required tenant indexes.
2. Implement `workflow_node_runs` with workflow-run link, node identity/status/timing, JSONB input/output summaries, safe error summary, retry count, and required indexes. Do not store credentials, raw prompt secrets, or unrestricted raw state in summary columns.
3. Implement `agent_messages`, `retrieved_sources`, and `extracted_fields` exactly as prescribed, including their organization/case/workflow/source links, structured JSONB payloads, prompt-version link, model accounting fields, citation data, confidence, and human-edited marker. Add the architecture-required retrieved-source indexes.
4. Implement `risk_assessments` and `approvals` with the complete booleans/decision/risk reason/editable draft/final text data shape required by the PRD. Preserve both AI draft and final human text as separate fields; do not implement approval decisions or separation-of-duties logic.
5. Use nullable foreign keys only where architecture says the relation can be absent. Any human-added/AI-added record must remain traceable to its organization and primary business case.

### 6. Implement audit, prompt/model, evaluation, and controlled-memory model group

1. Implement append-only `audit_events` with organization/optional actor/case, event/resource identifiers, optional `INET` IP, user agent, JSONB event data, and insertion time. Add the required tenant-time, tenant-event-type, and case indexes. Do not add update timestamps or an application mutation API.
2. Implement `prompt_versions` and `model_usage_records` with organization scoping/optionality exactly as architecture specifies, including active prompt state and provider/model/operation/tokens/cost/latency/safe failure summary data.
3. Implement `eval_datasets`, `eval_cases`, `eval_runs`, and `eval_results` with the specified global-or-organization optionality, JSONB expected behavior/source data, tags array, summary metrics, workflow link, deterministic scores/cost, pass/fail, and failure reasons. Do not add an evaluation runner or sample evaluation corpus yet.
4. Implement `memory_entries` with tenant/user scope, memory type/scope, JSONB content/source/active state, timestamps, optional archival time, and required tenant-scope and tenant-user indexes. It is a controlled-memory record only; do not connect LangMem or permit arbitrary sensitive content.
5. Confirm every model is importable without side effects and that relationship loading defaults avoid accidental large graph/document/audit loads.

### 7. Configure Alembic and write the baseline migration

1. Add Alembic configuration local to `apps/api`, with `env.py` obtaining metadata and safe database configuration from the application database settings rather than storing credentials in `alembic.ini`.
2. Generate the initial migration from reviewed metadata, then hand-review it. The migration must explicitly add extensions, tables, indexes, constraints, foreign keys, vector/full-text expressions, and any required server defaults; do not rely solely on an opaque autogenerated script.
3. Order upgrades by dependency: extensions and tenant/identity roots first; cases/documents/workflows next; dependent trace/audit/evaluation/memory tables and indexes afterwards. Name all objects consistently.
4. Implement `downgrade()` in exact reverse dependency order. It must remove schema objects and extensions only when safe for a fresh Phase 4 database; it must not drop a pre-existing extension owned outside this migration. Document the expected clean-local-database rollback use case.
5. Add a focused migration checker/command that can report current revision versus head and fail cleanly on a pending/unapplied migration without exposing a connection string.

### 8. Add safe, deterministic local seed data

1. Implement `scripts/seed_local.py` (or a narrowly scoped equivalent) as an explicit command, never an import-time side effect and never a Compose/API startup action.
2. Seed at least one synthetic Norwegian demo organization with `nb` as default/preferred language, safe retention/settings JSON, the five required global roles (`Admin`, `Compliance Reviewer`, `Case Worker`, `Manager`, `Read-only Auditor`), and synthetic Norwegian-named users linked to the relevant roles.
3. Add a separate clearly synthetic isolated organization/user only when needed to make tenant-isolation fixtures unambiguous. All names, emails, external references, and data must be demonstrably fake and non-personal.
4. Do not add a plaintext-password convention. Until Phase 6, use no password hash or a deliberately unusable synthetic identity marker; document that the seeded users are database fixtures, not functioning accounts.
5. Make seeding idempotent using stable natural keys (organization slug, role name, seeded email/identity) and transactions. Re-running it must not add duplicate roles, memberships, or organizations.

### 9. Document and integrate the local developer workflow

1. Document prerequisite local stack startup, explicit migration/seed commands, migration status checks, integration test commands, and the destructive nature of reset/downgrade operations.
2. If a Compose/API image command is added for migrations, make it explicit and one-shot; the normal API/worker startup must not mutate schema automatically. Keep it compatible with the existing pgvector Postgres image and Compose network.
3. Update README/development documentation truthfully: the project has schema/migrations and safe synthetic local seed data, but no functional product CRUD, login, document pipeline, retrieval, or workflow execution yet.
4. Review the complete diff for accidental credentials, committed local database files, raw synthetic data that resembles real PII, generated artifacts, and scope creep into Phase 5 or later.

## Required tests and validation

Run all checks from the repository root after installing locked dependencies. Resolve failures before marking the phase complete.

### Automated database integration tests

Use an isolated PostgreSQL 16 + pgvector instance (for example Testcontainers with the same `pgvector/pgvector` image) rather than SQLite; SQLite cannot validate PostgreSQL extensions, JSONB/INET/array types, vector indexes, or full-text indexes.

```bash
uv run pytest apps/api/tests/unit apps/api/tests/integration
```

At minimum, tests must prove all of the following:

- a fresh empty PostgreSQL+pgvector database upgrades successfully from base to Alembic head;
- the migration adds the UUID-generation and vector extensions, all required tables, and named key indexes/constraints;
- `document_chunks.embedding` has the documented dimension and both vector/full-text indexes are present and usable by PostgreSQL;
- representative inserts exercise UUID/server timestamps, tenant FKs, one-to-one document text, unique document chunk positions, role membership uniqueness, case-number uniqueness within an organization, JSONB metadata, array tags, `INET`, and numeric values;
- cross-tenant foreign-key/reference mistakes and duplicate constrained values fail safely at the database boundary;
- the baseline downgrade returns an empty Phase 4 schema cleanly, and a subsequent upgrade recreates the same schema;
- local seeding succeeds on an empty upgraded database, is idempotent, adds all five roles and synthetic Norwegian tenant data, and adds no plaintext password;
- models/metadata import cleanly and session/engine construction does not connect at module import time;
- application settings and migration failures never render a database URL/password in captured logs or exceptions.

### Static quality checks

```bash
pnpm format:check
pnpm lint
pnpm typecheck
uv run ruff format --check apps services packages scripts
uv run ruff check apps services packages scripts
uv run mypy apps services packages scripts
```

All new Python code must meet the existing strict mypy configuration. Do not suppress typing errors with broad `Any`, `ignore_errors`, untyped declarative models, or unreviewed migration casts.

### Migration and local runtime validation

1. Start the existing local stack:

   ```bash
   pnpm dev:up
   ```

2. From the API environment/container, run the documented explicit commands:

   ```bash
   alembic upgrade head
   python scripts/seed_local.py
   alembic current
   ```

3. Inspect migration status and the expected tables/extensions/indexes using safe local `psql`/checker queries. Confirm the synthetic seed is present and rerun the seed command to prove idempotence.
4. On a disposable local database only, prove rollback and replay:

   ```bash
   alembic downgrade base
   alembic upgrade head
   ```

5. Confirm existing Phase 2/3 liveness, readiness, OpenAPI, and local-stack verification behavior is unchanged:

   ```bash
   pnpm verify:local-stack
   curl --fail http://127.0.0.1:8000/health/live
   curl --fail http://127.0.0.1:8000/health/ready
   curl --fail http://127.0.0.1:8000/openapi.json
   ```

6. Stop the stack normally after manual validation:

   ```bash
   pnpm dev:down
   ```

### Manual architecture and scope review

- Compare each table, field, optionality, and required index to Architecture §10.2 before accepting the migration.
- Verify model naming/locations match Architecture §12 and that models remain separate from API Pydantic schemas.
- Confirm database URLs, passwords, raw object-storage keys beyond the architecture-required field, raw credentials, and raw exceptions are absent from logs/errors/docs/source control.
- Confirm raw files are not stored in PostgreSQL; only document metadata, object-storage keys, and later parsed/chunked text schema exist.
- Confirm no repository/service/API endpoint/auth/worker/retrieval/graph behavior was added early.

## Completion criteria

Phase 4 is complete only when all of the following are true:

- SQLAlchemy 2 models cover every Phase 4 table in Architecture §10.2 with the specified fields, PostgreSQL-native types, relationships, tenant keys, timestamps, archival fields, constraints, and indexes.
- Alembic has one clean, reviewable baseline migration that enables the needed extensions and applies successfully to an empty PostgreSQL 16 + pgvector database.
- The migration includes a safe rollback path for the current baseline and upgrades cleanly again after rollback.
- pgvector and full-text chunk indexes exist with a documented 1536-dimensional embedding contract, while retrieval/query behavior remains deferred.
- The database/session configuration is typed, lazy, testable, and does not leak connection information; importing the API still does not require a live database connection.
- Explicit local seeding adds only idempotent, synthetic Norwegian organization/role/user fixtures with no plaintext passwords or real personal data.
- Database integration tests and existing API tests pass, along with formatting, linting, strict type checks, and local Compose/health/OpenAPI validation.
- Documentation gives accurate, explicit migration and seed commands, identifies destructive rollback/reset operations, and does not overstate unimplemented product behavior.
- No work assigned to repository/service, auth/RBAC, case/document processing, RAG, LangGraph, approval, evaluation, security-hardening, frontend, or deployment phases has been implemented.

## Risks and dependencies

| Risk or dependency | Impact | Required handling in this phase |
| --- | --- | --- |
| Existing Compose PostgreSQL data volume already contains local state | Baseline migration/rollback can produce misleading results or destroy a developer's data. | Run rollback tests only against disposable test databases; clearly document volume-reset/destructive commands and never auto-downgrade on startup. |
| PostgreSQL extension availability differs between local Docker and Azure Database for PostgreSQL | A local-only schema could fail in the deployment target. | Use supported `pgcrypto`/`vector` capabilities, add extensions explicitly/idempotently, and document Azure extension validation as an infrastructure follow-up. |
| Vector index requires a fixed dimension but no provider is selected yet | Future embeddings may be incompatible with the baseline index. | Adopt and document the explicit 1536 baseline; require a reviewed migration before any future provider changes dimension. |
| Alembic async/sync driver confusion | Migrations or app sessions may fail despite valid credentials. | Keep an explicit async runtime URL and a private sync Alembic conversion/path; test both migration execution and async persistence. |
| One oversized initial migration becomes difficult to review | Missing FK/index/nullable detail undermines future functionality. | Organize models by domain but hand-review the generated migration against Architecture §10.2 table-by-table; use deterministic names. |
| Broad cascade deletes or mutable audit data conflict with regulated traceability | Evidence/history can disappear or be altered silently. | Use conservative FK deletion rules, append-only audit schema, soft archival where specified, and defer retention/privilege mechanics to their assigned phases. |
| Seeding adds credentials or personal-looking data | Violates demo and privacy expectations. | Use clearly synthetic identities, no plaintext passwords, idempotent fixtures, and a test that inspects the seeded password fields. |
| SQLite-backed tests miss PostgreSQL behavior | Extensions/indexes/types appear valid in tests but fail locally/production. | Require pgvector PostgreSQL integration tests; use SQLite only for narrow model-free unit tests if useful. |
| Database wiring changes Phase 3 health/OpenAPI behavior | Existing local startup checks regress. | Keep migration/seeding explicit, preserve health routes/factories, and run existing API/local-stack tests as compatibility checks. |

## Notes for the implementation agent

- Treat `architecture.md` §10.2 as the authoritative table/field contract. When a necessary implementation choice is not specified, prefer the smallest reversible choice and record it in code/docs; do not redesign future feature behavior.
- Do not make route handlers own sessions, perform business queries, or expose models directly. Phase 5 will introduce repositories/services; Phase 6 will bind current-user/tenant authorization.
- Keep SQLAlchemy models separate from Pydantic request/response schemas. Future API schemas should project from repositories/services, not expose ORM objects.
- The seed command supplies only database fixtures. Do not claim seeded people can log in before Phase 6 implements hashed credentials and a login flow.
- Keep migration revisions immutable once used. If a validation issue is discovered after applying the baseline locally, add a corrective migration rather than rewriting a revision that another environment may have applied, unless the repository remains explicitly unpublished and the change is coordinated.
- Do not mark Phase 4 `(DONE)` in `specs/roadmap.md` or update `specs/progress.md` until all required implementation, migration, rollback, integration, static, and local-stack validations pass.
