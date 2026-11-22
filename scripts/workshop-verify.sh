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

# Every other check passes -X, which skips psqlrc. This one loads it, because
# the banner is the first thing an attendee sees.
banner=$(docker exec "$CONTAINER" psql -c 'SELECT 1' 2>&1)
if grep -q 'error' <<<"$banner" || ! grep -qF '\i /workshop/00_check.sql' <<<"$banner" \
    || ! grep -qF "search('lemon')" <<<"$banner"; then
    echo "FAIL: the psqlrc banner is broken"; echo "$banner"; exit 1
fi
echo "psqlrc banner ok"

# Drive the :beer prompt the way an attendee would, through psqlrc and stdin.
tui=$(printf '%s\n' ':beer' ':top 2' 'dark roasty coffee' ':like 11149' ':explain' 'lemon' \
        ':top 99' ':nonsense' ':quit' 'SELECT count(*) AS still_psql FROM beers;' \
      | docker exec -i "$CONTAINER" psql 2>&1)
for want in 'Showing 2 results.' '(2 rows)' 'Komes Raspberry Baltic Porter' \
            'Index Scan using beers_embedding_hnsw' 'Usage:' 'Unknown command.' 'Cheers!' 'still_psql'; do
    grep -qF -- "$want" <<<"$tui" || { echo "FAIL: :beer prompt, missing: $want"; echo "$tui"; exit 1; }
done
if grep -q 'ERROR' <<<"$tui"; then echo "FAIL: :beer prompt raised an error"; echo "$tui"; exit 1; fi
echo ":beer prompt ok"

# Step mode: answer the three prompts of exercise 05, then press Enter at
# every pause, and check the attendee's own beer comes back from a search.
stepped=$(printf '%s\n' 'Stepped Stout' 'a pitch black stout with burnt toast and espresso' \
            'black beer that tastes of burnt toast' '' '' '' '' '' '' \
          | docker exec -i "$CONTAINER" psql -X -f /workshop/05_keep_it_fresh.sql 2>&1)
[ "$(grep -c 'Stepped Stout' <<<"$stepped")" -ge 3 ] && ! grep -q 'ERROR' <<<"$stepped" \
    || { echo "FAIL: step mode in 05_keep_it_fresh.sql"; echo "$stepped"; exit 1; }
# Enter at the end-of-live-part prompt stops a script; m continues it.
short=$(printf '\n\n\n\n\n' | docker exec -i "$CONTAINER" psql -X -f /workshop/02_search.sql 2>&1)
long=$(printf '\n\n\n\nm\n\n\n' | docker exec -i "$CONTAINER" psql -X -f /workshop/02_search.sql 2>&1)
grep -q 'dark roasty coffee' <<<"$short" && { echo "FAIL: Enter did not stop 02_search.sql"; exit 1; }
grep -q 'dark roasty coffee' <<<"$long" || { echo "FAIL: m did not continue 02_search.sql"; echo "$long"; exit 1; }
echo "step mode ok"

for pass in 1 2; do
    echo "=== exercise pass ${pass} ==="
    for f in 00_check 01_operators 02_search 03_indexes 04_sharp_edges 05_keep_it_fresh 06_ivfflat 07_similarity_limits; do
        printf '  %-22s' "$f"
        if out=$(docker exec "$CONTAINER" psql -X -v ON_ERROR_STOP=1 -v nopause=1 -q -f "/workshop/${f}.sql" 2>&1); then
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
