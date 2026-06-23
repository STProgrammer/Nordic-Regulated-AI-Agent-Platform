# Phase 22 — Human Approval Workflow

## Phase objective

Implement the durable human-in-the-loop approval boundary for AI-assisted case work. A completed Risk and Compliance assessment that requires approval must add a tenant-scoped review packet, pause the approval workflow, place the case in a reviewer queue, and prevent any final outcome until an authorized reviewer acts. Reviewers must be able to approve, edit and approve, reject, request more evidence, or reassign a pending review. Every action must be authorized, race-safe, auditable, and resume the paused workflow to the corresponding controlled outcome.

This phase makes the human—not the model—the final decision-maker for sensitive or low-confidence work. It retains the immutable original AI draft separately from the final human-approved text and keeps all approval decisions within organization and RBAC boundaries.

## Relevant context and constraints

- The roadmap requires an approval queue, review packet, workflow interruption and resume, approve, edit-and-approve, reject, request-more-evidence, and reassign actions. High-risk and low-confidence output must not bypass required approval. Integration and Playwright tests must cover the case-worker-to-reviewer flow, edits, rejection, and more-evidence paths.
- PRD `FR-HITL-001` requires reviewers to see the risk level, sources, AI draft, extracted fields, and workflow context before deciding. `FR-HITL-002` requires persisted interruption and reviewer-driven resume, with no silent approval bypass. `FR-HITL-003` requires original AI output, human-approved output, reviewer identity, timestamp, and optional reason to be retained separately.
- The architecture fixes the Human Approval Graph sequence: `prepare_review_packet`, `interrupt_for_human_review`, `handle_approval`, `handle_rejection`, `handle_edit`, `handle_more_evidence_request`, and `resume_workflow`. Keep these explicit responsibilities; do not turn this phase into an unstructured collection of route-side mutations.
- Phase 20 owns the immutable, citation-validated original `AgentMessage` draft and its source provenance. Phase 21 owns final risk assessment and the server-owned `requires_approval` decision. Phase 22 consumes those persisted records; it must never accept a draft, risk level, source list, workflow state, reviewer identity, or approval requirement from the browser.
- Existing `cases` transitions already reserve `waiting_for_human_review -> approved | rejected | needs_more_evidence`. Approval service code must be the only path that performs those terminal reviewer transitions. Generic case update endpoints must not become a workaround for the approval boundary.
- Existing roles establish `Admin` and `Compliance Reviewer` as the approval-capable roles. Case Workers, Managers, and Read-only Auditors must not decide, edit-and-approve, or reassign approvals. Enforce all permissions in backend services and routes; client-side role checks are presentation only.
- The current `approvals` router is intentionally empty, the `approvals` table is an early schema placeholder, and the generic `GraphRuntime` only supports terminal runs. This phase must add the minimal typed persistence and runtime extension needed for a durable paused approval run rather than faking a pause in browser state or a Celery payload.
- All current project conventions remain in force: opaque cookie authentication, organization-scoped SQL queries, strict Pydantic/Zod contracts, UUID-only worker messages, bounded safe snapshots, structured audit events with no raw sensitive content, deterministic/local automated testing, and no secrets in logs, snapshots, API errors, or browser storage.

## In-scope deliverables

1. A typed Human Approval Graph and a durable interruption/resumption mechanism that persists a paused approval run and can safely resume it from one server-validated reviewer action.
2. A review-packet addition flow for a case whose latest eligible risk assessment requires approval. It must bind the review to the protected original draft, its source references, latest eligible extracted fields, and risk assessment without trusting client-provided values.
3. Approval persistence and migration support for a pending queue item, assignment/reassignment, decision state, reviewer metadata, immutable original AI draft, separately stored final human text, timestamps, and suitable tenant/query indexes.
4. An organization-scoped approval service/repository and protected REST contracts for queue listing, review-packet detail, approve, edit-and-approve, reject, request-more-evidence, and reassign.
5. Explicit backend authorization and separation-of-duties protections, including protection against self-approval of a high-risk case by its originating Case Worker and against an unauthorized/foreign/inactive assignee or reviewer.
6. Transactional state changes that update the approval record, paused workflow run, case status, and audit event together and are idempotent under browser retries, duplicate broker delivery, and concurrent reviewer attempts.
7. A localized, accessible Approval Queue page and case-detail approval panel/review packet. Both Bokmål and English must make the paused/non-final state, assigned reviewer, action outcome, review reasons, and finality clear.
8. Focused unit, API, integration, web, and Playwright coverage using synthetic fixtures only, plus documentation for the local reviewer demonstration flow.

