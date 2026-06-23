# ADR 0001: Modular monorepo architecture style

- Status: Accepted
- Date: 2026-06-19

## Context

The platform combines a web application, API, AI-oriented service boundaries, shared schemas,
infrastructure, documentation, scripts, and safe demo-data guidance. Regulated workflows need clear
ownership, testability, and auditability, while early implementation should not force a premature
distributed deployment.

## Decision

Use a modular monorepo with explicit `apps/`, `services/`, `packages/`, `infra/`, `docs/`,
`scripts/`, and `sample-data/` boundaries. These express ownership and dependency direction without
requiring each boundary to become a separately deployed service before the roadmap proves that need.

## Consequences

- Clear boundaries support maintainability, focused testing, and a reviewable path from API work to
  AI workflows and deployment.
- Shared schemas can be introduced deliberately rather than copied between services.
- Contributors must maintain cross-workspace dependency discipline and avoid bypassing boundaries
  with incidental imports.

## Alternatives considered

- A single flat application: rejected because it would blur frontend, API, retrieval, document, and
  workflow ownership.
- Immediate microservices: rejected because network and deployment complexity would arrive before
  product behavior validates the split.

## Links

- [Architecture §6: Core services](../../specs/architecture.md#6-core-services)
- [Architecture §12: File and folder structure](../../specs/architecture.md#12-file-and-folder-structure)
- [Roadmap Phase 1](../../specs/roadmap.md#phase-1--repository-and-workspace-foundation-done)
