-- ============================================================
-- GUD-003 | 03_hnsw.sql
-- DEMONSTRATES: HNSW index — Hierarchical Navigable Small World
--   graph-based ANN; high recall, sub-linear query time
-- EXPECTED OBSERVATIONS:
--   * "Index Scan using beers_embedding_hnsw"
--   * Far fewer buffers read vs Seq Scan in 02_explain_no_index.sql
--   * Much lower execution time; same top-5 results as brute force
-- LEAVES STATE: beers_embedding_hnsw index EXISTS
-- ============================================================

\pset pager off

\echo ''
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo '  03 · HNSW index — approximate nearest-neighbour search'
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'

\echo ''
\echo '── Creating HNSW index ──'

CREATE INDEX beers_embedding_hnsw
    ON beers USING hnsw (embedding vector_cosine_ops);

\echo ''
\echo '── EXPLAIN ANALYZE: same top-5 query — now using HNSW ──'
\echo ''

EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT
    beer_name,
    style,
    round((embedding <=> (SELECT embedding FROM beers WHERE id = 10462))::numeric, 4) AS cosine_dist
FROM beers
WHERE id <> 10462
ORDER BY embedding <=> (SELECT embedding FROM beers WHERE id = 10462)
LIMIT 5;
