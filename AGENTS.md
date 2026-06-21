# AGENTS.md

# Spec-Driven Development Commands

This project uses a Spec-Driven Development workflow.

Core specification files live in `/specs`:

* `/specs/PRD.md`
* `/specs/architecture.md`
* `/specs/roadmap.md`
* `/phases/phaseX.md` files

## Command Shortcuts

The user may give short commands:

* `G 7` = generate `/phases/phase7.md`
* `I 7` = implement `/phases/phase7.md`
* `G` = generate the next phase file from `/specs/roadmap.md` that is not marked `(DONE)`
* `I` = implement the next unimplemented phase file

`G` means **Generate Phase Plan**.
`I` means **Implement Phase**.

If the phase number is not provided, determine it from `/specs/roadmap.md`, existing `/phases/phaseX.md` files, and `/specs/progress.md` if present. Use the safest deterministic choice.

---

## G Mode — Generate Phase Plan

When the user says `G X`, generate `/phases/phaseX.md`.

Before writing the phase file, read:

1. `/specs/PRD.md`
2. `/specs/architecture.md`
3. `/specs/roadmap.md`

Then locate Phase X in `/specs/roadmap.md`.

Write the generated phase plan directly to `/phases/phaseX.md`.

The generated `phaseX.md` must be a lean execution brief for Phase X only.

It must include:

* Phase title
* Phase objective
* Relevant context from PRD, architecture, and roadmap
* In-scope deliverables
* Out-of-scope items
* Likely files, folders, modules, and services affected
* Implementation tasks
* Required tests
* Validation steps
* A concise Validation Plan separating focused validation, broader validation, and full validation
* Completion criteria
* Risks or dependencies for this phase
* Notes for the implementation agent

Rules for G Mode:

* Do not write source code.
* Do not expand project scope beyond the specs.
* Do not include unrelated future-phase work.
* Include only the relevant context needed to implement the phase correctly.
* Make the phase practical, testable, and suitable for one focused AI coding-agent session.
* Make the phase file concrete enough to reduce mistakes, but not report-like.
* Validation and testing must be built into the step-by-step implementation sequence.
* The phase file must support professional implementation quality, not quick or temporary work.
* A phase is not complete unless its tests and validation checks pass.

---

## Phase File Quality Standard

Every `phaseX.md` file must make implementation, testing, and validation faster, more reliable, and less dependent on guessing.

The phase file is an execution brief, not a report.

A good phase file must:

* define the current phase goal clearly
* define exact in-scope and out-of-scope work
* identify affected files, folders, modules, and services
* list step-by-step implementation tasks
* include focused tests inside the implementation sequence
* provide exact focused validation commands where possible
* define conditional broader validation only when affected
* define expensive validation only when truly required
* define clear completion criteria
* mention only the PRD/architecture constraints needed to avoid mistakes

Avoid:

* long background explanations
* repeated product motivation
* large copied sections from PRD or architecture
* future-phase discussion
* broad full-suite validation by default
* long manual validation sections
* report-style writing

The phase file should be detailed only where detail prevents implementation mistakes.

## Phase Execution Plan Format

When generating a `phaseX.md` file, include an ordered execution plan that the implementation agent can follow directly.

Do not separate implementation, testing, and validation into unrelated sections only. Testing and validation must be part of the implementation sequence.

Use this pattern:

1. Inspect the existing files needed for this step.
2. Implement the smallest coherent part of the phase.
3. Add or update the focused tests for that part.
4. Run the focused tests for that part.
5. Fix focused failures before continuing.
6. Repeat for the next part of the phase.
7. Run broader affected checks only after all focused checks pass.
8. Run expensive validation last only when required.
9. Perform final scope review.
10. Mark the phase DONE only after final validation and final scope review pass.

Each implementation step should name:

* intended change
* likely files/modules
* tests to add or update
* focused validation command
* expected result

Avoid this pattern:

* implement everything first
* add tests later
* run broad validation at the end
* discover scope gaps after marking DONE


### Phase Validation Plan

When generating a `phaseX.md` file, include a concise Validation Plan.

Separate validation into:

1. **Focused validation** — required fast tests/checks directly related to this phase.
2. **Broader validation** — affected backend/frontend/worker checks only when this phase touches those areas.
3. **Expensive validation** — local-stack, full-suite, full Playwright, Docker rebuild, deployment, or manual browser validation only when truly needed.

Prefer exact focused commands over broad commands like `run all tests`.

Do not make full API suites, full integration suites, full web suites, full Playwright, Docker rebuilds, or long manual validation checklists mandatory by default.

Manual browser validation should normally be a fallback checklist if automated focused E2E fails twice, or if the user explicitly requests it.

---

## I Mode — Implement Phase

When the user says `I X`, implement `/phases/phaseX.md`.

Start by reading `/phases/phaseX.md`.

`phaseX.md` is the main source of truth for implementation scope. Follow it step by step.

The agent may consult `/specs/PRD.md`, `/specs/architecture.md`, and `/specs/roadmap.md` only when useful for clarification, architectural consistency, or avoiding wrong assumptions.

### I Mode Execution Discipline

Start with the affected files/modules listed in the phase file. Do not begin with broad repository exploration.

Broad search is allowed only when:

* the phase file does not identify the needed file
* the named file/module does not contain the expected code
* a focused test failure requires tracing a dependency
* an import/type/reference cannot be resolved from the named files

When broad search is used, keep it targeted and return immediately to the current implementation step.

Do not implement a large chunk and postpone tests until the end.

For each coherent part:

1. inspect the smallest relevant files
2. edit the smallest needed code
3. add or update the focused test
4. run the focused test
5. fix that focused test before moving on

Do not run broad suites to diagnose focused failures.

Implementation rules:

* Stay within the phase scope.
* Do not implement future phases.
* Do not expand the project beyond the PRD, architecture, roadmap, or phase file.
* Do not silently change architecture decisions.
* Keep code typed, tested, maintainable, and consistent with the project structure.
* Implement professionally, as part of the final product, not as temporary scaffolding or throwaway work.
* Run validation in the order defined by the phase file: focused first, broader affected checks second, expensive validation last.
* If validation fails, debug the smallest failing command first.
* If something is ambiguous, make the safest reasonable interpretation based on the specs and document the assumption briefly.

Before marking the phase complete:

* Confirm all in-scope deliverables from the phase file are implemented.
* Confirm out-of-scope work was not added.
* Confirm required tests were added or updated.
* Confirm required validation passed.
* Confirm no known blocker remains.

After successful implementation and validation:

* Mark the phase as `(DONE)` in `/specs/roadmap.md`.
* Update `/specs/progress.md` consistently if it exists.

At the end of implementation, report briefly:

* What was implemented
* Files changed
* Tests run
* Validation result
* Assumptions made
* Any known limitations or follow-up notes


---

## Native Plan Mode

If the user runs an implementation request in Codex plan mode, do not generate a separate `/phases/phaseX.md` file unless the user explicitly asks for one.

In plan mode, first read:

1. `AGENTS.md`
2. all files in `/specs`
3. `/phases/phaseX.md` if it already exists

If no `/phases/phaseX.md` exists for the requested phase, use `/specs/roadmap.md` to identify the phase scope and use the other `/specs` files for requirements and architecture boundaries.

The native plan must be a short execution brief, not a report. Its purpose is to make implementation, testing, and validation faster, more reliable, and less dependent on guessing.

The plan must focus on:

* the current phase goal
* exact in-scope and out-of-scope work
* affected files, folders, modules, and services
* implementation slices in order
* focused tests after each slice
* broader validation only after focused checks pass
* expensive validation last and only when truly required
* worktree baseline assumptions
* final scope review before marking the phase DONE

Testing and validation must be part of the implementation sequence, not a vague checklist at the end.

Each implementation slice should name:

* intended change
* likely files/modules
* tests to add or update
* focused validation command
* expected result

Avoid:

* long background explanations
* repeated product motivation
* copying large sections from PRD or architecture
* future-phase discussion
* broad full-suite validation by default
* full Playwright by default
* long manual validation sections
* meta-plans about generating another plan

Manual browser validation should normally be a fallback checklist only if automated focused E2E fails twice, or if the user explicitly requests it.

