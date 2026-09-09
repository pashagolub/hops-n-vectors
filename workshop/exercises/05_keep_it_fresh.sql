-- ============================================================
-- 05 | Keep it alive
--
-- A recommender that only knows yesterday's catalogue is a demo, not a
-- product.  New rows must get vectors, and edited rows must get new ones.
--
-- Two ways, both entirely inside PostgreSQL:
--   async - a scheduled job sweeps up whatever is stale   (already running)
--   sync  - a trigger embeds the row as it is written     (you add it)
-- ============================================================

\pset pager off
\timing on

\echo ''
\echo '== [1] Brew something of your own ==========================='
-- Change the name and the description. Make it yours.

INSERT INTO beers (beer_name, brewery, style, abv, info)
VALUES ('Vector Sour', 'WAWTech Homebrew', 'ALE, Sour  Wild Ale', 4.9,
        'Vector Sour Style: ALE, Sour  Wild Ale. A tart gose brewed live on stage '
        'at a PostgreSQL workshop in Warsaw, soured with Lublin hops and finished '
        'with oscypek smoked sheep cheese. Tasting notes: Tart, Smoky, Salty. '
        'Pairs well with: Cured Meats. Brewed in Poland.');

\echo ''
\echo '== [2] It exists, but it is invisible ======================='
-- No vector yet, so the search cannot reach it.

SELECT id, beer_name, embedded_at FROM stale_beers;
SELECT * FROM search('sour beer brewed at a postgres workshop with smoked cheese', 3);

\echo ''
\echo '== [3] The scheduled job catches it ========================='
-- pg_cron runs refresh_embeddings() every minute. Wait, or do it now:

SELECT refresh_embeddings() AS rows_embedded;

SELECT j.jobname, d.status, d.return_message, d.start_time
FROM cron.job_run_details d JOIN cron.job j USING (jobid)
ORDER BY d.start_time DESC LIMIT 3;

\echo ''
\echo '== [4] Now the database knows what you brewed ==============='

SELECT * FROM search('sour beer brewed at a postgres workshop with smoked cheese', 3);
SELECT * FROM similar_to((SELECT id FROM beers WHERE beer_name = 'Vector Sour'), 3);

\echo ''
\echo '== [5] Or embed at write time, with a trigger ==============='
-- No waiting, no job. The cost moves to whoever does the INSERT.

CREATE TRIGGER beers_embed
    BEFORE INSERT OR UPDATE OF info ON beers
    FOR EACH ROW EXECUTE FUNCTION embed_on_write();

UPDATE beers
SET info = info || ' Now double dry-hopped with Marynka and Lublin hops.'
WHERE beer_name = 'Vector Sour';

SELECT count(*) AS still_stale FROM stale_beers;

\echo ''
\echo '  Zero. The vector was rebuilt inside the UPDATE - look at the timing.'
\echo ''
\echo '  Async is cheap writes and eventual freshness.'
\echo '  Sync is instant freshness paid for on every write.'
\echo '  Pick per table, not per religion.'

\echo ''
\echo '== [6] Tidy up so you can run this again ===================='

DROP TRIGGER IF EXISTS beers_embed ON beers;
DELETE FROM beers WHERE id > 12656;

\echo ''
\echo '  That is the whole workshop. Homework:'
\echo '    \i /workshop/06_ivfflat.sql            -- a different index, different trade-off'
\echo '    \i /workshop/07_similarity_limits.sql  -- where similarity stops being logic'
\echo ''
