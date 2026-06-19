# architecture.md

# Nordic Regulated AI Agent Platform Architecture

## 1. Architecture Overview

Nordic Regulated AI Agent Platform is a production-style, cloud-ready enterprise AI system built around secure document handling, source-grounded AI workflows, human approval, auditability, evaluation, and Norwegian-language enterprise usability.

The architecture separates concerns across frontend, backend API, agent orchestration, retrieval, document processing, background workers, data storage, evaluation, and infrastructure. The platform is designed for maintainability, testability, observability, and deployability.

## 2. Architecture Goals

The architecture must demonstrate:

- Professional backend architecture
- AI workflow orchestration with LangGraph
- Controlled memory with LangMem where useful
- Source-grounded RAG
- Human-in-the-loop approval
- Secure document processing
- PostgreSQL-backed business data
- Vector search
- Queue-based background processing
- Cloud-ready Docker deployment
- CI/CD and automated test gates
- Strong evaluation strategy for AI behavior
- GDPR-aware data handling
- Norwegian-market relevance
- Clear boundaries between application layers

## 3. High-Level System Diagram

```text
                                ┌────────────────────────────┐
                                │        Browser Client       │
                                │  Norwegian / English UI     │
                                └──────────────┬─────────────┘
                                               │ HTTPS
                                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                           Frontend App                                │
│                     Next.js + TypeScript                              │
│  Case Inbox | Evidence Panel | Approval Queue | Evaluation Dashboard  │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ REST / OpenAPI
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                             API Service                               │
│                          FastAPI + Python                             │
│ Auth | RBAC | Cases | Documents | Workflows | Evaluation | Audit Logs │
└───────────────┬─────────────────────┬────────────────────┬───────────┘
                │                     │                    │
                ▼                     ▼                    ▼
┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐
│ Agent Orchestrator   │ │ Retrieval Service     │ │ Document Service      │
│ LangGraph + LangMem  │ │ Hybrid RAG            │ │ Parsing + Chunking    │
│ Human Approval       │ │ Reranking + Citations │ │ File Metadata         │
└──────────┬───────────┘ └──────────┬───────────┘ └──────────┬───────────┘
           │                        │                        │
           ▼                        ▼                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│                          Background Workers                           │
│       Document indexing | Embedding jobs | Workflow execution          │
│       Evaluation jobs | Export jobs | Cleanup jobs                     │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                              Data Layer                               │
│ PostgreSQL | pgvector | Redis | Object Storage | Optional OpenSearch   │
└──────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         Observability + DevOps                        │
│ Logs | Metrics | Traces | CI/CD | Security Scanning | Azure Deployment │
└──────────────────────────────────────────────────────────────────────┘
```

## 4. Chosen Technology Stack

## 4.1 Frontend

### Main Stack

- **Next.js**
- **TypeScript**
- **React**
- **Tailwind CSS**
- **shadcn/ui**
- **TanStack Query**
- **React Hook Form**
- **Zod**
- **Playwright**
- **Vitest**
- **Testing Library**
- **i18next or next-intl**

### Reasoning

Next.js and TypeScript show strong modern frontend competence. shadcn/ui and Tailwind allow a polished professional UI without heavy UI framework lock-in. TanStack Query gives reliable server-state handling. Zod helps align frontend validation with API contracts. Playwright demonstrates serious end-to-end testing.

### UI Requirements

- Norwegian Bokmål default
- English option
- Accessible layout
- Responsive admin dashboard
- Keyboard-friendly workflow controls
- Clear evidence and approval panels
- Norwegian date, number, and currency formatting

## 4.2 Backend API

### Main Stack

- **Python 3.12**
- **FastAPI**
- **Pydantic v2**
- **SQLAlchemy 2**
- **Alembic**
- **asyncpg**
- **Uvicorn / Gunicorn**
- **httpx**
- **structlog**
- **OpenAPI/Swagger**

### Reasoning

FastAPI is a strong fit for AI/backend systems because it supports typed APIs, async workflows, OpenAPI documentation, and clean integration with Python AI frameworks. SQLAlchemy and Alembic provide professional database modeling and migration handling.

## 4.3 Agent and AI Orchestration

### Main Stack

- **LangGraph**
- **LangChain where useful**
- **LangMem for controlled memory**
- **LangSmith-compatible tracing where useful**
- **Pydantic typed graph state**
- **OpenAI or Azure OpenAI model provider**
- **Local model adapter as optional fallback**
- **Instructor or Pydantic structured output validation**
- **Guardrails through typed schemas and validation**

### Reasoning

LangGraph is used for inspectable, stateful, multi-step workflows with human approval checkpoints. LangMem may be used for controlled memory, but only for organization-scoped, auditable, non-sensitive memory. Pydantic schemas keep AI output structured and testable.

## 4.4 Retrieval and Document Intelligence

### Main Stack

- **PostgreSQL + pgvector**
- **Qdrant as optional dedicated vector store**
- **OpenSearch as optional keyword/hybrid search component**
- **rank-bm25 or OpenSearch BM25**
- **Reranking model or hosted reranker**
- **unstructured**
- **pypdf**
- **python-docx**
- **pandas / openpyxl**
- **tiktoken or tokenizer-aware chunking**
- **language detection library**
- **PII detection using Microsoft Presidio or custom detectors**

