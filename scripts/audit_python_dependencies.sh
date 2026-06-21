#!/usr/bin/env bash

# pip-audit cannot query private workspace packages on PyPI. Export the locked
# third-party graph instead, then audit precisely those published packages.
set -euo pipefail

requirements_file="$(mktemp)"
trap 'rm -f "$requirements_file"' EXIT

uv export --locked --all-packages --no-emit-workspace --format requirements-txt \
  --output-file "$requirements_file" >/dev/null
uv run pip-audit --strict --require-hashes -r "$requirements_file"