When the user approves the native plan, implement it directly according to `AGENTS.md`.

Do not also run `G X` for the same phase unless the user explicitly wants a durable `/phases/phaseX.md` file.

---

## Validation Preconditions

When generating or approving a validation plan, every validation command must have clear preconditions.

Do not require a command to assert data, metrics, logs, traces, database rows, files, or UI state unless the plan first generates or triggers that state.

A validation step must be one of:

1. **Startup/static validation** — checks something guaranteed to exist after startup, install, migration, or build.
2. **Triggered validation** — first runs a focused action that generates the expected observation, then checks the result.
3. **Existing fixture validation** — relies on a named deterministic seed/fixture that the plan explicitly loads.

Avoid validations like:

* checking workflow metrics before any workflow has run
* checking model metrics before any model path has executed
* checking audit events before generating the event
* checking queue results before dispatching a task
* checking UI state before seeding or genearing the required record

For observability, metrics, logs, traces, audit events, and background jobs, the validation plan must say:

* what action produces the observation
* which exact metric/log/event/result should appear
* which absence is acceptable
* whether missing values should be `null`, zero, empty, or not emitted

If a validation only checks service startup, assert only startup-guaranteed signals.

If a validation checks runtime behavior, trigger the runtime behavior first.


## Validation Efficiency

During implementation, run focused tests first. Run broader checks only after focused tests pass.

Full-suite, full-stack, Docker rebuild, and full Playwright validation are expensive checks. Do not include them as mandatory phase validation unless the phase directly changes global app behavior, Docker/Compose, migrations, worker runtime, authentication flow, or deployment infrastructure.

When generating a phase file, list:

* focused validation as required
* broader validation as required when affected
* expensive full validation as conditional or final-check only

Prefer exact focused test commands over broad commands like `run all tests`.

If full-stack or Playwright validation fails, fix the current-phase issue and rerun it once. If it fails again, stop and report the blocker instead of repeatedly looping.

Use deterministic/local model and embedding providers for automated validation. Real external AI provider calls are for manual demo verification only.

Manual validation is optional after automated validation and is not required before marking a phase `(DONE)`.

---

## Expensive Validation Gate

Before running local-stack, Playwright, full-suite, or other expensive validation, perform a final scope/read-model/API-contract review against the phase file.

Confirm:

* all in-scope deliverables are implemented
* required response fields for later phases are present
* out-of-scope work was not added
* focused tests already pass
* no obvious missing field or endpoint remains

Do not run expensive validation before this review. If code changes after expensive validation, rerun only the affected focused checks plus the required final expensive check.

## Browser E2E Policy

During normal phase implementation, run focused backend, API, service, unit, integration, lint, type, and format checks first.

Do not run Playwright/browser E2E for every phase by default. Backend-only, service-only, API-only, documentation-only, and infrastructure-planning phases do not require browser E2E unless the user explicitly asks for it.

Run Playwright/browser E2E only when the phase changes a user-visible browser workflow, and only after the focused automated checks pass, unless the phase specifically requires earlier browser validation.

E2E should be focused on the main user journey affected by the phase. Do not run the full E2E suite unless the user explicitly asks, or the phase is CI, staging, production, final validation, or a dedicated E2E stabilization task.

If focused E2E fails, diagnose whether the failure is a real product bug, test fixture issue, stale data issue, UI refresh issue, wrong selector/assertion, or environment issue.

Fix the current-phase issue once and rerun the focused E2E once.

If focused E2E fails again, stop. Do not keep looping. Report the exact blocker and provide a step-by-step manual browser validation checklist for the user.

If the user confirms the manual browser validation passes, that may replace automated E2E for phase completion.

Use stable selectors or test IDs for critical workflow UI. Avoid fragile exact-text assertions when testing state.

Use API/service tests for edge cases, permissions, concurrency, invalid payloads, and backend correctness. Use browser E2E only for critical user journeys.

---

## Roadmap Completion Marking

After successfully implementing a phase, update `/specs/roadmap.md`.

Mark the completed phase heading with `(DONE)`.

Example:

```md
## Phase 7 — Authentication and RBAC
```