### Reasoning

pgvector keeps architecture simpler and employer-friendly because PostgreSQL remains central. Qdrant can be used if the project needs a dedicated vector service. OpenSearch is justified when exact term, compliance reference, and Norwegian keyword matching are important.

## 4.5 Database and Storage

### Main Stack

- **PostgreSQL 16**
- **pgvector**
- **Redis**
- **Azure Blob Storage or S3-compatible object storage**
- **MinIO for local development**

### Reasoning

PostgreSQL is the main source of truth. pgvector supports semantic search. Redis supports queues, locks, caching, and background workflow coordination. Blob-compatible object storage keeps uploaded files outside the relational database.

## 4.6 Background Jobs

### Main Stack

- **Celery + Redis**
- Alternative: **Dramatiq** or **Arq** if async-first simplicity is preferred

### Job Types

- Document parsing
- Chunking
- Embedding
- Re-indexing
- Workflow execution
- Evaluation runs
- Export jobs
- Retention cleanup
- Notification mock jobs

## 4.7 Testing Stack

### Backend Testing

- **pytest**
- **pytest-asyncio**
- **pytest-cov**
- **respx**
- **freezegun**
- **hypothesis**
- **testcontainers**
- **factory_boy**
- **Faker**
- **schemathesis for OpenAPI testing**
- **ruff**
- **mypy**
- **bandit**
- **pip-audit or uv audit**

### Frontend Testing

- **Vitest**
- **Testing Library**
- **Playwright**
- **axe-core accessibility checks**
- **TypeScript strict mode**
- **ESLint**
- **Prettier**

### AI Evaluation Testing

- **DeepEval or Ragas**
- **custom deterministic evaluation scripts**
- **prompt regression tests**
- **retrieval precision tests**
- **citation correctness checks**
- **faithfulness checks**
- **refusal behavior tests**
- **golden dataset tests**
- **LangGraph node-level tests**

### CI Quality Gates

CI must run:

- Backend lint
- Backend type checks
- Backend unit tests
- Backend integration tests
- API contract tests
- Frontend lint
- Frontend type checks
- Frontend component tests
- Playwright smoke tests
- AI deterministic regression tests
- Dependency scan
- Container scan
- Docker image build
- Migration check

## 4.8 DevOps and Cloud

### Main Stack

- **Docker**
- **Docker Compose**
- **GitHub Actions**
- **Azure Container Apps or Azure App Service for Containers**
- **Azure Database for PostgreSQL**
- **Azure Blob Storage**
- **Azure Key Vault**
- **Azure Application Insights**
- **Azure Monitor**
- **Bicep or Terraform**
- **GitHub Environments for staging and production**
- **Dependabot or Renovate**

### Kubernetes Position

AKS is allowed only when justified by service scale and operational complexity. The preferred impressive but credible deployment target is Azure Container Apps because it demonstrates cloud-native deployment without unnecessary Kubernetes overhead.

AKS may be documented as an optional enterprise deployment path, not the default deployment requirement.

## 5. Environment Architecture

## 5.1 Local Environment

Local development uses Docker Compose.

Services:

- frontend
- api
- worker
- postgres
- redis
- minio
- optional qdrant
- optional opensearch
- mail/mock notification service

Local requirements:

- `.env.example`
- no secrets committed
- local seed data
- local test documents
- local evaluation dataset
- one command to run the stack
- one command to run tests

## 5.2 Staging Environment

Staging mirrors production settings with smaller resources.

Purpose:

- Validate deployments
- Run smoke tests
- Run sample workflows
- Validate migrations
- Review UI and workflow behavior before production deployment

Requirements:

- HTTPS
- staging secrets
- staging database
- staging storage
- staging model provider settings
- test/demo users only
- CI deployment after main branch merge

## 5.3 Production Environment

Production is the public portfolio demo environment.

Requirements:

- HTTPS
- secure secrets
- database backups
- health checks
- monitored logs
- restricted demo data
- safe demo credentials if used
- rate limiting
- no real personal data
- admin access restricted

## 6. Core Services

## 6.1 Frontend Web App

Responsibilities:

- User login
- Case inbox
- Case detail view
- Document upload
- Evidence panel
- Approval queue
- Human edit interface
- Workflow trace view
- Evaluation dashboard
- Admin settings
- Norwegian/English language switch
- Accessibility support

Frontend must not contain business-critical authorization logic. Authorization must be enforced by backend.

## 6.2 API Service

Responsibilities:

- Authentication and session handling
- RBAC enforcement
- Organization scoping
- Case API
- Document API
- Workflow API
- Approval API
- Evaluation API
- Audit API
- User and role API
- OpenAPI documentation
- Request validation
- Rate limiting
- Secure error handling

## 6.3 Agent Orchestrator Service

Responsibilities:

- Run LangGraph workflows
- Persist workflow state
- Run human approval interrupts
- Call retrieval service
- Call document service
- Call model provider
- Validate structured outputs
- Log workflow node results
- Track token usage, latency, and cost
- Handle retry and fallback rules
- Use LangMem only where approved

