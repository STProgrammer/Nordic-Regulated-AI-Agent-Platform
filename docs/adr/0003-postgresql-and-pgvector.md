# ADR 0003: PostgreSQL with pgvector as the default data and vector store

- Status: Accepted
- Date: 2026-06-19

## Context

The platform needs a governed relational system of record, organization isolation, auditable
workflow data, and semantic plus keyword retrieval. The early deployment footprint should remain
operationally straightforward.

## Decision

Use PostgreSQL as the system of record and pgvector as the default semantic-search store. PostgreSQL
full-text and keyword capabilities will support hybrid retrieval. Qdrant and OpenSearch remain
optional, evidence-driven additions rather than baseline dependencies.

## Consequences

- Relational governance, audit data, and vector retrieval stay close to one mature operational
  platform.
- The initial local and cloud footprint remains simpler than a mandatory separate search cluster.
- A dedicated vector or search service may be justified later by scale, latency, or retrieval
  requirements and must be evaluated explicitly.

## Alternatives considered

- Qdrant as the default vector store: deferred until workload evidence requires a dedicated service.
- OpenSearch as a mandatory baseline: deferred because it adds operational complexity before the
  product demonstrates the need.

## Links

- [Architecture §4.4: Retrieval and document intelligence](../../specs/architecture.md#44-retrieval-and-document-intelligence)
- [Architecture §9: RAG architecture](../../specs/architecture.md#9-rag-architecture)
- [Architecture §20.3–20.4](../../specs/architecture.md#203-postgresql-as-main-database)
- [Roadmap Phase 4](../../specs/roadmap.md#phase-4--database-foundation-and-migrations)
