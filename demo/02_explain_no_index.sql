-- ============================================================
-- GUD-003 | 02_explain_no_index.sql
-- DEMONSTRATES: Brute-force (sequential scan) vector search —
--   what PostgreSQL does WITHOUT an ANN index
-- EXPECTED OBSERVATIONS:
--   * "Seq Scan on beers"   — all ~3 200 rows are read
--   * "Sort" / "Limit" node — Top-N heapsort to find nearest 5
--   * Execution time notably higher than with HNSW (see 03_hnsw.sql)
-- LEAVES STATE: beers_embedding_hnsw index DROPPED
--   (script 03 recreates it)
-- ============================================================

\echo ''
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo '  02 · Sequential scan — no index baseline'
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'

\echo ''
\echo '── Dropping HNSW index ──'

DROP INDEX IF EXISTS beers_embedding_hnsw;

\echo ''
\echo '── EXPLAIN ANALYZE: top-5 cosine neighbours of beer #807 ──'
\echo '   (Centennial IPA — IPA-American, 7.2% ABV)'
\echo ''

EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT
    beer_name,
    style,
    round((embedding <=> (SELECT embedding FROM beers WHERE id = 807))::numeric, 4) AS cosine_dist
FROM beers
WHERE id <> 807
ORDER BY embedding <=> (SELECT embedding FROM beers WHERE id = 807)
LIMIT 5;
