# PRD.md

# Nordic Regulated AI Agent Platform

## 1. Product Summary

**Nordic Regulated AI Agent Platform** is a production-style enterprise AI platform for Norwegian organizations that handle document-heavy, compliance-sensitive workflows. The platform uses agentic AI workflows to support case intake, document understanding, source-grounded question answering, structured extraction, risk checks, human approval, audit logging, and operational evaluation.

The product is designed for Norwegian employers and regulated environments where AI output must be traceable, reviewable, explainable, secure, and aligned with privacy-by-design principles. It must not behave like a generic chatbot or “chat with PDF” tool. It must demonstrate professional backend engineering, AI platform design, DevOps discipline, cloud deployment, testing strategy, and responsible AI engineering.

The primary language of the application is **Norwegian Bokmål**, with **English** as an optional interface language.

## 2. Product Positioning

This platform is positioned as an **enterprise AI workflow system** for regulated Norwegian organizations, especially:

- Public-sector administration
- Banking and finance
- Energy and industrial operations
- Compliance-heavy private companies
- Internal enterprise support teams
- Legal, HR, procurement, and document-processing departments

The platform supports employees by helping them process cases, retrieve trusted knowledge, draft responses, extract structured facts, identify risk, and route sensitive actions for human approval.

The system does not replace professional judgment. It assists employees while keeping humans responsible for final decisions in sensitive workflows.

## 3. Target Users

### 3.1 Case Worker

A public-sector or enterprise employee who handles incoming requests, documents, internal cases, reports, emails, policies, or customer/citizen-related material.

Needs:

- Fast document understanding
- Reliable summaries
- Source-grounded answers
- Suggested next actions
- Norwegian-language support
- Human-review workflow

### 3.2 Compliance Officer

A user responsible for privacy, regulatory review, internal policy compliance, or risk control.

Needs:

- Audit trail
- Risk flags
- PII detection
- Source references
- Human approval history
- Exportable evidence trail

### 3.3 Team Lead / Manager

A manager who wants visibility into workload, AI assistance quality, bottlenecks, and risk.

Needs:

- Dashboard of case status
- Workflow metrics
- Approval metrics
- Cost and latency insight
- Quality trends
- Failed workflow visibility

### 3.4 AI Platform Administrator

A technical or semi-technical user responsible for system settings, prompt versions, model settings, access control, and evaluation.

Needs:

- Workflow configuration
- Prompt and model configuration
- Evaluation reports
- Tool-call logs
- System health status
- Secure user and role management

### 3.5 Developer / Reviewer

A technical reviewer, employer, or engineering team member evaluating the codebase and architecture.

Needs:

- Clean repo
- Typed backend and frontend code
- API documentation
- Test strategy
- CI/CD
- Security documentation
- Deployment instructions
- Architecture decision records

## 4. Core Business Problem

Norwegian organizations often work with large volumes of documents, case notes, public guidance, internal policy material, regulations, reports, and correspondence. Employees spend significant time reading, searching, summarizing, extracting facts, drafting replies, and checking whether information is complete.

Generic AI tools are insufficient for this setting because they often lack:

- Source grounding
- Role-based access control
- Auditability
- Privacy-aware design
- Workflow integration
- Human approval
- Evaluation
- Norwegian-language domain adaptation
- Production deployment discipline

The platform solves this by providing a structured AI workflow system where every important AI action is grounded, logged, reviewable, and measurable.

## 5. Product Goals

### 5.1 Primary Goals

1. Provide a professional AI workflow platform for Norwegian regulated use cases.
2. Support Norwegian Bokmål as the default user-facing language.
3. Process documents and case text through structured LangGraph workflows.
4. Retrieve relevant source material and cite it in AI outputs.
5. Extract structured fields from documents and case descriptions.
6. Detect risk, uncertainty, PII, and weak evidence.
7. Require human approval for sensitive, high-risk, or low-confidence outputs.
8. Store a complete audit trail of AI actions, tool calls, sources, approvals, and edits.
9. Provide quality evaluation for RAG and agent workflows.
10. Run as a deployable cloud-ready system with CI/CD, tests, security controls, and documented operations.

