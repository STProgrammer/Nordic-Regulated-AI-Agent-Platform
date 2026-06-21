# Phase 21 — Risk and Compliance Graph

## Phase objective

Deliver the asynchronous Risk and Compliance Graph that performs the platform's final, deterministic compliance assessment of an eligible case workflow. It must consolidate trustworthy prior signals, revalidate the draft/evidence boundary, assign a final `low`/`medium`/`high` risk level, record closed risk reasons and an approval requirement, persist a tenant-scoped `risk_assessments` record, and show a truthful localized assessment on Case Detail.

This phase is a risk-routing boundary. It may say that a draft needs more evidence or mandatory human review, but it must not create an approval, pause/resume a graph for a reviewer, let a human edit or finalize a draft, or expose an audit trace.

## Relevant context and constraints

- The roadmap requires final checks for PII, weak or contradictory evidence, prompt-injection indicators, high-impact actions, missing required sources, low confidence, and policy conflicts; it also requires risk-reason display and audit entries. PRD `FR-AGENT-006` additionally calls out sensitive domains. High-risk workflows must require approval.
- Architecture §7.6 fixes the graph order and responsibilities: `check_pii_policy`, `check_weak_evidence`, `check_high_impact_action`, `check_policy_conflict`, `check_prompt_injection_result`, `assign_final_risk`, and `decide_approval_requirement`. Keep those seven explicit nodes; express the additional roadmap checks as bounded inputs/reason codes inside their appropriate node rather than adding an uncontrolled parallel graph.
- Phase 16 supplies the typed LangGraph runtime, safe snapshots, bounded retries, model/provider ports, and UUID-only orchestration pattern. Phases 17–20 are completed prerequisites: Intake provides preliminary PII/injection/low-confidence signals; Evidence owns evidence sufficiency and contradictions; Extraction owns typed fields; Drafting owns the immutable, protected original AI draft and copied source provenance.
- The final assessment must be built only from tenant-scoped persisted records. The browser cannot supply risk facts, policy text, source IDs, model settings, action classifications, or an override. Recheck the selected Drafting run and its current Evidence provenance in the worker so a stale/foreign/unsafe prerequisite cannot become a final risk result.
- Use one documented, closed, server-owned policy matrix. It maps trusted boolean/category signals to closed reason codes, final risk, `requires_approval`, and one safe next state. It must be deterministic and unit-tested; do not use a free-form model rationale, a client score, or an unimplemented generic policy engine as the compliance decision maker.
- `risk_assessments` and `cases.risk_level` already exist. Persist only the existing safe booleans plus bounded reason-code metadata in `risk_reasons`; add a narrowly justified migration only if a required integrity constraint/index cannot be expressed through existing structures. Never place draft text, case descriptions, source excerpts, prompts, model output, raw policy analysis, credentials, or exceptions in snapshots, normal logs, audit metadata, or the risk-reason JSON.
- Phase 22 exclusively owns approvals, reviewer queues, interruptions/resumption, reassign/reject/request-more-evidence decisions, human final text, and edit-and-approve. Phase 23 owns the trace/audit browsing UI. This phase may display the final risk result and a non-actionable review-required notice only.

## In scope

1. A typed seven-node Risk and Compliance LangGraph with a closed policy matrix and safe terminal outcomes.
2. Server-owned loading/revalidation of the latest eligible original draft, Evidence result/provenance, Intake result, and bounded Extraction metadata needed for closed high-impact/policy checks.
3. Tenant-safe persistence of one final assessment per successful risk run, safe `cases.risk_level` projection, workflow/node lifecycle data, and content-free audit events.
4. Closed start/status/assessment-read API contracts, UUID-only task dispatch, and a dedicated worker execution path.
5. A localized, accessible, read-only Case Detail Risk and Compliance panel that accurately shows final risk, reason categories, and whether review will be required later.
6. Deterministic fixtures, comprehensive graph/API/worker/web/E2E coverage, necessary non-secret configuration/documentation, and full local validation.

## Out of scope