## 6.4 Retrieval Service

Responsibilities:

- Query rewriting
- Hybrid retrieval
- Vector search
- Keyword search
- Reranking
- Source filtering
- Citation extraction
- Evidence sufficiency checks
- Contradiction detection
- Retrieval evaluation support

## 6.5 Document Service

Responsibilities:

- Validate uploaded files
- Store raw files in object storage
- Extract text and metadata
- Detect language
- Chunk documents
- Produce embeddings
- Index chunks
- Track parsing errors
- Support re-indexing

## 6.6 Evaluation Service

Responsibilities:

- Run evaluation datasets
- Score retrieval quality
- Score citation correctness
- Score answer faithfulness
- Test refusal behavior
- Run prompt regression tests
- Store evaluation results
- Export evaluation reports

## 6.7 Worker Service

Responsibilities:

- Run slow jobs outside request lifecycle
- Handle document parsing
- Handle embedding jobs
- Run agent workflows
- Run evaluation tasks
- Run exports
- Run cleanup jobs

## 7. LangGraph Workflow Architecture

## 7.1 Shared Workflow State

All workflows use typed state.

Example state fields:

```python
class CaseWorkflowState(BaseModel):
    organization_id: UUID
    case_id: UUID
    user_id: UUID
    language: Literal["nb-NO", "en"]
    case_type: str | None
    domain: str | None
    risk_level: Literal["low", "medium", "high", "critical"] | None
    pii_detected: bool
    uploaded_document_ids: list[UUID]
    rewritten_queries: list[str]
    retrieved_source_ids: list[UUID]
    evidence_summary: str | None
    extracted_fields: dict[str, Any]
    draft_output: str | None
    confidence_score: float | None
    requires_human_approval: bool
    approval_status: str | None
    final_output: str | None
    errors: list[str]
```

## 7.2 Intake Graph

Purpose:

- Understand incoming case
- Detect language
- Detect PII
- Classify domain
- Assign workflow
- Estimate risk

Nodes:

1. validate_case_input
2. detect_language
3. classify_case_type
4. detect_pii
5. detect_prompt_injection
6. estimate_risk
7. choose_workflow
8. persist_intake_result

Outputs:

- case type
- domain
- language
- risk level
- required workflow
- approval requirement

## 7.3 Evidence Graph

Purpose:

- Find and validate sources

Nodes:

1. rewrite_query
2. retrieve_vector_candidates
3. retrieve_keyword_candidates
4. merge_candidates
5. rerank_sources
6. filter_by_permissions
7. check_source_status
8. evaluate_evidence_sufficiency
9. detect_contradictions
10. persist_evidence

Outputs:

- ranked source list
- evidence summary
- citation candidates
- evidence sufficiency result

## 7.4 Extraction Graph

Purpose:

- Extract structured fields

Nodes:

1. select_extraction_schema
2. extract_fields
3. validate_structured_output
4. mark_low_confidence_fields
5. persist_extracted_fields

Outputs:

- structured fields
- confidence per field
- missing information
- validation errors

## 7.5 Drafting Graph

Purpose:

- Draft source-grounded response, recommendation, or action plan

Nodes:

1. prepare_context
2. draft_response
3. validate_citations
4. check_unsupported_claims
5. improve_clarity
6. persist_draft

Outputs:

- draft text
- citations
- confidence score
- unsupported claim warnings

## 7.6 Risk and Compliance Graph

Purpose:

- Decide whether output can be shown, needs review, or needs more evidence

Nodes:

1. check_pii_policy
2. check_weak_evidence
3. check_high_impact_action
4. check_policy_conflict
5. check_prompt_injection_result
6. assign_final_risk
7. decide_approval_requirement

Outputs:

- final risk level
- risk reasons
- approval requirement
- safe next state

## 7.7 Human Approval Graph

Purpose:

- Pause workflow until reviewer action

Nodes:

1. prepare_review_packet
2. interrupt_for_human_review
3. handle_approval
4. handle_rejection
5. handle_edit
6. handle_more_evidence_request
7. resume_workflow

Reviewer actions:

- approve
- edit and approve
- reject
- request more evidence
- reassign

## 7.8 Evaluation Graph

Purpose:

- Run quality tests against workflows

Nodes:

1. load_eval_dataset
2. run_case_workflows
3. score_retrieval
4. score_citations
5. score_faithfulness
6. score_refusal_behavior
7. score_latency_and_cost
8. persist_eval_results
9. mark_pass_fail

## 8. LangMem Usage

LangMem may be used only for controlled, auditable memory.

Allowed memory examples:

- User UI language preference
- Organization-approved workflow preference
- Reusable domain explanation approved by admin
- Common reviewer feedback pattern after approval
- Stable terminology preferences

Forbidden memory examples:

- Raw personal data
- Sensitive case details
- Secrets
- Unapproved user profiling
- Cross-organization memory leakage
- Hidden decision history not visible to authorized users

Memory requirements:

- Memory must be scoped by organization.
- Memory must be inspectable by authorized users where relevant.
- Memory usage must be logged.
- Memory may be disabled by admin.
- Memory must not override source-grounded evidence.

## 9. RAG Architecture

## 9.1 Ingestion Pipeline

```text
Upload file
  → validate file
  → store raw file
  → extract text
  → detect language
  → extract metadata
  → chunk text
  → embed chunks
  → index vector data
  → index keyword data
  → mark document searchable
```

## 9.2 Retrieval Pipeline

```text
User/case query
  → rewrite query
  → run vector search
  → run keyword search
  → merge candidates
  → rerank
  → filter by permissions
  → filter by document status
  → return source excerpts
  → evaluate evidence sufficiency
```

## 9.3 Answer Pipeline

```text
Evidence package
  → draft source-grounded answer
  → validate citations
  → detect unsupported claims
  → detect contradictions
  → assign confidence
  → route to approval or final output
```

## 10. Database Structure

## 10.1 Naming Rules

- Table names use plural snake_case.
- Primary keys use UUID.
- Timestamps use `inserted_at` and `updated_at`.
- Organization isolation uses `organization_id`.
- Soft archival uses `archived_at`.
- Sensitive logs avoid raw secrets and unnecessary personal data.

## 10.2 Core Tables

### organizations

Stores tenant organizations.

Fields:

- id UUID PK
- name text
- slug text unique
- default_language text
- retention_policy jsonb
- settings jsonb
- inserted_at timestamptz
- updated_at timestamptz
- archived_at timestamptz nullable

### users

Stores users.

Fields:

- id UUID PK
- organization_id UUID FK
- email text unique
- display_name text
- password_hash text nullable
- identity_provider text nullable
- identity_subject text nullable
- preferred_language text
- is_active boolean
- last_login_at timestamptz nullable
- inserted_at timestamptz
- updated_at timestamptz

### roles

Stores roles.

Fields:

- id UUID PK
- name text unique
- description text
- inserted_at timestamptz

### user_roles

Maps users to roles.

Fields:

- user_id UUID FK
- role_id UUID FK
- organization_id UUID FK
- inserted_at timestamptz

Composite unique:

- user_id, role_id, organization_id

### cases

Stores business cases.

Fields:

- id UUID PK
- organization_id UUID FK
- case_number text
- title text
- description text
- language text
- domain text
- case_type text nullable
- priority text
- status text
- risk_level text nullable
- assigned_user_id UUID nullable FK
- submitted_by_user_id UUID FK
- due_date date nullable
- external_reference text nullable
- inserted_at timestamptz
- updated_at timestamptz
- archived_at timestamptz nullable

Indexes:

- organization_id, status
- organization_id, risk_level
- organization_id, case_number
- organization_id, inserted_at

### documents

Stores uploaded document metadata.

Fields:

- id UUID PK
- organization_id UUID FK
- case_id UUID nullable FK
- uploaded_by_user_id UUID FK
- title text
- original_filename text
- file_type text
- mime_type text
- file_size_bytes bigint
- checksum_sha256 text
- object_storage_key text
- language text nullable
- source_status text
- confidentiality_level text
- page_count integer nullable
- parsing_status text
- parsing_error text nullable
- inserted_at timestamptz
- updated_at timestamptz
- archived_at timestamptz nullable

Indexes:

- organization_id, case_id
- organization_id, source_status
- checksum_sha256

### document_texts

Stores extracted text.

Fields:

- id UUID PK
- document_id UUID FK
- extracted_text text
- extraction_metadata jsonb
- inserted_at timestamptz

### document_chunks

Stores chunks for retrieval.

Fields:

- id UUID PK
- organization_id UUID FK
- document_id UUID FK
- chunk_index integer
- page_number integer nullable
- section_title text nullable
- content text
- token_count integer
- metadata jsonb
- embedding vector
- inserted_at timestamptz
- updated_at timestamptz

Indexes:

- organization_id, document_id
- vector index on embedding
- full-text index on content

### workflow_runs

Stores LangGraph workflow runs.

Fields:

- id UUID PK
- organization_id UUID FK
- case_id UUID FK
- workflow_name text
- workflow_version text
- status text
- started_by_user_id UUID FK
- started_at timestamptz
- finished_at timestamptz nullable
- duration_ms integer nullable
- total_cost_estimate numeric nullable
- total_tokens integer nullable
- error_summary text nullable
- state_snapshot jsonb
- inserted_at timestamptz
- updated_at timestamptz

Indexes:

- organization_id, case_id
- organization_id, workflow_name
- organization_id, status

### workflow_node_runs

Stores LangGraph node execution details.

Fields:

- id UUID PK
- workflow_run_id UUID FK
- node_name text
- status text
- started_at timestamptz
- finished_at timestamptz nullable
- duration_ms integer nullable
- input_summary jsonb
- output_summary jsonb
- error_summary text nullable
- retry_count integer
- inserted_at timestamptz

Indexes:

- workflow_run_id
- node_name, status

### agent_messages

Stores AI messages and structured outputs.

Fields:

- id UUID PK
- organization_id UUID FK
- case_id UUID FK
- workflow_run_id UUID FK
- message_type text
- role text
- content text
- structured_output jsonb nullable
- model_provider text
- model_name text
- prompt_version_id UUID nullable FK
- token_input integer nullable
- token_output integer nullable
- cost_estimate numeric nullable
- latency_ms integer nullable
- inserted_at timestamptz

### retrieved_sources

Stores sources used in RAG.

Fields:

- id UUID PK
- organization_id UUID FK
- case_id UUID FK
- workflow_run_id UUID FK
- document_id UUID FK
- chunk_id UUID FK
- rank integer
- score numeric
- retrieval_method text
- excerpt text
- citation_label text
- inserted_at timestamptz

Indexes:

- organization_id, case_id
- workflow_run_id

### extracted_fields

Stores structured extraction results.

Fields:

- id UUID PK
- organization_id UUID FK
- case_id UUID FK
- workflow_run_id UUID FK
- field_name text
- field_value jsonb
- confidence numeric nullable
- source_chunk_id UUID nullable FK
- human_edited boolean
- inserted_at timestamptz
- updated_at timestamptz

### risk_assessments

Stores risk assessment results.

Fields:

- id UUID PK
- organization_id UUID FK
- case_id UUID FK
- workflow_run_id UUID FK
- risk_level text
- risk_reasons jsonb
- pii_detected boolean
- prompt_injection_detected boolean
- weak_evidence boolean
- high_impact_action boolean
- requires_approval boolean
- inserted_at timestamptz

### approvals

Stores human approval actions.

Fields:

- id UUID PK
- organization_id UUID FK
- case_id UUID FK
- workflow_run_id UUID FK
- reviewer_user_id UUID FK
- decision text
- reviewer_comment text nullable
- ai_draft text nullable
- final_text text nullable
- decision_at timestamptz
- inserted_at timestamptz

### audit_events

Stores audit events.

Fields:

- id UUID PK
- organization_id UUID FK
- actor_user_id UUID nullable FK
- event_type text
- resource_type text
- resource_id UUID nullable
- case_id UUID nullable FK
- ip_address inet nullable
- user_agent text nullable
- event_data jsonb
- inserted_at timestamptz

Indexes:

- organization_id, inserted_at
- organization_id, event_type
- case_id

### prompt_versions

Stores prompt templates and versions.

Fields:

- id UUID PK
- organization_id UUID nullable FK
- name text
- version text
- content text
- description text nullable
- is_active boolean
- inserted_at timestamptz
- updated_at timestamptz

### model_usage_records

Stores model usage details.

Fields:

- id UUID PK
- organization_id UUID FK
- case_id UUID nullable FK
- workflow_run_id UUID nullable FK
- provider text
- model_name text
- operation text
- token_input integer nullable
- token_output integer nullable
- cost_estimate numeric nullable
- latency_ms integer nullable
- success boolean
- error_summary text nullable
- inserted_at timestamptz

### eval_datasets

Stores evaluation datasets.

Fields:

- id UUID PK
- organization_id UUID nullable FK
- name text
- description text
- dataset_version text
- domain text
- inserted_at timestamptz
- updated_at timestamptz

### eval_cases

Stores individual evaluation cases.

Fields:

- id UUID PK
- eval_dataset_id UUID FK
- input_case jsonb
- expected_behavior jsonb
- expected_sources jsonb
- expected_risk_level text nullable
- tags text[]
- inserted_at timestamptz

### eval_runs

Stores evaluation runs.

Fields:

- id UUID PK
- organization_id UUID nullable FK
- eval_dataset_id UUID FK
- run_name text
- status text
- started_at timestamptz
- finished_at timestamptz nullable
- summary_metrics jsonb
- pass_fail text
- inserted_at timestamptz

### eval_results

Stores per-case evaluation results.

Fields:

- id UUID PK
- eval_run_id UUID FK
- eval_case_id UUID FK
- workflow_run_id UUID nullable FK
- retrieval_score numeric nullable
- citation_score numeric nullable
- faithfulness_score numeric nullable
- refusal_score numeric nullable
- latency_ms integer nullable
- cost_estimate numeric nullable
- passed boolean
- failure_reasons jsonb
- inserted_at timestamptz

### memory_entries

Stores controlled LangMem-related memory records where allowed.

Fields:

- id UUID PK
- organization_id UUID FK
- user_id UUID nullable FK
- memory_scope text
- memory_type text
- content jsonb
- source text
- is_active boolean
- inserted_at timestamptz
- updated_at timestamptz
- archived_at timestamptz nullable

Indexes:

- organization_id, memory_scope
- organization_id, user_id

## 11. API Boundaries

## 11.1 API Style

- REST API with OpenAPI documentation.
- JSON request and response bodies.
- Typed schemas with Pydantic.
- Consistent error model.
- Auth required by default.
- Organization scoping enforced in backend.

## 11.2 API Route Groups

### Auth

```text
POST   /api/auth/login
POST   /api/auth/logout
GET    /api/auth/me
```

### Users and Roles

```text
GET    /api/users
POST   /api/users
GET    /api/users/{user_id}
PATCH  /api/users/{user_id}
GET    /api/roles
PUT    /api/users/{user_id}/roles
```