### 5.2 Employer-Signal Goals

The project must prove competence in:

- Backend engineering
- API design
- Cloud deployment
- Docker and DevOps
- CI/CD
- AI engineering
- LangGraph workflow orchestration
- RAG and retrieval engineering
- Testing and evaluation
- Security and privacy
- Maintainable architecture
- Norwegian enterprise software expectations

## 6. Non-Goals

The platform must not be positioned as:

- A small chatbot
- A generic PDF Q&A tool
- A tutorial clone
- A student exercise
- A one-page demo
- A black-box AI answer system
- A system that makes final legal, medical, financial, or public-sector decisions without human approval

The system will not use real personal data in the public demo. All sample data must be synthetic, public, anonymized, or safe for demonstration.

## 7. Primary Use Cases

### 7.1 Public-Sector Case Support

A case worker submits a Norwegian case description and relevant documents. The platform classifies the case, detects personal data, retrieves relevant internal policy and public guidance, drafts a response in Norwegian Bokmål, and sends the result to human approval before final use.

### 7.2 Banking Compliance Review

A compliance user uploads a customer-related case description and internal policy documents. The system identifies risk factors, extracts structured information, retrieves applicable policy sections, drafts an internal recommendation, and requires approval from a reviewer.

### 7.3 Energy Operations Support

An employee uploads an operational report or safety-related note. The system extracts assets, issue type, severity, deadlines, and recommended next actions, then retrieves relevant procedure documents and escalates high-risk cases.

### 7.4 Internal Policy Assistant

An employee asks questions about HR, IT security, procurement, privacy, or internal procedures. The system answers only when it can ground the response in approved sources. If evidence is weak, the system refuses or asks for more context.

### 7.5 Document Intelligence Workflow

A user uploads a document. The platform identifies document type, extracts structured fields, summarizes key points, identifies deadlines and obligations, flags uncertainty, and stores the result for review.

## 8. Functional Requirements

## 8.1 Authentication and User Management

### FR-AUTH-001: User Login

The system must support secure user login.

Acceptance criteria:

- Users can log in with email and password or an enterprise-ready identity provider configuration.
- Passwords are never stored in plain text.
- Sessions use secure cookies or secure token handling.
- Failed login attempts are rate-limited.

### FR-AUTH-002: Role-Based Access Control

The system must support roles:

- Admin
- Compliance Reviewer
- Case Worker
- Manager
- Read-only Auditor

Acceptance criteria:

- Users only see resources allowed by their role and organization.
- Admins can manage users and role assignments.
- Audit users can inspect logs but cannot edit cases.
- Case Workers cannot approve their own high-risk cases when separation of duties is required.

### FR-AUTH-003: Organization Isolation

The system must support organization-level data isolation.

Acceptance criteria:

- All users belong to an organization.
- Cases, documents, logs, evaluations, and settings are scoped to organization.
- Cross-organization access is blocked by backend authorization checks.

## 8.2 Case Management

### FR-CASE-001: Case Submission

Users must be able to submit a case with:

- Title
- Description
- Domain pack
- Priority
- Language
- Attachments
- Optional due date
- Optional external reference

Acceptance criteria:

- Required fields are validated.
- Norwegian date formatting is supported.
- Submitted cases receive a unique case number.
- Case status is visible in the case inbox.

### FR-CASE-002: Case Inbox

The system must show a case inbox with:

- Case number
- Title
- Status
- Risk level
- Priority
- Assigned user
- Due date
- Last updated time
- Workflow state

Acceptance criteria:

- Users can filter by status, risk, assignee, domain, and priority.
- Users can search by case number or text.
- Managers can view team-level workload.

### FR-CASE-003: Case Status Workflow

Supported statuses:

- New
- Processing
- Waiting for Human Review
- Needs More Evidence
- Approved
- Rejected
- Completed
- Failed
- Archived

Acceptance criteria:

- Status changes are logged.
- Only authorized users can move cases through approval states.
- Failed workflows expose an error summary without leaking secrets.