## Out of scope

- Full workflow trace browsing, raw node/tool/model logs, trace filtering, and a generic `/trace` UI or API; these belong to Phase 23. The Phase 22 review packet may show only the bounded status/provenance summary required to make a decision, never a substitute trace explorer.
- LangMem or reviewer-feedback learning, memory storage, or memory-driven routing; this is Phase 24.
- Evaluation datasets, automated evaluation comparison of draft/final text, dashboards, metrics, cost/latency dashboards, exports, notification integrations, and enterprise handoffs; these begin in Phases 25–28.
- New model-provider calls, redrafting logic, citation generation, retrieval changes, document parsing, or risk-policy redesign. `request_more_evidence` ends the approval flow in the controlled `needs_more_evidence` state; it does not silently invoke a fresh Evidence or Drafting run.
- A general workflow cancellation/resume API for every graph, custom user-defined approval rules, multi-stage approval chains, delegations outside the tenant, or notification delivery. Reassignment is limited to a pending Phase 22 review and an active, approval-capable same-organization user.
- Case completion, export, external sending, or treating an approved result as an autonomous action. `approved` means human-approved within the case lifecycle; later phases own downstream use and integrations.
- Broad audit-trail presentation. Record the required approval events now, but leave audit/trace browsing for Phase 23.

## Likely files, folders, modules, and services affected

- `apps/api/migrations/versions/` — one additive Alembic revision for approval lifecycle/assignment fields, constraints, and indexes.
- `apps/api/src/app/db/models/workflow.py`, `apps/api/src/app/db/repositories/` — evolve `Approval`; add a narrowly scoped approval repository rather than scattering approval queries through routes.
- `apps/api/src/app/services/approvals/` — new approval policy, service, and typed commands/read models; reuse existing case, identity, workflow, audit, and authorization services.
- `apps/api/src/app/services/auth/policy.py` and `apps/api/src/app/services/cases/` — only the minimal shared authorization/lifecycle additions needed to reserve approval-state transitions for the approval service.
- `apps/api/src/app/services/workflows/`, `apps/api/src/app/workers/tasks.py`, and `apps/api/src/app/workers/celery_app.py` — approval-run dispatch/resume handling, UUID-only messages, and safe paused-run lifecycle support.
- `apps/api/src/app/api/routes/approvals.py`, `apps/api/src/app/api/schemas/approvals.py`, `apps/api/src/app/api/schemas/workflows.py`, and existing route/schema registries — closed request/response DTOs and the established `/api/approvals` boundary.
- `services/agent_orchestrator/src/agent_orchestrator/graphs/approval_graph.py`, `approval_types.py`, `runtime.py`, persistence ports, and snapshot allowlists — the typed graph and the minimal safe interrupt/resume semantics.
- `apps/api/tests/` and `services/agent_orchestrator/tests/` — graph, service, API, migration/integration, authorization, concurrency/idempotency, and audit tests.
- `apps/web/src/app/[locale]/approvals/page.tsx`, `apps/web/src/components/approval/`, `apps/web/src/components/cases/case-detail.tsx`, `apps/web/src/lib/api/approvals.ts`, `contracts.ts`, query hooks, tests, and `messages/nb.json` / `messages/en.json` — queue, review packet, case-detail controls, strict API contracts, and localization.
- `apps/web/e2e/` and `docs/development.md` (or the existing local validation guide) — synthetic end-to-end flow and manual review instructions.

Exact filenames may follow established module naming, but preserve the existing router ownership, API client boundary, service-layer pattern, and localized component conventions.

## Implementation tasks

### 1. Define the approval lifecycle and closed contracts first

1. Introduce closed typed enums and Pydantic/Zod schemas for:
   - approval lifecycle (`pending`/`assigned`/`approved`/`rejected`/`needs_more_evidence` as appropriate to the final model);
   - reviewer decisions (`approve`, `edit_and_approve`, `reject`, `request_more_evidence`);
   - strict action requests with an optional bounded reviewer comment, bounded final text only for `edit_and_approve`, and a UUID target only for reassign;
   - safe queue-item, review-packet, and action-result response DTOs.
