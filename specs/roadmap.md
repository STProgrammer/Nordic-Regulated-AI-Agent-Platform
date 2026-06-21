# Roadmap

This roadmap describes the implementation path for the final production-ready product. Early phases run locally for manual and automated testing, but they are still part of the final system, not disposable prototypes.

Every phase must include at least one validation method. A phase is not complete until its tests or validation checks pass.

---

## Phase 1 — Repository and Workspace Foundation (DONE)

- Set up the monorepo structure for frontend, backend API, agent orchestration, retrieval, document processing, evaluation, infrastructure, shared schemas, scripts, documentation, and sample data.
- Add standard project configuration files for formatting, linting, type checking, environment examples, Git hygiene, and editor consistency.
- Add initial architecture decision records for the chosen architecture style, LangGraph workflows, PostgreSQL with pgvector, and Azure deployment target.
- Validation: Repository structure matches `architecture.md`; formatting and lint commands run successfully on the empty workspace.

## Phase 2 — Local Docker Development Environment (DONE)

- Add Docker Compose services for frontend, API, worker, PostgreSQL, Redis, Azurite, and optional local support services.
- Add local environment configuration using `.env.example` without secrets.
- Add local health endpoints for API and worker readiness.
- Validation: A developer can run the local stack with one command; API, frontend, PostgreSQL, Redis, and Azurite are reachable; health checks pass.

## Phase 3 — Backend API Skeleton (DONE)

- Set up the FastAPI application with structured configuration, logging, error handling, dependency wiring, and OpenAPI documentation.
- Add route groups for auth, users, cases, documents, workflows, approvals, retrieval, evaluations, audit, and admin as stable API boundaries.
- Add a consistent response and error model.
- Validation: Backend unit tests pass; OpenAPI schema is generated; API health and documentation endpoints work locally.

## Phase 4 — Database Foundation and Migrations (DONE)

- Add SQLAlchemy models and Alembic migrations for organizations, users, roles, user roles, cases, documents, document texts, chunks, workflow runs, node runs, agent messages, retrieved sources, extracted fields, risk assessments, approvals, audit events, prompt versions, model usage records, evaluation tables, and memory entries.
- Enable PostgreSQL extensions needed for UUIDs, full-text search, and pgvector.
- Add seed data for local organizations, roles, safe users, and synthetic Norwegian demo setup.
- Validation: Migrations apply cleanly from an empty database; rollback path works for current migrations; database integration tests pass.

## Phase 5 — Backend Repository and Service Layer (DONE)

- Add repository and service-layer patterns for core entities so route handlers stay thin.
- Implement organization scoping across data access paths.
- Add common pagination, filtering, sorting, and audit-event helpers.
- Validation: Repository tests verify organization isolation, basic CRUD behavior, and safe error handling.

## Phase 6 — Authentication, Sessions, and RBAC (DONE)

- Implement secure login, logout, current-user lookup, password hashing, session/token handling, and failed-login rate limiting.
- Implement backend-enforced RBAC for Admin, Compliance Reviewer, Case Worker, Manager, and Read-only Auditor.
- Add authorization checks for organization-scoped resources and separation-of-duties rules for high-risk approval.
- Validation: Auth and RBAC tests pass; unauthorized and cross-organization requests are blocked; OpenAPI documents protected routes.

## Phase 7 — Frontend Application Shell (DONE)

- Set up the Next.js frontend with TypeScript, routing, layout, shared UI components, API client, form handling, and server-state management.
- Add Norwegian Bokmål as the default interface language and English as an optional language.
- Add authenticated navigation for case inbox, approvals, evaluations, admin, and audit areas.
- Validation: Frontend lint, type checks, and component tests pass; local UI connects to the API; language switching works.

## Phase 8 — Case Management Backend (DONE)

- Implement case submission, case listing, case detail, status updates, assignment, filtering, search, archiving, and audit events.
- Support Norwegian date formatting requirements at API boundary through consistent data modeling and frontend formatting support.
- Add validation for title, description, domain, priority, language, due date, and external reference.
- Validation: API tests cover case submission, filters, status transitions, organization isolation, and audit logging.

## Phase 9 — Case Management UI (DONE)

- Implement Case Inbox with filtering by status, risk level, assignee, domain, and priority.
- Implement Case Detail with metadata, status, documents, extracted fields placeholder, evidence placeholder, workflow placeholder, risk placeholder, approval placeholder, and audit timeline placeholder.
- Add accessible forms, error messages, loading states, and empty states in Norwegian Bokmål.
- Validation: Frontend tests and Playwright smoke test cover login, case submission, case list, and case detail navigation.

