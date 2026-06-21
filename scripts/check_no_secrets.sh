#!/usr/bin/env bash

# Compare the tracked-file secret scan with the reviewed baseline. The baseline
# records only public local emulator values and intentional test fixtures; any
# change requires an explicit security review.
set -euo pipefail

baseline=".secrets.baseline"
if [[ ! -f "$baseline" ]]; then
  printf 'Secret-scan baseline is missing: %s\n' "$baseline" >&2
  exit 1
fi

mapfile -d '' tracked_files < <(git ls-files -z)
uv run detect-secrets-hook --baseline "$baseline" "${tracked_files[@]}"
