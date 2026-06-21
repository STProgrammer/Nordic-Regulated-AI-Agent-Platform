"""The local evaluation command must work with no service stack running."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_run_evals_script_passes_canonical_dataset() -> None:
    root = Path(__file__).resolve().parents[3]
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_evals.py",
            "--dataset",
            "nordic-regulated-core-v1",
            "--check",
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert '"passed": true' in completed.stdout