- Changing Intake classification, PII/injection detection, Evidence retrieval/reranking/contradiction ownership, Extraction editing, Draft generation, citation validation, or direct-RAG behavior.
- Reviewer queues or packets; creating `approvals` rows; approval/rejection/reassignment/request-more-evidence actions; graph interrupts/checkpoints/resume; human draft edits; final approved output; case lifecycle decisions beyond the safe risk-level projection.
- A general policy-management UI/API, organization-specific editable rules, policy-document ingestion/search, LangMem, evaluation, export, notifications, trace/audit UI, streaming, cancellation, or external integrations.
- Any client-controlled risk override, free-text policy reason, raw model rationale, numeric score/cost/token display, or browser storage of protected workflow/draft content.

## Likely files and ownership

| Area | Likely files/folders | Phase-21 responsibility |
| --- | --- | --- |
| Risk graph and policy | `services/agent_orchestrator/src/agent_orchestrator/graphs/risk_*.py`, `state/`, prompt/provider contracts only if genuinely needed | Typed closed inputs/state/results and the seven architecture-defined nodes; deterministic policy mapping. |
| Workflow service/persistence | `apps/api/src/app/services/workflows/risk*.py`, `orchestrator.py`, existing workflow/case repositories and `db/models/workflow.py` | Eligibility loading, atomic assessment/risk-level persistence, safe projections, and idempotency. |
| API and worker | `api/schemas/workflows.py`, `api/routes/workflows.py`, dependency wiring, `workers/tasks.py`, `services/workflows/dispatch.py` | Closed `risk_compliance` lifecycle/read contracts and UUID-only task execution. |
| Web | `apps/web/src/components/cases/**`, `lib/api/risk*.ts`, `lib/api/contracts.ts`, locale messages and tests | Read-only localized final-risk presentation and active-run polling. |
| Tests/docs | Agent/API/web/E2E suites, local-stack docs/configuration | Deterministic safe scenarios and documented validated behavior. |

## Implementation tasks

1. **Define the trusted prerequisite and policy boundary.** Establish a server-side loader for the case, latest completed protected Drafting run, its eligible Evidence package/source provenance, latest relevant Intake result, and only the bounded Extraction facts that the fixed policy needs. Define whether an absent, stale, contradictory, insufficient, source-incomplete, or otherwise ineligible prerequisite becomes `needs_more_evidence` before the graph executes. Never reconstruct these facts from browser input or a raw state snapshot.

2. **Make risk types closed and portable.** Add typed enums/models for the workflow identifier/version, final risk level, safe next state, closed reason codes, and assessment result. Include reason codes covering PII/sensitive-domain policy, weak evidence, contradictory evidence, missing required source, Intake low confidence, high-impact action, policy conflict, and prompt injection. Reject extra fields, arbitrary policy IDs, user-authored reasons, unknown risk levels, and raw text. Reuse the established `CaseRiskLevel` semantics rather than creating a competing risk vocabulary.

3. **Write and test one deterministic policy matrix.** Document in code which trusted signals each check consumes, which reason codes it may emit, which combinations force `needs_more_evidence`, and which combinations force `high` plus `requires_approval=True`. At minimum, high risk must require approval; no path may make a required-approval case appear safe. Treat unresolved/invalid policy input conservatively. Sensitive-domain and high-impact classification must be derived from existing server-owned closed case/draft/extraction categories, never an LLM's unbounded interpretation of draft text.

4. **Implement the seven explicit nodes in architecture order.**
   - `check_pii_policy` evaluates persisted Intake PII and the case's closed domain/confidentiality policy.
   - `check_weak_evidence` reuses the completed Evidence outcome/provenance to flag insufficient, contradictory, or required-source-missing conditions; it must not rerun retrieval or contradiction analysis.
   - `check_high_impact_action` evaluates only policy-approved, bounded action/domain signals from the trusted inputs.
   - `check_policy_conflict` applies the fixed local policy matrix to existing classifications and validated metadata; it does not introduce document search or free-form legal/compliance advice.
   - `check_prompt_injection_result` consumes the persisted Intake signal rather than re-parsing user/document content.
   - `assign_final_risk` combines closed signals/reasons deterministically and produces one final level and safe next state.
   - `decide_approval_requirement` derives an irreversible-for-this-run boolean from final risk/reasons and safe next state. It only records the requirement; it creates no approval or interrupt.