2. Make each action endpoint explicit rather than accepting a free-form action discriminator that could be extended accidentally. For example, retain the architecture-aligned approve, reject, and request-more-evidence paths and add explicit edit-and-approve and reassign paths beneath `/api/approvals/{approval_id}`.
3. Reject unknown keys, blank/oversized final text or comments, malformed UUIDs, final text on non-edit actions, and browser-supplied case/risk/draft/source/workflow/actor fields. Do not expose internal snapshots, prompt/provider details, raw model output metadata, hidden source content, numerical score/cost/token data, or exception text.
4. Extend workflow status/read projection only as required to represent `waiting_for_human_review` safely. Queue and detail contracts must be purpose-built; do not overload the generic workflow status DTO with raw review packet content.

### 2. Make approval persistence represent a real pending review

1. Add an additive Alembic migration that evolves the placeholder `approvals` table into a pending-review record. It must be able to exist before a decision, record assignment/reassignment separately from the final decision actor, and enforce the tenant/case/workflow/user relationships with foreign keys and indexes.
2. Keep the original AI text immutable and separate from final human text. Preserve the existing protected Phase 20 `AgentMessage` as the source of truth and pin the review to its drafting run. Persist the original text/snapshot needed for the durable approval record in `ai_draft`; persist only human-approved edited text in `final_text`. An unchanged approval has no human rewrite; it must not mutate the original AI draft.
3. Store decision, reviewer user, optional reviewer comment, assignment history or safely modeled current assignment, and decision timestamps so the final record can be audited. Use nullable fields and database constraints that accurately model a pending review; never invent a reviewer or decision to satisfy an old non-null placeholder.
4. Add a uniqueness/locking strategy that allows at most one active approval for the eligible approval workflow/case at a time, while retaining completed historical approval records. Add deterministic queue ordering and indexes for organization + active state + assignment + addition time.
5. Keep text and review-packet payloads out of generic workflow state snapshots and audit `event_data`. Snapshot only bounded lifecycle flags, IDs/counts, decision code, and safe reason codes needed for status projections.

### 3. Build the typed Human Approval Graph with durable interruption

1. Add `approval_types.py` with a strict, server-constructed state that contains trusted identifiers and closed outcome codes only. Keep raw draft text, source excerpts, extracted-field values, comments, and final human text in protected persistence ports—not in graph state, Celery arguments, or snapshots.
2. Implement `ApprovalGraph` with the architecture-prescribed responsibilities in their deterministic order:
   - `prepare_review_packet` revalidates the current tenant-scoped prerequisites and adds/returns one durable pending approval record;
   - `interrupt_for_human_review` persists the checkpoint, marks the workflow and case as waiting for human review, and returns without a terminal decision;
   - `handle_approval`, `handle_rejection`, `handle_edit`, and `handle_more_evidence_request` consume only a locked, server-validated decision command;
   - `resume_workflow` persists the matching terminal approval outcome and safe status projection.
3. Extend the shared graph runtime/persistence interface narrowly so a worker can atomically transition `queued -> running -> waiting_for_human_review`, later claim a paused run for a single resume, and finish it once. Preserve existing graph behavior and test it to prevent regressions.
4. A reviewer action must not place raw action data on the queue. Persist the validated decision in the same database transaction as the approval lock/state update, then enqueue only the workflow-run UUID for resumption. Duplicate resume delivery must be a no-op.
5. If review-packet preparation finds stale/missing/archived prerequisites, unavailable protected draft/provenance, or a risk assessment that does not require approval, fail closed without opening a queue item or changing the case to approved. Give only safe reason categories to authorized callers.

### 4. Implement review packet assembly and approval service policy