## Phase 10 — Secure Document Upload and Storage (DONE)

- Implement secure document upload for PDF, DOCX, TXT, Markdown, CSV, XLSX, EML, and pasted email text.
- Store raw files in Azurite locally and add object-storage-compatible storage abstractions for cloud.
- Add file type validation, file size limits, checksums, metadata, source status, confidentiality level, and audit logging.
- Validation: Upload API tests cover allowed files, rejected files, size limits, metadata persistence, and audit events.

## Phase 11 — Document Parsing Pipeline (DONE)

- Implement background document parsing for supported formats with safe error handling.
- Store parsed text separately from raw files, preserve page or section context where available, and detect language.
- Add parsing status, parsing error summaries, and reprocessing support.
- Validation: Parser tests cover each supported file type using safe sample files; failed parsing does not corrupt case or document state.

## Phase 12 — Chunking, Embeddings, and Indexing (DONE)

- Implement tokenizer-aware chunking with document identity, page, section, chunk index, token count, and metadata preservation.
- Add embedding generation and pgvector indexing for document chunks.
- Add keyword/full-text indexing for exact terms, policy names, numbers, and Norwegian text.
- Validation: Integration tests verify chunk persistence, vector index availability, full-text search, and re-indexing behavior.

## Phase 13 — Retrieval Service Foundation (DONE)

- Implement retrieval service boundaries for query rewriting, vector search, keyword search, candidate merging, permissions filtering, source-status filtering, and ranked source return.
- Add support for approved, draft, deprecated, restricted, and archived source behavior.
- Add retrieval logs linked to cases and workflow runs where applicable.
- Validation: Retrieval tests verify semantic search, keyword search, source filtering, restricted source blocking, and deprecated source warnings.

## Phase 14 — Evidence Panel and Document UI (DONE)

- Implement document list, document detail, parsing status display, source status controls, confidentiality display, and re-indexing controls.
- Implement Evidence Panel UI for source title, document type, page/section, score, excerpt, source status warning, and citation label.
- Add UI support for opening source context safely.
- Validation: Frontend and API tests cover document display, source governance actions, evidence rendering, and access restrictions.

## Phase 15 — RAG Answering with Citations (DONE)

- Implement source-grounded question answering over approved sources with citations.
- Add evidence sufficiency checks, weak-evidence refusal behavior, citation formatting, and Norwegian/English answer language handling.
- Store retrieved sources, AI messages, model usage records, latency, token usage, and estimated cost.
- Validation: RAG tests verify expected source retrieval, citations, refusal on weak evidence, Norwegian answers, and model usage logging.

## Phase 16 — Agent Orchestrator Foundation (DONE)

- Set up the agent orchestration service with LangGraph, typed Pydantic graph state, model provider abstraction, prompt version loading, tool registry, and workflow persistence.
- Add shared graph utilities for logging, retry limits, error summaries, node timing, and safe state snapshots.
- Add deterministic test model support for automated tests.
- Validation: LangGraph node-level tests pass; workflow state persists; deterministic test model produces stable test outputs.

## Phase 17 — Intake Graph (DONE)

- Implement the intake workflow for input validation, language detection, case type classification, domain selection, PII detection, prompt-injection signal detection, risk estimate, workflow selection, and persisted intake result.
- Allow low-confidence classification to be corrected by the user.
- Log all intake decisions in workflow and audit records.
- Validation: Graph tests cover Norwegian and English cases, PII examples, prompt-injection examples, low-confidence classification, and audit logging.

## Phase 18 — Evidence Graph (DONE)

- Implement the evidence workflow with query rewriting, hybrid retrieval, candidate merging, reranking, permission filtering, source-status filtering, evidence sufficiency checks, contradiction checks, and persisted evidence package.
- Route weak or contradictory evidence to Needs More Evidence.
- Link evidence results to the case detail page.
- Validation: Graph and integration tests verify expected evidence routing, weak-evidence handling, contradiction flags, and source trace persistence.

## Phase 19 — Extraction Graph (DONE)

- Implement structured extraction for names, organizations, dates, deadlines, amounts, reference numbers, obligations, tasks, risks, missing information, and suggested next actions.
- Validate structured outputs with typed schemas and mark low-confidence fields.
- Store extracted fields with source references and human-edit tracking support.
- Validation: Graph tests cover extraction schemas, validation failures, low-confidence fields, and source-linked structured outputs.

