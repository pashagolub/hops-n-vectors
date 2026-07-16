#!/usr/bin/env bash
# E2E smoke test for the hops-n-vectors beer recommender stack.
#
# Asserts acceptance criteria AC-001 through AC-003:
#   AC-001  docker compose up → ready within 10 min (visible progress + hints)
#   AC-002  TUI lemon query → ≥ 5 results, citrus-themed beers at top
#   AC-003  embedded count = total row count
#
# Performance gate (PER-002):
#   Full initial embedding of ~3,300 rows must complete within 5 minutes
#   on the current CI runner.
#
# Usage:
#   bash scripts/e2e.sh [--keep]
#
# Options:
#   --keep   Do not tear down the stack after the test (useful for debugging).
#
# Exit codes:
#   0  All assertions passed
#   1  One or more assertions failed

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KEEP_STACK=0

for arg in "$@"; do
    case "$arg" in
        --keep) KEEP_STACK=1 ;;
        *) echo "Unknown argument: $arg" >&2; exit 1 ;;
    esac
done

PASS=0
FAIL=0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ok()   { echo "  ✅ $*"; ((PASS++)) || true; }
fail() { echo "  ❌ $*"; ((FAIL++)) || true; }

section() { echo; echo "── $* ──"; }

# shellcheck disable=SC2317  # called indirectly via trap
teardown() {
    if [[ $KEEP_STACK -eq 0 ]]; then
        echo
        echo "Tearing down stack…"
        docker compose -f "$REPO_ROOT/docker-compose.yml" down -v --remove-orphans 2>/dev/null || true
    else
        echo
        echo "--keep specified; stack left running."
    fi
}

# ---------------------------------------------------------------------------
# Bring the stack up
# ---------------------------------------------------------------------------

section "AC-001 – Stack startup"

cd "$REPO_ROOT"
trap teardown EXIT

echo "Running: docker compose down -v (clean slate)"
docker compose down -v --remove-orphans 2>/dev/null || true

echo "Running: docker compose up -d"
START_TS=$(date +%s)
docker compose up -d

# ---------------------------------------------------------------------------
# Wait for scheduler container to finish the bootstrap phase
# (loader → embedder → pg_timetable running)
# ---------------------------------------------------------------------------

MAX_WAIT_SECS=600   # 10 minutes (AC-001 budget)
EMBED_DEADLINE=300  # 5 minutes (PER-002 budget, measured from start)
POLL_INTERVAL=5
ELAPSED=0
READY=0
EMBEDDING_START_TS=""
EMBEDDING_END_TS=""

echo "Waiting for bootstrap to complete (up to ${MAX_WAIT_SECS}s)…"

while [[ $ELAPSED -lt $MAX_WAIT_SECS ]]; do
    LOGS=$(docker compose logs scheduler 2>/dev/null || true)

    # Detect embedding start
    if [[ -z "$EMBEDDING_START_TS" ]] && echo "$LOGS" | grep -q "Embedding [0-9]"; then
        EMBEDDING_START_TS=$(date +%s)
        echo "  → Embedding started at ${ELAPSED}s"
    fi

    # Detect completion: HNSW index ready + TUI hint in logs
    if echo "$LOGS" | grep -q "HNSW index ready" && \
       echo "$LOGS" | grep -q "docker compose run"; then
        EMBEDDING_END_TS=$(date +%s)
        READY=1
        break
    fi

    sleep $POLL_INTERVAL
    ELAPSED=$(($(date +%s) - START_TS))
done

TOTAL_ELAPSED=$(($(date +%s) - START_TS))

if [[ $READY -eq 1 ]]; then
    ok "Stack ready in ${TOTAL_ELAPSED}s (budget: ${MAX_WAIT_SECS}s)"
else
    fail "Stack did not become ready within ${MAX_WAIT_SECS}s"
    echo "=== scheduler logs ==="
    docker compose logs --tail=50 scheduler
    exit 1
fi

