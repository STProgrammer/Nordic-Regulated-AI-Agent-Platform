# ADR 0002: LangGraph for agent workflows

- Status: Accepted
- Date: 2026-06-19

## Context

The platform must make multi-step AI assistance inspectable, source-grounded, testable, and subject
to human approval. Workflows need explicit state, node transitions, persistence, and controlled
handling of retries and interrupts.

## Decision

Future agent workflows will use LangGraph with typed Pydantic state, explicit nodes and transitions,
persisted workflow state, and human-approval interrupts. LangMem is deferred and will only be
introduced for controlled, organization-scoped, auditable, non-sensitive use cases.

## Consequences

- Explicit graphs support workflow traces, deterministic node-level tests, approval checkpoints, and
  audit-oriented inspection.
- Typed state constrains model and tool boundaries and makes failures easier to reason about.
- The project accepts the learning and integration cost of graph orchestration rather than hiding
  regulated workflow decisions in unstructured prompts.

## Alternatives considered

- Linear prompt chains: rejected because approval, routing, persistence, and traceability would be
  implicit and harder to test.
- Uncontrolled long-term agent memory: rejected because it risks privacy, tenancy, and evidence
  governance failures.

## Links

- [Architecture §7: LangGraph workflow architecture](../../specs/architecture.md#7-langgraph-workflow-architecture)
- [Architecture §8: LangMem usage](../../specs/architecture.md#8-langmem-usage)
- [Architecture §20.2: LangGraph for agent workflows](../../specs/architecture.md#202-langgraph-for-agent-workflows)
- [Roadmap Phase 16](../../specs/roadmap.md#phase-16--agent-orchestrator-foundation-done)
