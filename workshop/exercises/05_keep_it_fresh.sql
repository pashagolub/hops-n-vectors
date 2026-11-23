-- ============================================================
-- 05 | Keep it alive
--
-- A recommender that only knows yesterday's catalogue is a demo, not a
-- product.  New rows must get vectors, and edited rows must get new ones.
--
-- Two ways, both entirely inside PostgreSQL:
--   async - a scheduled job sweeps up whatever is stale   (already running)
--   sync  - a trigger embeds the row as it is written     (you add it)
--
-- The script asks you for a beer, then stops after every step and waits
-- for Enter.
-- ============================================================

\pset pager off

-- Ask for a beer.  Pressing Enter three times brews the built-in Vector Sour.
-- With nopause set there is nobody to ask, so the defaults are used.
\set beer_name ''
\set beer_desc ''
\set beer_ask ''
\if :{?nopause}
\else
    \echo ''
    \echo '  Brew a beer of your own.  Enter alone keeps the suggestion in brackets.'
    \echo ''
    \prompt '  Name your beer [Vector Sour]: ' beer_name
    \prompt '  Describe it [a tart gose with smoked cheese, brewed on stage]: ' beer_desc
    \prompt '  How would a customer ask for it? [sour beer with smoked cheese]: ' beer_ask
\endif

\set QUIET on
\timing off
\set ECHO none
SELECT coalesce(nullif(btrim(:'beer_name'), ''), 'Vector Sour') AS beer_name,
       coalesce(nullif(btrim(:'beer_desc'), ''),
                'A tart gose brewed live on stage at a PostgreSQL workshop in Warsaw, '
                'soured with Lublin hops and finished with oscypek smoked sheep cheese. '
                'Tasting notes: Tart, Smoky, Salty. Pairs well with: Cured Meats. '
                'Brewed in Poland.') AS beer_desc,
       coalesce(nullif(btrim(:'beer_ask'), ''),
                'sour beer brewed at a postgres workshop with smoked cheese') AS beer_ask
\gset
-- Print each statement before its result, so the query is on screen with its answer.
\set ECHO queries
\timing on
\set QUIET off

\echo ''
\echo '== [1] Your beer exists, but the search cannot see it ======='
-- The row has no vector yet.  These three statements run without a pause,
-- because the scheduled job could embed the row while you wait.

INSERT INTO beers (beer_name, brewery, style, abv, info)
VALUES (:'beer_name', 'WAWTech Homebrew', 'ALE, Sour  Wild Ale', 4.9,
        :'beer_name' || ' Style: ALE, Sour  Wild Ale. ' || :'beer_desc')
RETURNING id AS beer_id \gset

SELECT id, beer_name, embedded_at FROM stale_beers;
SELECT * FROM search(:'beer_ask', 3);

\i /workshop/tui/pause.psql
\echo ''
\echo '== [2] The scheduled job catches it ========================='
-- pg_cron runs refresh_embeddings() every minute.  Do not wait for it:

SELECT refresh_embeddings() AS rows_embedded;

SELECT j.jobname, d.status, d.return_message, d.start_time
FROM cron.job_run_details d JOIN cron.job j USING (jobid)
ORDER BY d.start_time DESC LIMIT 3;

\i /workshop/tui/pause.psql
\echo ''
\echo '== [3] Now the database knows what you brewed ==============='

SELECT * FROM search(:'beer_ask', 3);
SELECT * FROM similar_to(:beer_id, 3);

\i /workshop/tui/pause.psql
\echo ''
\echo '== [4] Or embed at write time, with a trigger ==============='
-- No waiting, no job.  The cost moves to whoever does the INSERT.

DROP TRIGGER IF EXISTS beers_embed ON beers;
CREATE TRIGGER beers_embed
    BEFORE INSERT OR UPDATE OF info ON beers
    FOR EACH ROW EXECUTE FUNCTION embed_on_write();

UPDATE beers
SET info = info || ' Now double dry-hopped with Marynka and Lublin hops.'
WHERE id = :beer_id;

SELECT count(*) AS still_stale FROM stale_beers;

\echo ''
\echo '  Zero. The vector was rebuilt inside the UPDATE - look at the timing.'
\echo ''
\echo '  Async is cheap writes and eventual freshness.'
\echo '  Sync is instant freshness paid for on every write.'
\echo '  Pick per table, not per religion.'

\echo ''
\echo '  The next step removes your beer and the trigger, so this script can run again.'
\i /workshop/tui/pause.psql
\echo ''
\echo '== [5] Tidy up =============================================='

DROP TRIGGER IF EXISTS beers_embed ON beers;
DELETE FROM beers WHERE id > 12656;

\echo ''
\echo '  That is the whole workshop. Homework:'
\echo '    \\i /workshop/06_ivfflat.sql            -- a different index, different trade-off'
\echo '    \\i /workshop/07_similarity_limits.sql  -- where similarity stops being logic'
\echo ''
\set ECHO none