5. **Persist results atomically and idempotently.** Create a `risk_compliance` workflow run/version with normal safe node records. For completed assessments, insert exactly one tenant/case/run-bound `RiskAssessment`, store only closed reason codes/booleans, and project the final level to `Case.risk_level` in the same transaction. Persist `needs_more_evidence` or failed terminal states safely when prerequisites or execution fail; do not overwrite an independent case status, original draft, Evidence result, or prior assessment. Duplicate delivery/retry must not create duplicate assessments or contradictory case-risk updates.

6. **Expose only closed lifecycle and assessment reads.** Extend the existing start union and workflow-status DTO/Zod contract with the one risk workflow identifier and an allowlisted risk result summary. Add a distinct tenant/RBAC-protected latest-assessment read endpoint/DTO if needed to return final level, closed localized reason codes, `requires_approval`, safe next state, and run identifier without leaking trace/snapshot/input data. Enforce cookie auth, appropriate case-read/start authorization, organization isolation, strict request bodies, UUID validation, one active risk run per case, archived/missing safety, and UUID-only task payloads. Do not add any risk PATCH/override or approval endpoint.

7. **Add worker composition and safe audit events.** Reload and claim the run by UUID, revalidate prerequisites in a fresh session, compile/run the graph through the established runtime, and persist via the service boundary. Cover finite retry, duplicate delivery, dispatch failure, database failure, and loop/session disposal. Audit `workflow.risk_compliance_queued`, `started`, `completed`, `needs_more_evidence`, and `failed` events transactionally with organization/case/run identifiers, final level/counts/closed reason categories only. Normal logs and errors remain secret- and content-free.

8. **Present risk without pre-implementing approval.** Add a Bokmål-first/English Case Detail panel that lets an authorized operational user start the closed assessment only when prerequisites are eligible, polls only its active run, and displays queued/running/completed/needs-more-evidence/failed states. A completed panel shows semantic, non-color-only risk level, localized closed reason categories, safe-next-state text, and a clear “human review will be required” notice when applicable. It has no reviewer queue, approve/reject/edit/reassign/request-more-evidence buttons, final-output label, raw policy details, or trace link.

9. **Document exact guarantees and limits.** Document the fixed policy matrix, safe reason-code vocabulary, prerequisite/rerun behavior, default-deny projection rule, and that this is an assessment/routing stage rather than a decision or approval implementation. Configure only necessary bounded non-secret thresholds/fixtures; do not claim regulatory certification or automatic legal/compliance determination.

## Required tests

### Graph and policy tests

- The graph has exactly the seven named nodes in architecture order; typed state/result schemas reject extra data, arbitrary reason codes/policy controls, invalid levels, and raw content fields.
- Table-driven policy cases cover each required signal: PII, sensitive domain, weak evidence, contradiction, missing required source, low confidence, high-impact action, policy conflict, and prompt injection. Verify deterministic reason ordering/deduplication, final level, `requires_approval`, and safe next state.
- High-risk combinations always require approval. Evidence/prerequisite failure routes conservatively to `needs_more_evidence` and cannot present a safe/final result. A medium/low scenario is allowed only when all forced-review/evidence conditions are absent according to the documented matrix.
- The graph consumes trusted persisted classifications only; injection-like case/source/draft text cannot alter policy, source eligibility, workflow name, model/provider, or risk result.
- Node/runtime/persistence failures have bounded retry behavior and safe default-deny snapshots with no raw draft, source, policy rationale, prompt, credentials, exception, cost, or token data.

### Persistence, API, worker, and audit tests

