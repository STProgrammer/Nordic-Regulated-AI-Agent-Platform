"""Run the explicit, idempotent synthetic local database seed."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_SOURCE = ROOT / "apps" / "api" / "src"
if str(API_SOURCE) not in sys.path:
    sys.path.insert(0, str(API_SOURCE))

from app.db.seed import seed_local  # noqa: E402
from app.db.session import dispose_database_engines  # noqa: E402


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed synthetic local fixture data.")
    parser.add_argument(
        "--password-env",
        metavar="VARIABLE",
        help=(
            "Optional environment variable holding a local-only synthetic password. "
            "The password is never printed."
        ),
    )
    return parser.parse_args()


async def main() -> int:
    """Seed only safe fixture data and keep database errors non-sensitive."""

    arguments = _arguments()
    local_password: str | None = None
    if arguments.password_env is not None:
        local_password = os.getenv(arguments.password_env)
        if local_password is None:
            print(
                "Local seed failed. The requested password environment variable is not set.",
                file=sys.stderr,
            )
            return 1
    try:
        organization_count, role_count, user_count = await seed_local(local_password=local_password)
    except Exception:
        # Connection information and raw database errors are intentionally not
        # displayed by this local convenience command.
        print("Local seed failed. Confirm migrations and database configuration.", file=sys.stderr)
        return 1
    finally:
        await dispose_database_engines()

    print(
        "Synthetic local seed complete: "
        f"organizations={organization_count} roles={role_count} users={user_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
