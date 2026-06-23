# Security Guide

## Authentication and authorization

Local password authentication uses Argon2id. Browser sessions are opaque, finite, HTTP-only Redis
records; passwords, session ids, and connection strings are not returned by the API. The backend
reloads active users and roles before protected work and enforces organization scope, RBAC, and the
high-risk approval separation-of-duties rule. Login attempts use independent normalized-email and
client-origin limits with HMAC-derived Redis keys.

## Browser transport controls

The normal browser path is same-origin `/api/...` through the Next.js rewrite. CORS is disabled
unless `NORDIC_API_CORS_ALLOWED_ORIGINS` contains exact `http`/`https` origins; wildcards are
rejected. Unsafe cookie-authenticated API requests must send an exact origin listed in
`NORDIC_API_CSRF_TRUSTED_ORIGINS`. Staging and production require that setting and default to no
Swagger/OpenAPI endpoints unless explicitly enabled.

Both the API and web shell set anti-framing, MIME-sniffing, referrer, permissions, and cross-origin
isolation headers. API responses enable HSTS when deployed. TLS termination, public host routing,
and deployment ingress configuration are planned cloud-operational work; no public environment is
provisioned by this repository version.

## File handling

Uploads are allowed only for the documented supported types and are bounded before multipart
parsing. The API validates extension, compatible MIME type, signatures/UTF-8 structure, filename,
and OOXML archive paths, duplication, encryption, member size, and compression ratio. Accepted raw
objects are private, server-keyed, checksummed, and processed asynchronously; normal API responses
never expose storage keys, raw files, checksums, or parsed text.

The platform does not provide a malware-scanning service. Treat the format and archive checks as a
defense-in-depth boundary, not an antivirus guarantee. A deployed environment needs a documented
malware-scanning integration before accepting untrusted production documents.

## AI safety and privacy

Prompts, provider payloads, raw workflow state, secrets, and raw sensitive content are excluded from
public trace, audit, and normal log projections. The platform uses typed workflow state, allowlisted
tools, prompt-injection signals, source-grounded citations, evidence sufficiency gates,
structured-output validation, deterministic regression tests, and required human approval for
high-risk output. Controlled memory is organization-scoped, auditable, optional, and rejects case
content and credentials.

## Secrets and dependency hygiene

Keep credentials in untracked local environment files, CI secret stores, or deployed secret
management—not repository files, screenshots, logs, fixtures, or sample data. `.env.example` holds
only intentionally public local emulator values and must never be reused outside local development.
The reviewed secret-scan baseline records those emulator values and existing synthetic test or
localization false positives; it does not exclude tests from future scanning.

Run the repository checks below after dependency changes. `pip-audit` and `pnpm audit` require
current advisory data; high-severity JavaScript findings and any Python audit finding fail the
command. These checks are CI quality gates.

```bash
pnpm security:static
pnpm security:python-deps
pnpm security:node-deps
pnpm security:secrets
```
