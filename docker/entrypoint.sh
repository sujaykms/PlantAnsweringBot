#!/usr/bin/env bash
# Runtime: Postgres (localhost only) + FastAPI (localhost only) + Next.js on the public $PORT.
set -uo pipefail
PGBIN=/usr/lib/postgresql/16/bin
# The base image already defines PGDATA, so use our own name. Mount a volume here to keep history/alerts.
PGDATA="${APP_PGDATA:-/home/user/pgdata}"

if [ ! -s "$PGDATA/PG_VERSION" ]; then
  mkdir -p "$PGDATA"
  cp -a /seed/pgdata/. "$PGDATA"/
fi
chmod 700 "$PGDATA"
"$PGBIN/pg_ctl" -D "$PGDATA" -o "-c listen_addresses=127.0.0.1 -c port=5432 -k /tmp" -w -l /tmp/postgres.log start

export DATABASE_URL="${DATABASE_URL:-postgresql://plant@127.0.0.1:5432/plantdocs}"
(cd /app/backend && exec uvicorn app.main:app --host 127.0.0.1 --port 8000) &
API=$!
(cd /app/web && HOSTNAME=0.0.0.0 PORT="${PORT:-7860}" exec node server.js) &
WEB=$!

cleanup() { kill "$API" "$WEB" 2>/dev/null; "$PGBIN/pg_ctl" -D "$PGDATA" -m fast stop >/dev/null 2>&1; }
trap 'cleanup; exit 0' TERM INT
wait -n "$API" "$WEB"   # if either process dies, exit so the platform restarts the container
code=$?
cleanup
exit "$code"