1. Add a dedicated approval service/repository that loads all resources by `organization_id` and locks the approval row for mutation. Route handlers stay thin and never directly alter case status or approval columns.
2. Allow approval initiation only after the latest completed Phase 21 assessment for the case is eligible and has `requires_approval=True`. Verify the linked original drafting run, evidence/source provenance, and case are still readable/current before constructing the review packet.
3. Build a bounded review packet from server-owned persisted data: case identity/status, final risk level/reason codes, protected original AI draft, citation labels with authorized source-context references, latest eligible extracted fields, assignment state, and a minimal workflow lifecycle summary. Do not provide raw workflow trace, model settings, prompt text, internal policy calculation, unrestricted document text, or cross-tenant source data.
4. Queue visibility and all review actions require an active `Admin` or `Compliance Reviewer` in the organization. The queue is filtered to pending items the principal is allowed to view; action authorization additionally requires that the reviewer is the current assignee when an assignment exists. Case Workers, Managers, and Read-only Auditors receive no approval decision capability.
5. Reassignment is permitted only while pending, only to an active same-organization user holding an approval-capable role, and never to a foreign, inactive, or unauthorized identity. Record the actor and target in a safe audit event. A reassignment leaves the workflow interrupted.
6. Enforce separation of duties server-side for high-risk/mandatory-approval records. At minimum, a user who submitted or originated the protected high-risk AI workflow cannot approve that same case; do not rely on the Case Worker UI hiding a button. Define the exact trusted origin fields used by the policy, document the choice, and cover both multi-role and direct API attempts.
7. On approve: retain the original draft, record the final reviewer decision, resolve the approval graph as `approved`, and move the case `waiting_for_human_review -> approved` transactionally.
8. On edit-and-approve: validate and store the human final text separately from the original AI draft, record that this was an edit, resolve as `approved`, and move the case to `approved`. Do not overwrite the `AgentMessage`, its provenance, or citations.
9. On reject: store the decision/comment, resolve the paused graph as `rejected`, and move the case to `rejected`. No final approved text is added.
10. On request more evidence: store the decision/comment, resolve the paused graph as `needs_more_evidence`, and move the case there. Do not auto-run evidence/drafting or fabricate a final text; a later authorized workflow operation can produce new evidence.
11. Record content-free, transactionally consistent audit events for addition/interrupt, assignment/reassignment, decision submitted, workflow resumed, and each terminal outcome. Preserve the audit actor, approval/resource IDs, case ID, workflow name/status, decision code, and safe reason codes only.

### 5. Add protected API routes and worker composition

1. Replace the Phase 22 approvals placeholder description with the real stable API boundary, retaining `/api/approvals` as the sole approval route group. Implement queue/list, one protected review-packet read, and explicit actions under it. Use the established `require_current_principal` dependency and response envelope/error model.
2. Add only the smallest workflow start/action surface necessary to add a required approval checkpoint. It must be server-selected from the risk result rather than a client command to approve arbitrary cases. Do not add a browser-visible generic `resume` endpoint.
3. Update orchestration dispatch and worker tasks to use UUID-only approval workflow messages, finite retries, scoped session reloads, locks/claims, safe failure states, and engine disposal. A worker failure must not turn a pending review into approval or expose error content.
4. Ensure OpenAPI documents the protected operations, strict request fields, successful safe projections, and expected unauthorized/not-found/conflict/validation responses without leaking implementation details.

### 6. Deliver the localized accessible approval experience

1. Replace `apps/web/src/app/[locale]/approvals/page.tsx` with a protected Approval Queue. It must present pending review items, risk/status, assignment, case identity, deterministic ordering, empty/loading/error states, and a link to the review packet. It must not put approval data in local/session storage.
2. Add a review-packet component/page that exposes only the protected fields: risk level/reasons, original AI draft clearly labelled non-final, bounded source links using the existing authorized context dialog, extracted fields, assignment, and action controls. Avoid a Phase 23 trace browser; show only a concise lifecycle/provenance summary.
3. Add a case-detail approval section that appears only when the server reports a pending/terminal approval relevant to the case. It should make the current `waiting_for_human_review`, approved, rejected, or needs-more-evidence state clear and link reviewers to the same review packet. Replace the obsolete approval placeholder card only; keep unrelated future UI areas as honest placeholders.
4. Make approve/reject/request-more-evidence/reassign/edit-and-approve safe, deliberate interactions: confirmation before terminal actions, textarea labels/instructions, validation/error recovery, disabled pending state, query invalidation after action, and no optimistic claim that the workflow resolved before the server confirms it.
5. Provide complete Bokmål-default and English messages, semantic headings/forms/labels, visible keyboard focus, `aria-live` status feedback, non-color-only risk/decision state, accessible dialogs/confirmations, and proper focus restoration. Do not display hidden source/extracted data to a role that the API does not authorize.

### 7. Document the limited, verifiable Phase 22 operation

1. Update the developer/local validation documentation with the synthetic-only flow: add an eligible case, run the prerequisite workflow sequence, reach `waiting_for_human_review`, use a distinct reviewer session, approve/edit/reject/request more evidence, and inspect only safe API/UI results.
2. State that human approval is required for records flagged by Phase 21 and that Phase 22 does not send/export/finalize external actions, expose a full trace, or use real personal data/model credentials for automated validation.

## Required tests

### Agent orchestration and policy tests