### Cases

```text
GET    /api/cases
POST   /api/cases
GET    /api/cases/{case_id}
PATCH  /api/cases/{case_id}
POST   /api/cases/{case_id}/archive
```

### Documents

```text
POST   /api/documents/upload
GET    /api/documents/{document_id}
GET    /api/documents/{document_id}/chunks
POST   /api/documents/{document_id}/reindex
POST   /api/documents/{document_id}/archive
```

### Workflows

```text
POST   /api/cases/{case_id}/workflows/run
GET    /api/workflows/{workflow_run_id}
GET    /api/workflows/{workflow_run_id}/trace
POST   /api/workflows/{workflow_run_id}/cancel
```

### Approvals

```text
GET    /api/approvals/queue
POST   /api/approvals/{approval_id}/approve
POST   /api/approvals/{approval_id}/reject
POST   /api/approvals/{approval_id}/request-more-evidence
```

### Retrieval

```text
POST   /api/retrieval/search
POST   /api/retrieval/answer
```

### Evaluation

```text
GET    /api/evaluations/datasets
POST   /api/evaluations/run
GET    /api/evaluations/runs
GET    /api/evaluations/runs/{eval_run_id}
```

### Audit

```text
GET    /api/audit/events
GET    /api/cases/{case_id}/audit
```

### Admin

```text
GET    /api/admin/settings
PATCH  /api/admin/settings
GET    /api/admin/health
GET    /api/admin/model-usage
```

## 12. File and Folder Structure

```text
nordic-regulated-ai-agent-platform/
  README.md
  SECURITY.md
  LICENSE
  .env.example
  .gitignore
  docker-compose.yml
  docker-compose.test.yml

  docs/
    PRD.md
    architecture.md
    deployment.md
    testing.md
    security.md
    gdpr-notes.md
    ai-evaluation.md
    langgraph-workflows.md
    api-contracts.md
    adr/
      0001-architecture-style.md
      0002-langgraph-for-agent-workflows.md
      0003-postgresql-and-pgvector.md
      0004-azure-deployment-target.md

  apps/
    web/
      package.json
      next.config.ts
      tsconfig.json
      src/
        app/
          [locale]/
            layout.tsx
            page.tsx
            cases/
            approvals/
            evaluations/
            admin/
        components/
          case/
          evidence/
          approval/
          workflow/
          evaluation/
          layout/
          ui/
        lib/
          api/
          auth/
          i18n/
          formatting/
          validation/
        tests/
          unit/
          e2e/
      public/
        screenshots/

    api/
      pyproject.toml
      alembic.ini
      src/
        app/
          main.py
          core/
            config.py
            logging.py
            security.py
            rate_limit.py
            errors.py
          api/
            routes/
              auth.py
              users.py
              cases.py
              documents.py
              workflows.py
              approvals.py
              retrieval.py
              evaluations.py
              audit.py
              admin.py
            dependencies.py
            schemas/
          db/
            session.py
            models/
            migrations/
            repositories/
          services/
            auth/
            cases/
            documents/
            retrieval/
            approvals/
            audit/
            evaluation/
          workers/
            celery_app.py
            jobs/
          tests/
            unit/
            integration/
            api/
            contract/

  services/
    agent_orchestrator/
      pyproject.toml
      src/
        agent_orchestrator/
          graphs/
            intake_graph.py
            evidence_graph.py
            extraction_graph.py
            drafting_graph.py
            risk_graph.py
            approval_graph.py
            evaluation_graph.py
          state/
            case_state.py
            evidence_state.py
          nodes/
            intake/
            retrieval/
            extraction/
            drafting/
            risk/
            approval/
          tools/
            retrieval_tool.py
            document_tool.py
            memory_tool.py
            audit_tool.py
          memory/
            langmem_store.py
            policies.py
          prompts/
            intake/
            retrieval/
            extraction/
            drafting/
            risk/
          model_providers/
            base.py
            openai_provider.py
            azure_openai_provider.py
            local_provider.py
          tests/
            unit/
            graph/
            regression/

    retrieval/
      pyproject.toml
      src/
        retrieval/
          chunking/
          embeddings/
          hybrid_search/
          reranking/
          citations/
          evaluation/
          tests/

    document_processor/
      pyproject.toml
      src/
        document_processor/
          parsers/
          validators/
          metadata/
          pii/
          tests/

    evaluation/
      pyproject.toml
      src/
        evaluation/
          datasets/
          metrics/
          runners/
          reports/
          tests/

  packages/
    shared_schemas/
      pyproject.toml
      src/
        shared_schemas/
          cases.py
          documents.py
          workflows.py
          evaluations.py
          audit.py

  infra/
    azure/
      bicep/
        main.bicep
        modules/
      terraform/
        main.tf
        variables.tf
        outputs.tf
    docker/
      api.Dockerfile
      web.Dockerfile
      worker.Dockerfile
    github-actions/
      ci.yml
      deploy-staging.yml
      deploy-production.yml

  sample-data/
    public-sector/
    banking/
    energy/
    internal-policy/
    evaluation/

  scripts/
    seed_local.py
    run_evals.py
    check_migrations.py
    export_openapi.py
```

