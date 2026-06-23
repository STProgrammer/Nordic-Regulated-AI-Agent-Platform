# ADR 0004: Azure deployment target with Container Apps before AKS

- Status: Accepted
- Date: 2026-06-19

## Context

The platform targets Norwegian enterprise and public-sector environments, where Azure services are
commonly relevant. It needs a cloud path for containers, relational storage, object storage,
secrets, images, and monitoring without making Kubernetes operations an early project dependency.

## Decision

Use Azure as the deployment target. Prefer Azure Container Apps ahead of AKS, supported by Azure
Database for PostgreSQL, Blob Storage, Key Vault, Container Registry, managed identity, and
monitoring services. Infrastructure as code and public deployment remain planned work; the current
repository validates local production-image and configuration contracts only.

## Consequences

- The deployment direction aligns with the intended market while retaining a lower-complexity
  container platform for the initial cloud path.
- Azure service assumptions stay documented before infrastructure implementation begins.
- AKS remains an optional enterprise-scale path, not a premature operational commitment.

## Alternatives considered

- Start on AKS: rejected because Kubernetes administration is unnecessary before the system proves
  its scale and orchestration needs.
- Select a cloud-neutral infrastructure baseline now: deferred; the architecture has already chosen
  Azure for the target market.

## Links

- [Architecture §5: Environment architecture](../../specs/architecture.md#5-environment-architecture)
- [Architecture §20.5–20.6](../../specs/architecture.md#205-azure-as-deployment-target)
- [Deployment readiness and data modes](../deployment-readiness.md)
