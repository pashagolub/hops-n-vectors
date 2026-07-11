-- 06_iterative_scan.sql
-- =====================
-- WHAT THIS DEMONSTRATES
--   pgvector >= 0.8.0 fixes the filtering shortfall from 05 with
--   ITERATIVE SCAN: when the filter discards candidates, the index scan
--   automatically resumes and fetches more until LIMIT is satisfied
--   (or a safety cap is hit).
--
--   Modes:
--     hnsw.iterative_scan    = off | strict_order | relaxed_order
--     ivfflat.iterative_scan = off | relaxed_order
--   relaxed_order allows slightly out-of-order results (better recall);
--   strict_order preserves exact distance order.
--
-- EXPECTED OBSERVATIONS
--   The exact query that returned 0 rows in 05 now returns all 10 rows,
--   with only a modest latency increase (visible in EXPLAIN ANALYZE).

SET enable_seqscan = off;   -- same forced-ANN setup as 05

\echo '=== Before: iterative scan off — 0 of 10 rows (the 05 pitfall) ==='
SET hnsw.iterative_scan = off;
SELECT count(*) AS rows_returned
FROM (
    SELECT id
    FROM beers
    WHERE abv > 12
    ORDER BY embedding <=> (SELECT embedding FROM beers WHERE id = 1)
    LIMIT 10
) q;

\echo ''
\echo '=== After: hnsw.iterative_scan = relaxed_order — LIMIT satisfied ==='
SET hnsw.iterative_scan = relaxed_order;

EXPLAIN ANALYZE
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

\echo ''
\echo '=== Tuning knobs ==='
-- How far the iterative scan may go before giving up:
SHOW hnsw.max_scan_tuples;        -- default 20000
-- strict_order variant: exact ordering, slightly slower:
SET hnsw.iterative_scan = strict_order;
SELECT count(*) AS rows_strict
FROM (
    SELECT id
    FROM beers
    WHERE abv > 12
    ORDER BY embedding <=> (SELECT embedding FROM beers WHERE id = 1)
    LIMIT 10
) q;

RESET hnsw.iterative_scan;
RESET enable_seqscan;