## Phase 20 — Drafting Graph (DONE)

- Implement drafting of Norwegian Bokmål responses, internal recommendations, summaries, and action plans grounded in retrieved sources.
- Add citation validation, unsupported-claim detection, clarity pass, and persisted AI draft records.
- Ensure drafts use user interface language unless otherwise requested.
- Validation: Drafting tests verify citation coverage, unsupported-claim flags, Norwegian language output, and stored draft metadata.

## Phase 21 — Risk and Compliance Graph (DONE)

- Implement final risk checks for PII, weak evidence, contradictory evidence, prompt-injection indicators, high-impact actions, missing required sources, low confidence, and policy conflicts.
- Assign final risk level and approval requirement.
- Persist risk assessments and display risk reasons in the UI.
- Validation: Risk graph tests verify high-risk routing, approval requirements, risk reason display, and audit log entries.

## Phase 22 — Human Approval Workflow (DONE)

- Implement approval queue, review packet, workflow interruption, workflow resume, approve, edit-and-approve, reject, request-more-evidence, and reassign actions.
- Ensure high-risk and low-confidence outputs cannot bypass required approval.
- Store original AI draft separately from final human-approved text.
- Validation: Integration and Playwright tests cover full case worker to reviewer approval flow, edit tracking, rejection, and request-more-evidence paths.

## Phase 23 — Workflow Trace and AI Audit Trail (DONE)

- Implement trace views for workflow runs, LangGraph nodes, tool calls, model calls, retrieved sources, errors, retries, timing, token usage, cost estimate, and final state.
- Implement audit event filtering by organization, case, resource type, event type, and time.
- Ensure traces exclude secrets and unsafe raw credentials.
- Validation: Tests verify trace completeness, audit filtering, role restrictions, and absence of secrets in trace output.

## Phase 24 — Controlled LangMem Memory (DONE)

- Implement LangMem-backed controlled memory for approved non-sensitive use cases such as UI language preference, organization workflow preference, approved terminology, and reusable process hints.
- Add memory scoping, admin disablement, memory usage logging, and memory inspection where appropriate.
- Ensure memory cannot override source-grounded evidence.
- Validation: Memory tests verify organization scoping, user scoping, disablement, forbidden memory rejection, and audit events.

## Phase 25 — Evaluation Dataset and Deterministic Evaluation Runner (DONE)

- Add synthetic Norwegian and English evaluation datasets for public sector, banking, energy, and internal policy scenarios.
- Implement deterministic evaluation runner for retrieval, citation expectations, refusal behavior, risk labels, and LangGraph routing.
- Store evaluation datasets, evaluation runs, and per-case results.
- Validation: Evaluation tests run locally without external model dependency where possible; expected pass/fail results are stored and inspectable.

## Phase 26 — AI Quality Evaluation Dashboard (DONE)

- Implement Evaluation Dashboard with latest run status, retrieval score, citation score, faithfulness score, refusal behavior, latency, cost, and regression failures.
- Add links from failed evaluation cases to detailed result records.
- Add evaluation report export for portfolio and review use.
- Validation: Frontend, API, and integration tests verify evaluation run listing, result detail, failure display, and dashboard metrics.

## Phase 27 — Cost, Latency, Metrics, and Observability (DONE)

- Add structured logging across frontend-relevant API flows, backend services, workers, retrieval, model providers, and LangGraph nodes.
- Add metrics for API latency, workflow runs, node latency, retrieval latency, model latency, token usage, estimated cost, parsing failures, evaluation pass rate, approval rate, and refusal rate.
- Add OpenTelemetry-compatible tracing hooks where appropriate.
- Validation: Observability tests verify expected log fields, metrics emission, workflow timing, and safe error summaries.

## Phase 28 — Export and Mock Enterprise Integrations

- Implement exports for approved outputs in JSON, CSV, Markdown, and PDF report formats.
- Add safe mock integrations for ticket handoff, email handoff, Teams-style notification, and document archive.
- Ensure all exports and mock tool calls are logged and permission-controlled.
- Validation: API and integration tests verify export formats, source references in exports, permission checks, and mock integration audit logs.

## Phase 29 — Security Hardening

