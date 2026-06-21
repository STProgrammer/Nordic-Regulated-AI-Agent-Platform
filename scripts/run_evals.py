"""Run the checked-in synthetic corpus without a database, network, or AI provider."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from evaluation.contracts import load_canonical_dataset
from evaluation.runners import evaluate_dataset


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, help="Checked-in canonical dataset key.")
    parser.add_argument(
        "--check", action="store_true", help="Exit non-zero unless every exact threshold passes."
    )
    args = parser.parse_args(arguments)
    try:
        report = evaluate_dataset(load_canonical_dataset(args.dataset))
    except (OSError, ValueError, json.JSONDecodeError):
        print(json.dumps({"status": "invalid_dataset"}, sort_keys=True))
        return 2
    print(json.dumps(report.safe_summary(), sort_keys=True))
    return 0 if not args.check or report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
