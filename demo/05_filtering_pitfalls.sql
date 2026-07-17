-- 05_filtering_pitfalls.sql
-- =========================
-- WHAT THIS DEMONSTRATES
--   ANN indexes scan a fixed candidate set FIRST and apply your WHERE
--   filter AFTERWARDS.  With a selective filter the candidates may all be
--   filtered away, so the query returns FEWER ROWS THAN `LIMIT` asks for
--   — silently.  (pgvector docs: "Filtering".)
--
-- EXPECTED OBSERVATIONS
--   1. Exact query (seq scan): 10 strong beers (abv > 12), correct answer.
--   2. Same query through the HNSW index: 0 rows!  The index hands back
--      hnsw.ef_search = 40 nearest candidates; none of them survives the
--      abv > 12 filter, and the scan stops there.
--   3. Raising ef_search helps but only shifts the cliff; 06 shows the
--      real fix (iterative scan).
--
-- NOTE: the planner strongly prefers the HNSW index for ORDER BY
-- vector-distance queries regardless of table size.  Step 1 explicitly
-- disables index scans to obtain the true exact (seq-scan) answer.
-- Step 2 re-enables them and turns off seqscan to expose the pitfall.

\pset pager off

\echo ''
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo '  05 · Filtering pitfalls'
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'

\echo '=== Reference beer (query vector source) ==='
SELECT id, beer_name, style, abv FROM beers WHERE id = 1;

\echo ''
\echo '=== 1) Exact answer (seq scan): top-10 similar beers with abv > 12 ==='
SET enable_seqscan = on;
SET enable_indexscan = off;    -- prevent planner from choosing HNSW
SET enable_bitmapscan = off;
SET hnsw.iterative_scan = off;
SELECT id, beer_name, style, abv,
       round((embedding <=> (SELECT embedding FROM beers WHERE id = 1))::numeric, 3) AS distance
FROM beers
WHERE abv > 12
ORDER BY embedding <=> (SELECT embedding FROM beers WHERE id = 1)
LIMIT 10;

\echo ''
\echo '=== 2) Same query via HNSW: returns 0 rows ==='
RESET enable_indexscan;
RESET enable_bitmapscan;
SET enable_seqscan = off;   -- force the ANN index plan (see NOTE above)
SHOW hnsw.ef_search;        -- 40 candidates by default

EXPLAIN (COSTS OFF)
SELECT id, beer_name, abv
FROM beers
WHERE abv > 12
ORDER BY embedding <=> (SELECT embedding FROM beers WHERE id = 1)
LIMIT 10;

SELECT id, beer_name, style, abv,
       round((embedding <=> (SELECT embedding FROM beers WHERE id = 1))::numeric, 3) AS distance
FROM beers
WHERE abv > 12
ORDER BY embedding <=> (SELECT embedding FROM beers WHERE id = 1)
LIMIT 10;
-- ^ 0 rows: all 40 candidates had abv <= 12 and were filtered out.

\echo ''
\echo '=== 3) Workaround: crank up ef_search (costly, still no guarantee) ==='
SET hnsw.ef_search = 400;
SELECT count(*) AS rows_returned
FROM (
    SELECT id
    FROM beers
    WHERE abv > 12
    ORDER BY embedding <=> (SELECT embedding FROM beers WHERE id = 1)
    LIMIT 10
) q;
-- ~1 of 10: better, but ef_search is capped at 1000 and every query pays
-- for the larger candidate set.  On to 06 for the proper fix.

RESET hnsw.ef_search;
RESET enable_seqscan;
RESET enable_indexscan;
RESET enable_bitmapscan;
