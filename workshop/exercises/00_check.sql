-- 00 | Is my beer database ready?
--
--   docker exec -it beer psql
--   \i /workshop/00_check.sql
--
-- Everything below should say OK.  If anything says MISSING, reset with:
--   docker rm -fv beer
--   docker run -d --name beer -p 5432:5432 ghcr.io/pashagolub/hops-n-vectors:pg18

\pset pager off
\timing off

\echo '=== Extensions ============================================='
SELECT extname AS extension, extversion AS version
FROM pg_extension
WHERE extname IN ('vector', 'plpython3u', 'pg_cron')
ORDER BY extname;

\echo '=== The embedding model, inside this database =============='
SELECT * FROM embed_model_info();

\echo '=== Data ==================================================='
SELECT count(*)                         AS beers,
       count(embedding)                 AS embedded,
       (SELECT count(*) FROM stale_beers) AS stale
FROM beers;

\echo '=== Checklist =============================================='
SELECT item, CASE WHEN ok THEN 'OK' ELSE 'MISSING' END AS status
FROM (
    VALUES
        ('embed() works',      vector_dims(embed('lemon')) = 384),
        ('12656 beers loaded', (SELECT count(*) FROM beers) = 12656),
        ('all beers embedded', (SELECT count(*) FROM beers WHERE embedding IS NULL) = 0),
        ('HNSW index',         EXISTS (SELECT 1 FROM pg_indexes
                                       WHERE tablename = 'beers'
                                         AND indexname = 'beers_embedding_hnsw')),
        ('refresh job',        EXISTS (SELECT 1 FROM cron.job
                                       WHERE jobname = 'refresh-embeddings')),
        ('image ready',        EXISTS (SELECT 1 FROM dataset_meta
                                       WHERE key = 'workshop_ready' AND value = 'true'))
) AS t(item, ok);

\echo '=== First search ==========================================='
SELECT * FROM search('lemon', 3);

\echo ''
\echo 'Ready.  Next:  \i /workshop/01_operators.sql'
\echo ''
