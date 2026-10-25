"""Apply db/migrations/*.sql in order (idempotent SQL; tracked in schema_migrations)."""

import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import get_settings  # noqa: E402

MIGRATIONS = Path(__file__).resolve().parents[2] / "db" / "migrations"


def main() -> None:
    with psycopg.connect(get_settings().database_url, autocommit=True) as conn:
        conn.execute("create table if not exists schema_migrations (name text primary key)")
        applied = {r[0] for r in conn.execute("select name from schema_migrations")}
        for path in sorted(MIGRATIONS.glob("*.sql")):
            if path.name in applied:
                continue
            with conn.transaction():
                conn.execute(path.read_text())
                conn.execute("insert into schema_migrations values (%s)", (path.name,))
            print(f"applied {path.name}")
    print("migrations up to date")


if __name__ == "__main__":
    main()