# PER-002: embedding duration
if [[ -n "$EMBEDDING_START_TS" && -n "$EMBEDDING_END_TS" ]]; then
    EMBED_ELAPSED=$((EMBEDDING_END_TS - EMBEDDING_START_TS))
    echo "  Embedding duration: ${EMBED_ELAPSED}s (budget: ${EMBED_DEADLINE}s)"
    if [[ $EMBED_ELAPSED -le $EMBED_DEADLINE ]]; then
        ok "PER-002 embedding completed in ${EMBED_ELAPSED}s"
    else
        fail "PER-002 embedding took ${EMBED_ELAPSED}s, exceeds ${EMBED_DEADLINE}s budget"
    fi
else
    fail "PER-002 could not measure embedding duration (start/end markers missing)"
fi

# ---------------------------------------------------------------------------
# AC-003: embedded count = total row count
# ---------------------------------------------------------------------------

section "AC-003 – Embedded count = total row count"

TOTAL=$(docker compose exec -T postgres \
    psql -U beer -d beer -t -c "SELECT count(*) FROM beers;" 2>/dev/null | tr -d '[:space:]')
EMBEDDED=$(docker compose exec -T postgres \
    psql -U beer -d beer -t -c "SELECT count(*) FROM beers WHERE embedding IS NOT NULL;" \
    2>/dev/null | tr -d '[:space:]')

echo "  Total rows:    $TOTAL"
echo "  Embedded rows: $EMBEDDED"

if [[ "$TOTAL" -gt 0 && "$TOTAL" == "$EMBEDDED" ]]; then
    ok "AC-003 all ${TOTAL} rows embedded"
else
    fail "AC-003 embedded=${EMBEDDED} of total=${TOTAL}"
fi

# ---------------------------------------------------------------------------
# AC-002: TUI lemon query returns ≥ 5 citrus-ranked results
# ---------------------------------------------------------------------------

section "AC-002 – TUI lemon query"

JSON_OUTPUT=$(docker compose run --rm scheduler \
    python -m hopsnvectors.tui --query lemon --json --top 10 2>/dev/null)

echo "  TUI output (first 200 chars): ${JSON_OUTPUT:0:200}"

# Parse result count
RESULT_COUNT=$(echo "$JSON_OUTPUT" | python3 -c \
    "import json,sys; data=json.load(sys.stdin); print(len(data.get('results', data) if isinstance(data, dict) else data))" \
    2>/dev/null || echo "0")

if [[ "$RESULT_COUNT" -ge 5 ]]; then
    ok "AC-002 TUI returned ${RESULT_COUNT} results (≥ 5 required)"
else
    fail "AC-002 TUI returned ${RESULT_COUNT} results (< 5)"
fi

# Check citrus/lemon content in top results
TOP_NAMES=$(echo "$JSON_OUTPUT" | python3 -c \
    "import json,sys; data=json.load(sys.stdin); results=data.get('results', data) if isinstance(data, dict) else data; [print(r.get('beer_name','') + ' ' + r.get('style','') + ' ' + r.get('info','')[:80]) for r in results[:3]]" \
    2>/dev/null | tr '[:upper:]' '[:lower:]' || echo "")

if echo "$TOP_NAMES" | grep -qiE "lemon|citrus|wheat|wit|hefeweizen|orange|grapefruit"; then
    ok "AC-002 citrus/lemon-themed beers in top results"
else
    echo "  Top result info: $TOP_NAMES"
    fail "AC-002 top results do not appear citrus/lemon-themed"
fi

# ---------------------------------------------------------------------------
# AC-010: pg_timetable chain registered
# ---------------------------------------------------------------------------

section "AC-010 – pg_timetable chain registration"

CHAIN=$(docker compose exec -T postgres \
    psql -U beer -d beer -t \
    -c "SELECT chain_name FROM timetable.chain WHERE chain_name = 'rebuild_embeddings';" \
    2>/dev/null | tr -d '[:space:]' || echo "")

if [[ "$CHAIN" == "rebuild_embeddings" ]]; then
    ok "AC-010 rebuild_embeddings chain registered in timetable"
else
    fail "AC-010 rebuild_embeddings chain NOT found in timetable.chain"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

section "Results"
echo "  Passed: $PASS"
echo "  Failed: $FAIL"
echo

if [[ $FAIL -gt 0 ]]; then
    echo "E2E FAILED with $FAIL assertion(s)."
    exit 1
else
    echo "E2E PASSED — all assertions green."
    exit 0
fi