- The Human Approval Graph exposes the seven architecture-defined responsibilities in the documented order; state and decision types reject unknown keys, malformed IDs, invalid lifecycle transitions, raw text in state, and unsupported actions.
- The graph persists an interrupt checkpoint and a safe `waiting_for_human_review` projection, then resumes exactly once for approve, edit-and-approve, reject, and request-more-evidence outcomes.
- A stale/missing risk assessment, `requires_approval=False`, missing/invalid immutable draft, stale source provenance, archived case, or malformed resume command fails closed without queue addition or case approval.
- Existing non-approval graphs and the normal queued/running/completed/failed runtime lifecycle remain unchanged by the pause/resume extension.
- Duplicate dispatch/resume delivery, retry after a worker error, and concurrent resume attempts cannot produce multiple decisions or multiple terminal transitions.

### Service, persistence, and API tests

- Migration tests apply to an empty database and upgrade existing Phase 21 schema correctly; constraints/indexes support pending, assigned, and terminal approval records without breaking historical fields.
- Queue and review packet enforce cookie authentication, tenant scoping, active approval-capable roles, case visibility, assignment restrictions, archived/missing behavior, and deterministic pagination/order.
- Direct API attempts by Case Worker, Manager, Read-only Auditor, foreign tenant, inactive/unauthorized assignee, or an originator forbidden by high-risk separation-of-duties policy are rejected without disclosure or state changes.
- Every action validates strict payloads and permissible state: approve has no replacement text; edit-and-approve requires bounded valid final text; reject/request-more-evidence do not add final text; reassign cannot decide or resume the workflow.
- Approve, edit-and-approve, reject, and request-more-evidence each atomically update approval, workflow, case status, and audit event. Repeated submission returns a safe conflict/no-op and never duplicates final text or audit decision records.
- Original draft content/provenance remains unchanged after every action. An edited final text persists separately with reviewer/time/comment metadata; unchanged approve has no fabricated human edit.
- Queue/read/action API responses exclude raw state snapshots, prompt/provider/model metadata, traces, unsafe source content, secrets, error internals, browser-controlled fields, and cross-tenant identifiers.
- Content-free approval audit events are emitted for queueing/interruption, reassignment, each decision, resume, and terminal outcome with the correct actor/resource/case linkage.
- Existing authentication, RBAC, cases, workflows, drafting, evidence, risk, audit, router registry, and OpenAPI contract tests remain green.

### Web and end-to-end tests

- Zod/API client tests reject malformed approval DTOs and send only the closed action payloads; query cache invalidation and terminal/pending polling cleanup are tested.
- Component tests cover Bokmål and English queue/review packet rendering, loading/empty/error states, role-gated controls, assigned/unassigned state, risk reasons, immutable original draft, source-context keyboard access, action confirmation, field validation, and accessible status feedback.
- Verify the case-detail view correctly changes from waiting for review to approved/rejected/needs more evidence without showing an unsafe final-text editor to unauthorized users.
- Playwright uses synthetic data and separate case-worker/reviewer sessions to cover the full queue flow, an edit-and-approve preserving the original draft, rejection, request-more-evidence, reassignment, unauthorized/self-approval denial, and source-context access. It must assert that no action bypasses the required review checkpoint.

## Validation steps

Run focused checks first; only proceed to broader and full validation after they pass.

```bash
# Focused graph, API, and UI checks
uv run pytest services/agent_orchestrator/tests/test_approval_graph.py
uv run pytest apps/api/tests/api/test_approvals.py apps/api/tests/integration/test_approval_service.py
pnpm test:web -- approval

# Broader affected suites and static checks
uv run pytest services/agent_orchestrator/tests
uv run pytest apps/api/tests/api apps/api/tests/integration
pnpm test:web
pnpm lint
pnpm typecheck
pnpm format:check
pnpm check:workspace

# Full migration/local-stack/browser validation
pnpm dev:up
docker compose --env-file .env.example exec api uv run alembic upgrade head
docker compose --env-file .env.example exec api uv run alembic current
pnpm verify:local-stack
pnpm test:e2e
pnpm dev:down
git diff --check
```

Manual synthetic-only validation after the automated checks:

1. Start the local stack and open `http://127.0.0.1:3000/nb/approvals` in a reviewer session.
2. Add or use a synthetic case with a valid completed Evidence/Drafting/Risk sequence whose risk assessment requires approval. Confirm the case becomes `Waiting for Human Review` and appears exactly once in the queue.
3. Open the review packet. Confirm it shows bounded risk reasons, original AI draft, source-context links, extracted fields, assignment state, and only a concise workflow status summary—no raw trace, secret, prompt, or provider data.
4. With a distinct approval-capable reviewer, exercise approve and edit-and-approve. Confirm the original draft remains available unchanged, only the edited path stores separate final human text, and the case becomes `Approved`.
5. Repeat with synthetic cases for reject and request-more-evidence; confirm `Rejected` and `Needs More Evidence` respectively, no final approved text, and no automatic fresh Evidence/Drafting run.
6. Reassign a pending item to an active same-organization reviewer and confirm only the assignee can decide. Verify a Case Worker/originator/self-approval attempt is denied.
7. Repeat one terminal action in English at `http://127.0.0.1:3000/en/approvals`, checking localized text, keyboard navigation, focus, and non-color-only status cues. Inspect protected endpoint contracts at `http://127.0.0.1:8000/docs` without printing credentials, cookies, raw case text, or drafts.

## Validation Plan

### Focused validation

- Run the new approval graph, approval service/API, migration, and approval component/client tests.
- Exercise each terminal decision and reassign path with deterministic synthetic fixtures, including repeat/concurrent action safety and separation-of-duties denial.
- Confirm the API/OpenAPI contract rejects extraneous fields and emits only safe queue/review packet/action projections.

### Broader validation

- Run all agent-orchestrator tests and affected API/integration suites, then the complete frontend unit suite.
- Run formatting, lint, type checking, and workspace-contract checks to catch cross-package status/schema/runtime changes.
- Confirm existing Risk, Drafting, Cases, Auth/RBAC, Audit, router-registry, and OpenAPI coverage has not regressed.

### Full validation

- Bring up the local stack, apply and inspect the migration, run the local-stack verifier, and execute the synthetic Playwright approval flow.
- Perform the two-session manual Bokmål/English reviewer check described above after the automated browser tests pass.
- Shut the stack down cleanly and run `git diff --check` before marking the phase complete.

## Completion criteria

- A latest eligible risk result with `requires_approval=True` reliably produces one tenant-scoped pending approval and a persisted interrupted workflow/case state; no unapproved path can produce a final outcome.
- Authorized Admins and Compliance Reviewers can view the correct queue/review packet and, subject to assignment and separation-of-duties rules, approve, edit-and-approve, reject, request more evidence, or reassign a review.
- Each reviewer action resumes the paused workflow exactly once, reaches the correct case/approval terminal state, and is transactionally audit logged without unsafe payloads.
- The original Phase 20 AI draft and its provenance remain immutable. Edited final human text is stored independently with correct reviewer metadata; rejected/more-evidence actions have no final approved text.
- All data access, queue visibility, assignments, sources, draft reads, and mutations are organization-scoped and backend-authorized. Foreign, inactive, unauthorized, malformed, stale, duplicated, and self-approval attempts fail safely.
- The Approval Queue, review packet, and case-detail status are localized, accessible, truthful about non-final/terminal state, and supported by automated UI and Playwright coverage.
- Required focused, broader, and full validation commands pass. Only then may a later implementation turn mark Phase 22 `(DONE)` in `specs/roadmap.md` and update `specs/progress.md`.

## Risks, dependencies, and notes for the implementation agent

- Phase 21 is a hard prerequisite. Treat its persisted `requires_approval` and safe state as the server-owned gate; do not let a route/UI choose whether a case needs review. If Phase 21 work is not yet validated, do not claim Phase 22 implementation complete.
- The current generic graph runtime is terminal-only. Extend it carefully for a durable paused state with explicit locking/claim semantics; do not simulate interruption with a long-running worker, in-memory event, browser polling state, or an unbounded queue message.
- Review actions are high-integrity mutations. Use database transactions/row locks, idempotency behavior, and queued UUID-only resume work to defend against double-clicks, retries, two reviewers, and delayed deliveries.
- Preserve Phase 20's source-grounded draft contract. A reviewer may alter final wording only through the dedicated edit-and-approve field; they may not inject source IDs, risk decisions, workflow routes, provider settings, or trace payloads.
- The requirements call for reviewer context, while Phase 23 owns trace views. Keep Phase 22's packet bounded to decision-relevant lifecycle/provenance fields and safe source-context links; do not prematurely ship a raw trace endpoint or screen.
- Do not weaken the case status policy to make the UI convenient. Approval transitions must remain reserved for the approval service, and `request_more_evidence` must not silently re-run prior graphs.
- Use synthetic safe fixtures and deterministic/local providers only in automation. Do not log or manually paste cookies, credentials, raw drafts, source text, prompts, or provider configuration into test output or documentation.
- This is a plan-generation task only. Do not mark roadmap/progress status, modify application source, or implement Phase 22 while adding this file.
