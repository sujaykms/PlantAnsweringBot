#!/usr/bin/env bash
# Build time: initialise Postgres, apply migrations, embed + load the documents into /seed/pgdata.
set -euo pipefail
PGBIN=/usr/lib/postgresql/16/bin
SEED=/seed/pgdata

"$PGBIN/initdb" -D "$SEED" -U plant --auth=trust -E UTF8 >/dev/null
"$PGBIN/pg_ctl" -D "$SEED" -o "-c listen_addresses=127.0.0.1 -c port=5432 -k /tmp" -w start >/dev/null
"$PGBIN/createdb" -h 127.0.0.1 -U plant plantdocs

export DATABASE_URL=postgresql://plant@127.0.0.1:5432/plantdocs
cd /app/backend
python scripts/migrate.py
python -m ingest.run --path docs

"$PGBIN/pg_ctl" -D "$SEED" -m fast -w stop >/dev/null