## 8.3 Document Handling

### FR-DOC-001: Document Upload

Users must be able to upload supported file types:

- PDF
- DOCX
- TXT
- Markdown
- CSV
- XLSX
- EML or pasted email text

Acceptance criteria:

- File type is validated.
- File size limits are enforced.
- Files are scanned and safely stored.
- Unsafe or unsupported files are rejected.
- Uploaded files are linked to organization, user, and case.

### FR-DOC-002: Document Parsing

The system must extract readable text and metadata from uploaded documents.

Acceptance criteria:

- Parsed text is stored separately from raw file storage.
- Document pages or sections are preserved when possible.
- Metadata includes filename, file type, size, checksum, language, page count where available, and upload user.
- Parsing errors are logged and shown in a safe user-facing format.

### FR-DOC-003: Chunking and Indexing

Documents must be chunked and indexed for retrieval.

Acceptance criteria:

- Chunking preserves document identity, page, section, and source location.
- Chunks are embedded and indexed.
- Keyword search indexing is supported.
- Re-indexing is possible when parsing or embedding settings change.

### FR-DOC-004: Source Governance

Documents must have a source status:

- Approved
- Draft
- Deprecated
- Restricted
- Archived

Acceptance criteria:

- RAG answers prefer approved sources.
- Restricted sources require permission.
- Deprecated sources are shown with warning.
- Archived sources are not used unless explicitly selected by authorized users.

## 8.4 RAG and Source-Grounded Answers

### FR-RAG-001: Grounded Question Answering

Users must be able to ask questions about approved knowledge sources.

Acceptance criteria:

- Answers include citations.
- Citations link to document chunks or source excerpts.
- The answer states uncertainty when evidence is incomplete.
- The system refuses to answer when support is insufficient.

### FR-RAG-002: Hybrid Retrieval

The retrieval system must support semantic and keyword retrieval.

Acceptance criteria:

- Vector search is used for semantic matching.
- Keyword search is used for exact terms, legal references, policy names, and numbers.
- Results can be reranked.
- Retrieved source snippets are visible in the evidence panel.

### FR-RAG-003: Citation Verification

The system must verify that answer claims are supported by retrieved sources.

Acceptance criteria:

- Unsupported claims are flagged.
- Final answers contain only source-supported claims unless clearly marked as assumptions.
- Citation coverage is included in evaluation reports.

### FR-RAG-004: Norwegian Query Support

The RAG system must support Norwegian Bokmål queries.

Acceptance criteria:

- Users can ask questions in Norwegian Bokmål.
- The system can retrieve relevant Norwegian and English documents.
- Answers default to the user interface language unless the user requests otherwise.

## 8.5 Agentic Workflow Orchestration

### FR-AGENT-001: LangGraph Workflow Execution

The platform must use LangGraph for deterministic, inspectable agent workflows.

Acceptance criteria:

- Each workflow has typed state.
- Each node has a clear responsibility.
- Node transitions are explicit.
- Workflow execution can be resumed after interruption.
- Every workflow run is logged.

### FR-AGENT-002: Intake Workflow

The intake workflow must classify the case.

Required outputs:

- Detected language
- Case type
- Domain
- Priority
- Risk level
- PII presence
- Suggested workflow
- Human approval requirement

Acceptance criteria:

- Classification result is stored.
- Low-confidence classification is flagged.
- User can correct classification before continuing.

### FR-AGENT-003: Evidence Workflow

The evidence workflow must gather and rank sources.

Required steps:

- Query rewriting
- Retrieval
- Reranking
- Source filtering
- Evidence sufficiency check
- Contradiction check

Acceptance criteria:

- Sources are visible before final answer approval.
- Weak or contradictory evidence routes the case to Needs More Evidence.
- All retrieval steps are logged.

### FR-AGENT-004: Extraction Workflow

The extraction workflow must pull structured fields from documents and case descriptions.

Supported fields:

- People or organization names
- Dates and deadlines
- Amounts
- Reference numbers
- Obligations
- Tasks
- Risks
- Missing information
- Suggested next actions

