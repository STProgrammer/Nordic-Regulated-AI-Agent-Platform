# Security Policy

## Supported security boundary

This repository is a portfolio/demo system under active development. It uses only synthetic, public,
anonymized, or otherwise safe demonstration data. Do not upload real personal data, customer
documents, production credentials, or private connection strings.

## Reporting a vulnerability

Do not open a public issue containing exploit details, credentials, or personal data. Contact the
repository owner privately with a concise reproduction, affected component, and impact. Do not
include a proof-of-concept that can reach external systems or contains real data.

## Security checks

Run the checks from the repository root after installing locked dependencies:

```bash
pnpm security:static
pnpm security:python-deps
pnpm security:node-deps
pnpm security:secrets
```

`security:secrets` checks tracked files against the reviewed `.secrets.baseline`. Its explicit
entries cover only known public local-emulator values and synthetic test/localization fixtures;
generated locks and immutable historical migration identifiers are excluded by reviewed patterns. Do
not refresh it to silence a finding without reviewing why it was detected.

See [docs/security.md](docs/security.md) for implementation boundaries and deployment guidance.
