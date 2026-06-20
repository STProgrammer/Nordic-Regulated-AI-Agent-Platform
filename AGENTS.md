# AGENTS.md

# Spec-Driven Development Commands

This project uses a Spec-Driven Development workflow.

Core specification files live in `/specs`:

- `/specs/PRD.md`
- `/specs/architecture.md`
- `/specs/roadmap.md`
- `/phases/phaseX.md` files

## Command Shortcuts

The user may give short commands:

- `G 7` = generate `/phases/phase7.md`
- `I 7` = implement `/phases/phase7.md`
- `G` = generate the next phase file from `/specs/roadmap.md` that is not marked `(DONE)`
- `I` = implement the next unimplemented phase file

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

The generated `phaseX.md` must be a detailed implementation plan for Phase X only.

It must include:

- Phase title
- Phase objective
- Relevant context from PRD, architecture, and roadmap
- In-scope deliverables
- Out-of-scope items
- Likely files, folders, modules, and services affected
- Implementation tasks
- Required tests
- Validation steps
- Completion criteria
- Risks or dependencies for this phase
- Notes for the implementation agent

Rules for G Mode:

- Do not write source code.
- Do not expand project scope beyond the specs.
- Do not include unrelated future-phase work.
- Include enough context inside `phaseX.md` so implementation can proceed without normally needing to read PRD, architecture, or roadmap.
- Make the phase self-contained, practical, testable, and suitable for one focused AI coding-agent session.
- Make the phase file detailed enough to reduce implementation mistakes and unnecessary guessing.
- The phase file must support professional implementation quality, not quick or temporary work.
- A phase is not complete unless its tests and validation checks pass.

---

## Phase File Quality Standard

Every `phaseX.md` file must be strong enough to guide a coding agent toward professional implementation.

A good phase file must:

- Restate the phase goal clearly.
- Explain how the phase fits into the final product.
- Identify relevant architecture constraints.
- Identify affected services, folders, modules, and documentation.
- Define what must be implemented now.
- Define what must not be implemented yet.
- Include testing requirements for the phase.
- Include validation commands or validation expectations where possible.
- Include completion criteria that are objective and checkable.
- Include assumptions only when necessary, and make them explicit.
- Keep the implementation focused on the current phase.

The phase file should make the implementation agent less likely to:

- implement future phases too early
- ignore architecture decisions
- skip tests
- leave incomplete work
- add unnecessary features
- produce demo-quality or temporary code
- make silent assumptions that damage the final system

---

## I Mode — Implement Phase

When the user says `I X`, implement `/phases/phaseX.md`.

Start by reading `/phases/phaseX.md`.

`phaseX.md` is the main source of truth for implementation scope. It should contain enough context to implement the phase without unnecessary back-and-forth.

The agent may also consult `/specs/PRD.md`, `/specs/architecture.md`, and `/specs/roadmap.md` when useful for clarification, architectural consistency, or avoiding wrong assumptions.

Implementation rules:

- Follow `phaseX.md` as the primary implementation plan.
- Stay within the phase scope.
- Do not implement future phases.
- Do not expand the project beyond the PRD, architecture, roadmap, or phase file.
- Do not silently change architecture decisions.
- Keep code typed, tested, maintainable, and consistent with the project structure.
- Implement professionally, as part of the final product, not as temporary scaffolding or throwaway work.
- Add or update the tests required by the phase.
- Run validation checks before marking the phase complete.
- If tests fail, fix the issue before moving on.
- If something is ambiguous, make the safest reasonable interpretation based on the specs and document the assumption in the final report.

After successful implementation and validation:

- Mark the phase as `(DONE)` in `/specs/roadmap.md`.
- Update `/specs/progress.md` consistently if it exists.

At the end of implementation, report:

- What was implemented
- Files changed
- Tests run
- Validation result
- Assumptions made
- Any known limitations or follow-up notes

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

- the implementation for that phase is complete
- required tests have been added or updated
- required tests pass
- validation checks pass
- the implementation stays within phase scope
- no known blocker remains for that phase

Do not mark a phase as `(DONE)` if:

- tests fail
- validation was not run
- implementation is partial
- the phase scope was changed without clear justification
- the code only works as temporary or demo-quality work

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

## General Discipline

- The PRD defines product requirements.
- The architecture file defines technical boundaries.
- The roadmap defines phase order.
- The phase file defines implementation scope.
- During phase generation, read the full specs.
- During implementation, rely mainly on the phase file.
- Keep every phase shippable, reviewable, and testable.
- Never treat early phases as disposable prototypes.
- The project is one final professional system, built progressively.
- Mark phases as `(DONE)` in `/specs/roadmap.md` only after successful implementation and validation.