Acceptance criteria:

- Extracted fields are shown in editable form.
- Low-confidence fields are marked.
- Human edits are logged.

### FR-AGENT-005: Drafting Workflow

The drafting workflow must draft a response, summary, recommendation, or action plan.

Acceptance criteria:

- Drafts are grounded in retrieved sources.
- Drafts use clear Norwegian Bokmål by default.
- Sensitive drafts require approval.
- Drafts can be edited by humans.
- Final output keeps track of AI draft and human edits.

### FR-AGENT-006: Risk and Compliance Workflow

The platform must run risk checks before final output.

Risk checks include:

- PII presence
- Sensitive domain
- Weak evidence
- Contradictory evidence
- Prompt-injection indicators
- High business impact
- Missing required source
- Low confidence
- Policy conflict

Acceptance criteria:

- Risk level is shown in the UI.
- High-risk workflows require approval.
- Risk reasons are listed.
- Risk results are included in audit logs.

### FR-AGENT-007: LangMem-Based Memory

The platform may use LangMem for controlled memory where useful.

Memory must be limited to approved, organization-scoped, auditable use cases:

- User preferences for UI and language
- Organization-approved workflow preferences
- Case-independent reusable process hints
- Feedback patterns from approved evaluations

Acceptance criteria:

- Memory is scoped by organization and user where applicable.
- Memory must not store sensitive personal data unless explicitly allowed by policy and technically justified.
- Users can inspect relevant memory entries where appropriate.
- Admins can disable memory features.
- Memory usage is logged.

## 8.6 Human-in-the-Loop Approval

### FR-HITL-001: Approval Queue

Cases requiring review must appear in an approval queue.

Acceptance criteria:

- Reviewers see risk level, sources, AI draft, extracted fields, and workflow trace.
- Reviewers can approve, edit, reject, or request more evidence.
- Approval decision is logged.

### FR-HITL-002: Approval Interrupt

Agent workflows must pause before sensitive actions.

Acceptance criteria:

- Workflows pause at approval checkpoints.
- State is persisted.
- Reviewers can resume workflow after decision.
- The system never silently bypasses required approval.

### FR-HITL-003: Human Edit Tracking

The system must track edits made to AI-generated drafts.

Acceptance criteria:

- Original AI output is retained.
- Human-edited output is stored separately.
- Edit metadata includes user, time, and reason where provided.
- Evaluation can compare AI draft with final approved result.

## 8.7 Auditability

### FR-AUDIT-001: Audit Log

The system must log important events:

- Login events
- Document uploads
- Case submissions
- Workflow starts and ends
- LangGraph node execution
- Tool calls
- Retrieved sources
- Model calls
- Risk checks
- Human approvals
- Human edits
- Exports
- Permission changes

Acceptance criteria:

- Logs include user, organization, event type, timestamp, and resource reference.
- Logs are immutable from normal application flows.
- Audit users can filter and inspect logs.

### FR-AUDIT-002: AI Action Trace

Each AI workflow run must have a trace view.

Acceptance criteria:

- Trace shows nodes, timing, status, tool calls, model used, token usage, cost estimate, and errors.
- Trace links to retrieved sources.
- Trace excludes secrets and raw credentials.

## 8.8 Evaluation and Quality

### FR-EVAL-001: Evaluation Dataset

The project must include an evaluation dataset with synthetic Norwegian and English cases.

Acceptance criteria:

- Dataset includes questions, expected source references, expected answer criteria, and risk labels.
- Dataset avoids real personal data.
- Dataset covers public sector, banking, energy, and internal policy scenarios.

### FR-EVAL-002: RAG Evaluation

The platform must test retrieval and answer quality.

Metrics include:

- Retrieval precision
- Citation correctness
- Answer faithfulness
- Refusal correctness
- Unsupported-claim rate
- Language quality

Acceptance criteria:

- Evaluation can be run locally and in CI where cost allows.
- Results are stored and visible in evaluation dashboard or report.
- Failed quality thresholds block release in CI for deterministic tests.

