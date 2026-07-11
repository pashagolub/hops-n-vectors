#!/bin/sh
# Scheduler container entrypoint (spec v1.2 §4.1, PAT-001).
#
# Default flow:   load -> embed -> TUI/psql hint -> exec pg_timetable
# Dispatch:       first argument selects an alternative tool, e.g.
#                   docker compose run --rm scheduler tui [args...]
#                   docker compose run --rm scheduler embedder --once
# Each stage exits non-zero on failure, failing the container fast.
set -eu

case "${1:-}" in
    tui)
        shift
        exec python -m hopsnvectors.tui "$@"
        ;;
    loader|embedder)
        tool="$1"
        shift
        exec python -m "hopsnvectors.$tool" "$@"
        ;;
esac

echo "scheduler | stage 1/3: loading dataset ..."
python -m hopsnvectors.loader

echo "scheduler | stage 2/3: embedding pending rows ..."
python -m hopsnvectors.embedder

echo "scheduler | ready."
echo "scheduler | TUI:  docker compose run --rm scheduler tui"
echo "scheduler | psql: docker compose exec postgres psql -U ${POSTGRES_USER:-beer} -d ${POSTGRES_DB:-beer}"
echo "scheduler | stage 3/3: starting pg_timetable ..."

# Substitute the presenter-tunable schedule (spec §4.4) into the job
# registration SQL, executed by pg_timetable at startup via --file.
REBUILD_SCHEDULE="${REBUILD_SCHEDULE:-*/15 * * * *}"
sed "s|\*/15 \* \* \* \*|${REBUILD_SCHEDULE}|g" \
    /app/init/02_timetable_job.sql > /tmp/02_timetable_job.sql

exec pg_timetable \
    "postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST:-postgres}:5432/${POSTGRES_DB}?sslmode=disable" \
    --clientname=hops-n-vectors-scheduler \
    --file=/tmp/02_timetable_job.sql