## 13. Security Architecture

## 13.1 Authentication

- Secure login.
- Password hashing with Argon2 or bcrypt.
- Optional enterprise identity provider readiness.
- Secure cookies or secure token handling.
- Session expiration.
- Failed-login rate limiting.

## 13.2 Authorization

- Backend-enforced RBAC.
- Organization scoping on every data access path.
- Admin-only access for settings and user management.
- Reviewer-only access for approval decisions.
- Audit-only role for read-only audit inspection.

## 13.3 File Security

- Validate MIME type and extension.
- Enforce file size limits.
- Store raw files outside database.
- Use checksum to identify duplicates.
- Reject unsafe formats.
- Parse files in background jobs.
- Avoid exposing storage keys directly to users.

## 13.4 API Security

- Input validation with Pydantic.
- Rate limiting on login, upload, retrieval, and workflow routes.
- Secure headers.
- CORS restricted by environment.
- Consistent safe error responses.
- No stack traces in production responses.
- Secrets never logged.

## 13.5 AI Security

- Prompt-injection detection for documents and user input.
- Tool-call allowlist.
- Source-grounded answer constraints.
- Human approval for high-risk actions.
- Model output validation.
- Refusal behavior when evidence is weak.
- Audit logging of model and tool usage.

## 13.6 Privacy

- Synthetic demo data only.
- PII detection in documents and case text.
- Role-restricted sensitive cases.
- Logs minimized.
- Retention policy documented.
- Data archival and deletion flows documented.
- No personal data in public repository.

## 14. Observability Architecture

## 14.1 Logging

Use structured logging.

Log fields:

- timestamp
- environment
- service
- organization_id where safe
- user_id where safe
- case_id where relevant
- workflow_run_id where relevant
- event_type
- status
- duration_ms
- error_code
- safe error summary

## 14.2 Metrics

Track:

- API request count
- API latency
- API error rate
- workflow runs by status
- node latency
- retrieval latency
- model latency
- token usage
- estimated AI cost
- document parsing failures
- evaluation pass rate
- approval rate
- refusal rate

## 14.3 Tracing

OpenTelemetry is recommended.

Trace:

- API request lifecycle
- document processing jobs
- LangGraph node execution
- retrieval calls
- model calls
- evaluation runs

## 15. CI/CD Architecture

## 15.1 Pull Request Pipeline

Runs on every pull request:

1. Backend formatting check
2. Backend lint
3. Backend type check
4. Backend unit tests
5. Backend integration tests
6. API contract tests
7. Frontend lint
8. Frontend type check
9. Frontend unit tests
10. Playwright smoke tests
11. AI deterministic regression tests
12. Dependency scan
13. Container build check

## 15.2 Main Branch Pipeline

Runs after merge:

1. Full CI pipeline
2. Docker image build
3. Container scan
4. Push images to registry
5. Deploy to staging
6. Run staging smoke tests
7. Run selected evaluation tests
8. Manual approval for production deployment
9. Deploy to production
10. Run production smoke tests

## 15.3 Release Rules

Production deployment requires:

- passing tests
- no high-severity dependency findings
- successful migration check
- staging smoke test pass
- documentation updated for architecture-impacting changes

## 16. Infrastructure Architecture

## 16.1 Azure Components

Recommended Azure target:

- Azure Container Apps for API, web, and worker
- Azure Database for PostgreSQL
- Azure Blob Storage
- Azure Key Vault
- Azure Container Registry
- Azure Application Insights
- Azure Monitor
- Azure Cache for Redis if needed
- Azure Front Door or managed HTTPS endpoint if justified

## 16.2 Infrastructure-as-Code

Use Bicep or Terraform.

Required resources:

- resource group
- container registry
- container app environment
- API container app
- web container app
- worker container app
- PostgreSQL instance
- storage account
- key vault
- monitoring resources
- managed identity where possible

## 16.3 Secrets Management

Secrets must be stored in:

- local `.env` for local development only
- GitHub Actions secrets for CI/CD
- Azure Key Vault for deployed environments

Forbidden:

- secrets in repository
- secrets in screenshots
- secrets in logs
- secrets in sample config

## 17. Testing Architecture

## 17.1 Backend Unit Tests

Test:

- service functions
- validation
- auth helpers
- RBAC rules
- risk scoring
- citation validation
- parsing utilities
- cost calculation
- repository behavior with test database

## 17.2 Backend Integration Tests

Test:

- API + database
- document upload flow
- document indexing flow
- workflow run flow
- approval flow
- audit log flow
- evaluation run flow

Use testcontainers for PostgreSQL and Redis.

## 17.3 API Contract Tests

Use Schemathesis or equivalent to validate OpenAPI behavior.

Test:

- schema conformance
- error responses
- required auth
- invalid input handling

## 17.4 Frontend Tests

Test:

- case inbox rendering
- case detail page
- document upload form
- approval controls
- evidence panel
- evaluation dashboard
- language switching
- error states

## 17.5 End-to-End Tests

Use Playwright.

Core E2E scenario:

