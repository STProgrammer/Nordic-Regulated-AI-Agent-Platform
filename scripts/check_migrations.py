"""Report whether the configured database is exactly at the Alembic head revision."""

from __future__ import annotations

import sys
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]
API_SOURCE = ROOT / "apps" / "api" / "src"
if str(API_SOURCE) not in sys.path:
    sys.path.insert(0, str(API_SOURCE))

from app.core.config import get_settings  # noqa: E402


def main() -> int:
    """Print only revision identifiers and fail without rendering sensitive URLs."""

    config = Config(str(ROOT / "apps" / "api" / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    expected_revision = script.get_current_head()

    try:
        engine = create_engine(get_settings().database_sync_url())
        with engine.connect() as connection:
            current_revision = MigrationContext.configure(connection).get_current_revision()
        engine.dispose()
    except Exception:
        print("Unable to inspect database migration status.", file=sys.stderr)
        return 2

    print(f"database_revision={current_revision or 'base'} expected_revision={expected_revision}")
    if current_revision != expected_revision:
        print("Database is not at the Alembic head revision.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
