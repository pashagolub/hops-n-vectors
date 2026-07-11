-- ============================================================
-- GUD-003 | 04_ivfflat.sql
-- DEMONSTRATES: IVFFlat index — inverted-file flat clustering ANN
--   lists = 57  (rule of thumb: ≈ sqrt(3197 rows) ≈ 57)
--   probes = N  controls how many clusters are searched at query time
-- EXPECTED OBSERVATIONS:
--   * "Index Scan using beers_embedding_ivfflat"
--   * probes=1  → fastest, lowest recall (only 1 cluster searched)
--   * probes=10 → better recall, slightly slower
--   * HNSW generally beats IVFFlat on both recall and speed at
--     this dataset size; IVFFlat shines for very large corpora
--     where HNSW memory use becomes prohibitive
-- LEAVES STATE: beers_embedding_hnsw EXISTS, beers_embedding_ivfflat ABSENT
-- ============================================================

\echo ''
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo '  04 · IVFFlat index — cluster-based ANN'
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'

\echo ''
\echo '── Step 1: drop HNSW so the planner picks IVFFlat ──'

DROP INDEX IF EXISTS beers_embedding_hnsw;

\echo ''
\echo '── Step 2: create IVFFlat (lists=57, ≈ sqrt(3197)) ──'

CREATE INDEX beers_embedding_ivfflat
    ON beers USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 57);

\echo ''
\echo '── Step 3: EXPLAIN ANALYZE — IVFFlat, probes=1 (default) ──'
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

\echo ''
\echo '── Step 4: raise probes → more clusters → better recall ──'

SET ivfflat.probes = 10;

EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT
    beer_name,
    style,
    round((embedding <=> (SELECT embedding FROM beers WHERE id = 807))::numeric, 4) AS cosine_dist
FROM beers
WHERE id <> 807
ORDER BY embedding <=> (SELECT embedding FROM beers WHERE id = 807)
LIMIT 5;

RESET ivfflat.probes;

\echo ''
\echo '── Step 5: restore HNSW for subsequent scripts ──'

DROP INDEX IF EXISTS beers_embedding_ivfflat;

CREATE INDEX beers_embedding_hnsw
    ON beers USING hnsw (embedding vector_cosine_ops);

\echo ''
\echo 'Final indexes on beers:'
SELECT indexname FROM pg_indexes WHERE tablename = 'beers' ORDER BY indexname;
