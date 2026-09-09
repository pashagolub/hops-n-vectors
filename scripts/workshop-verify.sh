#!/usr/bin/env bash
# Acceptance run for the workshop image: wait for health, assert the contract,
# then execute every attendee exercise twice to prove they are re-runnable.
set -euo pipefail
CONTAINER="${1:-beer}"
export MSYS_NO_PATHCONV=1

printf 'waiting for %s to become healthy' "$CONTAINER"
for _ in $(seq 1 120); do
    [ "$(docker inspect -f '{{.State.Health.Status}}' "$CONTAINER" 2>/dev/null)" = "healthy" ] && break
    printf '.'; sleep 1
done
echo
[ "$(docker inspect -f '{{.State.Health.Status}}' "$CONTAINER")" = "healthy" ] || {
    echo "FAIL: container never became healthy"; docker logs --tail 40 "$CONTAINER"; exit 1; }

docker exec "$CONTAINER" psql -X -v ON_ERROR_STOP=1 -q -f /workshop/verify.sql

for pass in 1 2; do
    echo "=== exercise pass ${pass} ==="
    for f in 00_check 01_operators 02_search 03_indexes 04_sharp_edges 05_keep_it_fresh 06_ivfflat 07_similarity_limits; do
        printf '  %-22s' "$f"
        if out=$(docker exec "$CONTAINER" psql -X -v ON_ERROR_STOP=1 -q -f "/workshop/${f}.sql" 2>&1); then
            echo "ok"
        else
            echo "FAILED"; echo "$out" | tail -20; exit 1
        fi
    done
done

echo "=== post-conditions ==="
docker exec "$CONTAINER" psql -X -q -tA -v ON_ERROR_STOP=1 -c "
DO \$\$
DECLARE n int;
BEGIN
    SELECT count(*) INTO n FROM beers;
    ASSERT n = 12656, format('exercises left %s rows behind, expected 12656', n);
    SELECT count(*) INTO n FROM stale_beers;
    ASSERT n = 0, 'exercises left stale rows behind';
    ASSERT NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'beers_embed'),
        'exercise 05 left its trigger attached';
    ASSERT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'beers_embedding_hnsw'),
        'exercises left the HNSW index dropped';
    RAISE NOTICE 'database returned to its shipped state';
END \$\$;"
echo "ALL CHECKS PASSED"