### FR-EVAL-003: Prompt Regression Tests

Prompt and workflow changes must be tested against fixed scenarios.

Acceptance criteria:

- Prompt changes run regression checks.
- Important expected behaviors are tested.
- Output changes are reviewed when behavior changes.

### FR-EVAL-004: Cost and Latency Tracking

The system must track cost and latency of AI workflow runs.

Acceptance criteria:

- Token usage is stored where available.
- Estimated cost is stored per run.
- Latency is tracked per workflow node.
- Dashboard shows average and p95 latency.

## 8.9 Dashboards and User Interface

### FR-UI-001: Norwegian Bokmål Default UI

The interface must default to Norwegian Bokmål.

Acceptance criteria:

- Primary labels, navigation, workflow statuses, and user messages are in Norwegian Bokmål.
- English UI option is available.
- Norwegian date, number, and currency formatting are supported.

### FR-UI-002: Case Detail Page

The case detail page must show:

- Case metadata
- Status
- Documents
- Extracted fields
- Evidence panel
- AI draft
- Risk flags
- Approval controls
- Workflow trace link
- Audit events

Acceptance criteria:

- Users can understand why an answer was produced.
- Reviewers can approve or reject from the page.
- Users can inspect cited sources.

### FR-UI-003: Evidence Panel

The evidence panel must show retrieved sources and citations.

Acceptance criteria:

- Source title, document type, page or section, confidence score, and excerpt are shown.
- Users can open source context.
- Deprecated or restricted source warnings are visible.

### FR-UI-004: Evaluation Dashboard

The evaluation dashboard must show:

- Latest evaluation run
- Pass/fail status
- Retrieval metrics
- Citation metrics
- Answer faithfulness metrics
- Latency
- Cost
- Regression failures

Acceptance criteria:

- Admins and technical reviewers can inspect evaluation trends.
- Failed cases link to details.

### FR-UI-005: Accessibility

The UI must follow accessibility and universal design principles.

Acceptance criteria:

- Keyboard navigation is supported.
- Form fields have labels.
- Errors are clear.
- Contrast is readable.
- Important states are not communicated by color alone.
- Pages support semantic HTML structure.

## 8.10 API and Integration

### FR-API-001: OpenAPI Documentation

The backend must expose OpenAPI/Swagger documentation.

Acceptance criteria:

- Main endpoints are documented.
- Request and response schemas are typed.
- Auth requirements are visible.
- Error models are documented.

### FR-API-002: Export

Users must be able to export approved outputs.

Supported export formats:

- JSON
- CSV for structured fields
- PDF report
- Markdown report

Acceptance criteria:

- Exports are logged.
- Exports include source references when relevant.
- Sensitive export requires permission.

### FR-API-003: Mock Enterprise Integrations

The platform must include safe mock integrations for enterprise workflows.

Examples:

- Mock ticket system
- Mock email handoff
- Mock Teams notification
- Mock document archive

Acceptance criteria:

- Mock integrations are clearly marked.
- Tool-call behavior is logged.
- No real external communication is required for the public demo.

## 9. Non-Functional Requirements

## 9.1 Performance

- Case detail pages should load within acceptable interactive limits under demo workload.
- RAG retrieval should respond quickly enough for user-facing workflows.
- Long-running agent workflows must run asynchronously.
- Large document parsing must not block the UI.
- Background workers must handle document indexing and workflow execution.

Target metrics:

- API p95 latency under 500 ms for non-AI endpoints under demo load.
- Retrieval p95 under 2 seconds for indexed demo corpus.
- AI workflow trace visible during or after workflow execution.
- Long-running workflows show progress state.

## 9.2 Reliability

- Health check endpoints must exist for API and worker services.
- Workflow state must persist across interruptions.
- Failed nodes must produce safe errors and logs.
- Retries must be limited and observable.
- File processing failures must not corrupt case state.

## 9.3 Security