becomes:

```md
## Phase 7 — Authentication and RBAC (DONE)
```

Only mark a phase as `(DONE)` when:

* the implementation for that phase is complete
* required tests have been added or updated
* required tests pass
* validation checks pass
* the implementation stays within phase scope
* no known blocker remains for that phase

Do not mark a phase as `(DONE)` if:

* tests fail
* validation was not run
* implementation is partial
* the phase scope was changed without clear justification
* the code only works as temporary or demo-quality work

If `/specs/progress.md` exists, update it consistently with the roadmap status.

---

## Phase Number Resolution

For `G` without a number:

1. Read `/specs/roadmap.md`.
2. Find the first phase on `/specs/roadmap.md` that is not marked `(DONE)`.
3. Generate that phase file in `/phases/phaseX.md`.

For `I` without a number:

1. Find the lowest-numbered `/phases/phaseX.md` that has not been implemented yet.
2. Prefer implementation status from `/specs/progress.md` if that file exists.
3. If `/specs/progress.md` does not exist, use `(DONE)` markings in `/specs/roadmap.md`.
4. If multiple phases exist but status is unclear, implement the lowest-numbered phase that is not marked `(DONE)`.
5. Implement the next phase that has a phase file and is not marked `(DONE)`.

---

## Multi-Phase Implementation

If the user gives an implementation range such as `I 16-18`, implement the phases one by one in order.

For each phase, finish the normal `I` workflow completely before starting the next phase: read the phase file, implement it, run validation, fix current-phase validation failures if needed, mark it `(DONE)` only after validation passes, update progress, and commit.

Do not move to the next phase until the current phase is validated and committed.

---

## Worktree Baseline Gate

Before implementing a phase, check the worktree with:

```bash
git status --short
```

If there are uncommitted changes from a previous phase, do not silently continue.

Allowed options:

1. Continue only if the phase file explicitly says those changes are the accepted baseline.
2. Continue only if the user explicitly says to preserve and build on the dirty worktree.
3. Otherwise stop and report that the previous phase must be committed, reverted, or explicitly accepted before this phase starts.

Do not mark a new phase DONE on top of an unclear dirty worktree.


## Roadmap Completion Marking

Only mark a phase as `(DONE)` after all of the following are true:

1. The implementation tasks in the phase file are complete.
2. Required tests have been added or updated.
3. Focused validation passes.
4. Required broader validation passes.
5. Required expensive validation passes, if applicable.
6. The final scope review confirms no in-scope requirement was missed.
7. `git diff --check` passes.
8. No known blocker remains.

Before marking DONE, perform a final scope review against the phase file:

* in-scope deliverables implemented
* out-of-scope work not added
* required tests present
* validation commands run
* no late missing requirement discovered
* no unrelated dirty work mixed in accidentally

Do not mark DONE before final scope review.

If code changes after marking DONE, rerun the affected validation and update the completion report.


## Validation Failure Debugging

If validation fails, debug the smallest failing command first.

Use this order:

1. Identify the exact failing command.
2. Identify the failing test file, assertion, error, or log line.
3. Classify the failure as:

   * product bug
   * test bug
   * fixture/data bug
   * environment/local-stack issue
   * timeout/polling issue
   * selector/assertion wording issue
   * wrong validation command
4. Inspect the smallest relevant evidence: API response, DB row, log, component state, or test fixture.
5. Fix the smallest current-phase cause.
6. Rerun the smallest failing command.
7. Run broader validation only after the focused failure is fixed.

Do not repeatedly rerun broad suites to diagnose a focused failure.

If the same focused E2E fails twice after one fix attempt, stop and report the blocker with a manual fallback checklist.



## General Discipline

* The PRD defines product requirements.
* The architecture file defines technical boundaries.
* The roadmap defines phase order.
* The phase file defines implementation scope.
* During phase generation, read the full specs.
* During implementation, rely mainly on the phase file.
* Keep every phase shippable, reviewable, and testable.
* Never treat early phases as disposable prototypes.
* The project is one final professional system, built progressively.
* Mark phases as `(DONE)` in `/specs/roadmap.md` only after successful implementation and validation.