1. Login as case worker.
2. Submit case.
3. Upload document.
4. Run workflow.
5. Inspect evidence.
6. Login as reviewer.
7. Approve or request more evidence.
8. Confirm audit trail.
9. Inspect evaluation dashboard.

## 17.6 AI Evaluation Tests

Test:

- retrieval returns expected source
- answer cites expected source
- answer refuses weak evidence
- prompt-injection text is flagged
- PII case triggers high risk
- high-risk case requires approval
- Norwegian answer uses clear Bokmål
- unsupported claim detection works

## 18. Code Quality Standards

## 18.1 Python

- Python 3.12
- type hints required
- mypy strict or near-strict
- ruff for linting and formatting
- Pydantic schemas for boundaries
- SQLAlchemy models isolated from API schemas
- repository/service separation
- no business logic inside route handlers
- no raw SQL unless justified and documented

## 18.2 TypeScript

- strict mode enabled
- typed API client
- Zod validation where useful
- reusable UI components
- clear feature folders
- no business-critical authorization logic only in frontend
- accessible components

## 18.3 AI Workflow Code

- each LangGraph node has one clear responsibility
- graph state is typed
- prompts are versioned
- structured output is validated
- model calls are wrapped through provider interface
- tool calls are logged
- risky operations require explicit routing
- evaluation tests protect important behavior

## 19. Documentation Requirements

The repository must include:

- README.md
- PRD.md
- architecture.md
- deployment.md
- testing.md
- security.md
- gdpr-notes.md
- ai-evaluation.md
- langgraph-workflows.md
- API documentation
- architecture decision records
- screenshots
- demo instructions
- known limitations
- roadmap.md later

## 20. Architecture Decisions

## 20.1 FastAPI for Backend

FastAPI provides typed Python API development, OpenAPI documentation, async support, and strong AI ecosystem compatibility.

## 20.2 LangGraph for Agent Workflows

LangGraph is used because the system requires inspectable, stateful, multi-step workflows with approval checkpoints, typed state, persistence, and clear node transitions.

## 20.3 PostgreSQL as Main Database

PostgreSQL is used as the system of record because it is mature, employer-recognized, reliable, and suitable for enterprise software.

## 20.4 pgvector as Default Vector Store

pgvector keeps semantic search close to the main data layer and reduces operational complexity. Qdrant can be added if vector workload or search requirements justify it.

## 20.5 Azure as Deployment Target

Azure is selected because it is highly relevant to Norwegian enterprise, public-sector, and Microsoft-oriented environments.

## 20.6 Azure Container Apps Before AKS

Azure Container Apps demonstrates cloud-native deployment with lower operational burden. AKS is reserved for a documented enterprise-scale path.

## 20.7 Human Approval as Core Architecture

Human approval is not an add-on. It is a core safety and governance boundary for regulated workflows.

## 21. Deployment Requirements

A professional deployment must provide:

- HTTPS
- local, staging, production environments
- secure secrets handling
- health checks
- database migrations
- rollback strategy
- CI/CD deployment
- smoke tests after deployment
- monitoring
- safe demo data
- documented operational steps

## 22. Repository Presentation Requirements

The GitHub repository must include:

- professional README
- screenshots
- architecture diagram
- LangGraph workflow diagram
- live demo link
- safe demo credentials if used
- local setup instructions
- testing instructions
- deployment instructions
- security notes
- evaluation report
- known limitations
- professional commit history
- clear issue/roadmap structure

## 23. Known Architectural Risks

### 23.1 Overengineering Risk

The project must avoid unnecessary complexity. Every service and tool must support a clear product requirement.

Mitigation:

- Use PostgreSQL + pgvector as default.
- Add Qdrant or OpenSearch only if justified.
- Use Azure Container Apps before AKS.
- Keep service boundaries clear but not fragmented.

### 23.2 AI Reliability Risk

AI output may be incorrect or unsupported.

Mitigation:

- citations
- evidence sufficiency checks
- refusal behavior
- human approval
- prompt regression tests
- evaluation dataset
- audit trail

### 23.3 Privacy Risk

Documents may contain sensitive data.

Mitigation:

- synthetic demo data
- PII detection
- RBAC
- audit logs
- restricted file access
- no real personal data in public demo

### 23.4 Cost Risk

AI workflows may become expensive.

Mitigation:

- token tracking
- cost tracking
- workflow budgets
- model selection policy
- caching where appropriate
- evaluation of cost per case

### 23.5 Latency Risk

Multi-step workflows may be slow.

Mitigation:

- background jobs
- progress status
- async API design
- retrieval optimization
- node-level timing
- p95 latency monitoring

## 24. Final Architecture Summary

Nordic Regulated AI Agent Platform uses Next.js, FastAPI, PostgreSQL, pgvector, Redis, object storage, LangGraph, LangMem, Docker, GitHub Actions, Azure, and a strong testing/evaluation stack to deliver a professional enterprise AI workflow system.

The architecture is designed to show Norwegian employers that the project is not a small AI demo, but a serious software engineering project covering backend development, AI orchestration, RAG, security, privacy, DevOps, testing, deployment, and responsible AI operation.