- Add secure headers, CORS restrictions by environment, upload hardening, rate limiting for login/upload/retrieval/workflow routes, CSRF protection where relevant, and production-safe error handling.
- Add dependency/security scanning and no-secrets checks.
- Add security documentation for auth, RBAC, file handling, AI safety, secrets, and public demo restrictions.
- Validation: Security tests and scans pass; no high-severity dependency findings are allowed; no secrets are detected in repository.

## Phase 30 — Accessibility and Norwegian UX Polish

- Polish the UI for Norwegian Bokmål as default, English option, Norwegian date/number/currency formatting, clear enterprise language, and domain-relevant sample flows.
- Improve keyboard navigation, labels, error messages, semantic structure, contrast, and non-color-only state indicators.
- Add axe-core accessibility checks for critical pages.
- Validation: Frontend accessibility tests pass; Playwright verifies language switching, Norwegian formatting, and critical keyboard navigation.

## Phase 31 — CI Pipeline

- Add GitHub Actions pull request pipeline for backend linting, backend type checks, backend unit tests, backend integration tests, API contract tests, frontend linting, frontend type checks, frontend unit tests, Playwright smoke tests, deterministic AI regression tests, dependency scanning, and container build checks.
- Add branch protection expectations and CI status documentation.
- Add migration check and OpenAPI schema export check.
- Validation: Full CI pipeline passes from a clean checkout.

## Phase 32 — Container Images and Release Build

- Add production-ready Dockerfiles for frontend, API, and worker services.
- Add image build, tagging, container scanning, and registry push workflow.
- Add runtime environment configuration for local, staging, and production.
- Validation: Container images build successfully; container scan passes release threshold; production-mode containers run locally through Docker Compose.

## Phase 33 — Infrastructure-as-Code for Azure

- Add Bicep or Terraform infrastructure definitions for Azure Container Apps, Azure Database for PostgreSQL, Azure Blob Storage, Azure Key Vault, Azure Container Registry, monitoring resources, managed identity, and environment configuration.
- Add staging and production parameterization.
- Add documentation for required cloud secrets, resource naming, deployment assumptions, and cost-aware settings.
- Validation: Infrastructure plan/validation succeeds; configuration contains no secrets; documentation explains staging and production setup.

## Phase 34 — Staging Deployment

- Implement automated staging deployment after main branch pipeline success.
- Run database migrations, deploy frontend/API/worker containers, configure storage, connect secrets, and expose HTTPS endpoint.
- Add staging smoke tests for login, case submission, document upload, workflow run, approval, evaluation listing, and health checks.
- Validation: Staging deployment succeeds; staging smoke tests pass; health checks pass over HTTPS.

## Phase 35 — Production Deployment

- Implement production deployment with manual approval gate, secure secrets, HTTPS, backups, rate limiting, safe demo data, monitored logs, and restricted admin access.
- Run production smoke tests after deployment.
- Add rollback documentation and operational checklist.
- Validation: Production deployment succeeds; public HTTPS demo is reachable; production smoke tests pass; no real personal data is present.

## Phase 36 — Final End-to-End Product Validation

- Run complete manual and automated product validation across public-sector, banking, energy, and internal policy workflows.
- Validate full path from login, case submission, document upload, parsing, indexing, RAG, LangGraph workflows, risk checks, approval, audit trace, evaluation dashboard, export, and deployment.
- Confirm acceptance criteria from PRD are satisfied or explicitly documented as known limitations.
- Validation: Full E2E test suite passes; manual validation checklist passes; acceptance criteria checklist is complete.

## Phase 37 — Documentation and Portfolio Presentation

- Finalize README, deployment guide, testing guide, security notes, GDPR notes, AI evaluation report, LangGraph workflow documentation, API contract documentation, architecture diagrams, screenshots, demo instructions, and known limitations.
- Add portfolio-ready project summary, demo workflow script, safe demo credentials if used, and repository navigation guide for employers.
- Ensure documentation states implemented features accurately and marks any remaining items as known limitations.
- Validation: Documentation review passes; links, commands, diagrams, screenshots, and demo instructions are accurate.

## Phase 38 — Final Repository Quality Review

- Review commit history, naming consistency, folder structure, code quality, dead code, TODOs, dependency hygiene, environment examples, and public-demo safety.
- Run full local test suite, full CI, staging smoke tests, production smoke tests, security scans, and evaluation tests one final time.
- Tag the final professional release.
- Validation: Final release checklist passes; release tag is present; README points to live demo, architecture, tests, deployment, and evaluation evidence.
