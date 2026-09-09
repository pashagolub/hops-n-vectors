-- ============================================================
-- 03 | Make it fast
--
-- Comparing a question to 12,656 beers means 12,656 distance calculations.
-- That is fine here.  It is not fine at 12 million.
--
-- HNSW builds a navigable graph through the vector space, so the search
-- walks towards the answer instead of visiting everything.
-- ============================================================

\pset pager off
\timing on

\echo ''
\echo '== [1] Brute force: drop the index and look at every row ===='

DROP INDEX IF EXISTS beers_embedding_hnsw;

EXPLAIN (ANALYZE, BUFFERS, COSTS OFF)
SELECT b.beer_name
FROM beers b
ORDER BY b.embedding <=> (SELECT embed('dark roasty coffee chocolate'))
LIMIT 5;

\echo ''
\echo '  Look for: Seq Scan on beers, rows=12656, and a Top-N heapsort.'

\echo ''
\echo '== [2] Build the graph ======================================'
-- m = links per node, ef_construction = how hard we look while building.
-- Higher = better recall, slower build, bigger index.

CREATE INDEX beers_embedding_hnsw
    ON beers USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

\echo ''
\echo '== [3] The same query, now with the graph ==================='

EXPLAIN (ANALYZE, BUFFERS, COSTS OFF)
SELECT b.beer_name
FROM beers b
ORDER BY b.embedding <=> (SELECT embed('dark roasty coffee chocolate'))
LIMIT 5;

\echo ''
\echo '  Look for: Index Scan using beers_embedding_hnsw, and far fewer buffers.'

\echo ''
\echo '== [4] How big is the graph? ================================'

SELECT pg_size_pretty(pg_relation_size('beers'))                  AS table_size,
       pg_size_pretty(pg_relation_size('beers_embedding_hnsw'))   AS index_size;

\echo ''
\echo '  Next:  \i /workshop/04_sharp_edges.sql'
\echo ''