- No secrets in repository.
- Environment variables managed through secure configuration.
- Authentication required for all application routes except public health and documentation where allowed.
- Authorization enforced in backend services.
- Input validation for all API requests.
- File upload validation.
- Rate limiting for sensitive routes.
- CSRF protection where relevant.
- Secure headers in production.
- Audit logging for sensitive actions.

## 9.4 Privacy and GDPR-Aware Design

- Use synthetic, public, or anonymized data in demo.
- Store only necessary personal information.
- PII detection must flag sensitive content.
- Access to sensitive cases must be role-restricted.
- Deletion or archival policy must be documented.
- Users must not upload real personal data to public demo.
- Logs must avoid leaking secrets and unnecessary personal data.

## 9.5 Maintainability

- Clear frontend/backend/service boundaries.
- Typed code in frontend and backend.
- Shared schemas where useful.
- Consistent naming conventions.
- Modular LangGraph workflows.
- Documented architecture decisions.
- Automated formatting and linting.
- Testable service design.

## 9.6 Observability

- Structured logs.
- Workflow trace logs.
- Tool-call logs.
- Model-call metadata.
- Cost tracking.
- Latency tracking.
- Error tracking.
- Health checks.
- Optional OpenTelemetry tracing.

## 9.7 Deployment

The system must support:

- Local environment through Docker Compose
- Staging environment
- Production environment
- HTTPS in deployed environments
- Environment-specific configuration
- Secure secrets handling
- Automated deployment pipeline
- Database migrations

## 10. Data Requirements

## 10.1 Data Categories

The platform stores:

- Organizations
- Users
- Roles
- Cases
- Documents
- Parsed document text
- Document chunks
- Embeddings
- Workflow runs
- Workflow node runs
- Agent messages
- Retrieved sources
- Extracted fields
- Risk assessments
- Approvals
- Audit events
- Evaluation datasets
- Evaluation runs
- Prompt versions
- Model usage records

## 10.2 Data Retention

Retention settings must be configurable by organization.

Default retention assumptions:

- Audit logs retained for long-term traceability.
- Raw uploaded files can be deleted or archived based on policy.
- Evaluation datasets retained unless manually removed.
- AI traces retained for review and debugging, with privacy safeguards.

## 11. Success Metrics

## 11.1 Product Success Metrics

- Percentage of cases with source-grounded AI output.
- Percentage of high-risk cases routed to human approval.
- Average case processing time compared to manual workflow estimate.
- Number of unsupported-answer refusals correctly triggered.
- Number of human edits per AI draft.
- Evaluation pass rate.
- Retrieval quality trend.
- Cost per completed workflow.
- p95 workflow latency.

## 11.2 Engineering Success Metrics

- CI pipeline passes.
- Unit and integration test coverage meets documented threshold.
- API tests pass.
- RAG evaluation tests pass.
- No high-severity dependency vulnerabilities allowed in release.
- No secrets in repository.
- Deployment pipeline works for staging and production.
- Health checks pass.
- Architecture and deployment docs are up to date.

## 12. Acceptance Criteria for Final Project

The project is complete when:

1. A deployed HTTPS demo environment exists.
2. Local setup works with Docker Compose.
3. Staging and production configuration are separated.
4. Authentication and RBAC are functional.
5. Users can upload documents and submit cases.
6. Documents are parsed, chunked, embedded, indexed, and searchable.
7. LangGraph workflows run for intake, retrieval, extraction, risk checking, drafting, and approval.
8. Human approval interrupts are functional.
9. AI outputs include citations and evidence.
10. Weak evidence triggers refusal or Needs More Evidence state.
11. Audit logs capture important application and AI events.
12. Evaluation tests run for RAG and agent behavior.
13. Cost and latency tracking are visible.
14. CI/CD runs linting, type checks, tests, dependency checks, Docker build, and deployment.
15. README, architecture documentation, security notes, testing guide, and deployment guide are present.
16. The GitHub repository has screenshots, architecture diagram, demo instructions, and known limitations.
17. The system uses synthetic or safe demo data only.
18. The UI is primarily Norwegian Bokmål with English option.
19. The platform demonstrates Norwegian enterprise, public-sector, banking, or energy relevance.