- Closed start/status/assessment-read contracts enforce cookie auth, role/case authorization, tenant isolation, UUID validation, strict payloads, archived/missing safety, eligible Draft/Evidence prerequisites, and one-active-run policy.
- A successful run creates exactly one correctly scoped `RiskAssessment`, safe `risk_reasons`, node/run records, audit events, and `cases.risk_level` projection. Foreign tenant and unauthorized readers cannot infer an assessment.
- `needs_more_evidence`, dispatch failure, worker failure, duplicate delivery, stale prerequisites, and transaction failure do not create partial assessments, alter original drafts/Evidence/approval data, or leave a misleading case risk level.
- Queue payloads contain only the run UUID. Worker revalidation, retry/idempotency, broker failure, and async-engine/session disposal are covered.
- Status/read DTOs expose only final level, closed reasons, approval requirement, safe next state, and designed availability/count data; they exclude snapshots, node traces, source excerpts, model/prompt data, raw policy analysis, numeric score/cost/token values, and exceptions.
- Content-free risk audit events are transactionally consistent, and all earlier Intake/Evidence/Extraction/Drafting, direct-RAG, authorization, and Case suites remain green.

### Web and end-to-end tests

- Bokmål and English tests cover start eligibility, loading, queued/running, low/medium/high display, reason categories, required-review notice, needs-more-evidence, failed, empty, and safe API-error states.
- The panel has accessible headings/statuses, visible focus, semantic labels, and non-color-only risk meaning. It polls only active runs and validates the strict API contracts.
- Tests prove no browser token storage, raw workflow payload, risk override, reviewer-action controls, or trace/final-output UI appears.
- Playwright uses synthetic fixtures to run a high-risk assessment that displays closed reasons and a review-required notice, then an insufficient/contradictory-evidence scenario that ends in Needs More Evidence with no approval action available.

## Validation steps

```bash
uv run pytest services/agent_orchestrator/tests
uv run pytest apps/api/tests
pnpm test:web
pnpm test:e2e
pnpm format:check
pnpm lint
pnpm typecheck
pnpm check:workspace
pnpm dev:up
docker compose --env-file .env.example exec api uv run alembic current
pnpm verify:local-stack
pnpm dev:down
git diff --check
```

Manual synthetic-only check: at `http://127.0.0.1:3000/nb/cases`, open a case with a completed eligible original draft and its Evidence package, run Risk and Compliance, and verify the final risk/reason categories are localized and a high-risk result says human review is required. Repeat with contradictory or insufficient evidence and verify `Needs More Evidence` without any reviewer action. Inspect cookie-secured API contracts at `http://127.0.0.1:8000/docs`. Do not print or capture cookies, credentials, drafts, sources, prompts, or provider values.

## Completion criteria

- The seven-node typed graph deterministically evaluates every roadmap/PRD risk category from trusted persisted inputs and produces a closed final risk result.
- High-risk results always require approval; inadequate/stale/contradictory evidence ends safely in Needs More Evidence; no path bypasses the later human-review boundary.
- Each valid completed run persists one tenant-scoped assessment, safe case risk projection, workflow/node records, and content-free audit events without touching approval/human-finalization state.
- API/status/read surfaces and the localized accessible Case Detail panel show only safe final risk/reason/review-required data, with no override, review decision, trace, raw policy analysis, or unsafe content leakage.
- Graph, policy, persistence, API, worker, web, and E2E tests pass alongside static checks and rebuilt local-stack validation.

## Risks, dependencies, and notes for the implementation agent

- Treat the fixed policy matrix as a safety boundary, not a score-tuning exercise. Prefer a conservative `needs_more_evidence`/review-required outcome to guessing from absent or ambiguous input.
- Do not duplicate upstream ownership: revalidate Evidence and consume Intake signals, but do not rerun retrieval, PII detection, injection detection, or free-form contradiction analysis in this graph.
- Preserve the Phase 20 original draft as immutable. This phase records assessment/routing only; Phase 22 will create the approval packet, reviewer decision, and any distinct final human text.
- Keep `risk_reasons` a small versioned closed-code structure. It is a safe explanation surface, not a storage location for evidence, legal analysis, prompts, or raw model output.
- Do not mark Phase 21 `(DONE)` or edit `specs/roadmap.md` / `specs/progress.md` while generating this plan. A later implementation turn may update status only after all required validation passes.
