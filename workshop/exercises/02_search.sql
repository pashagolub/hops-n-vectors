-- ============================================================
-- 02 | Teach PostgreSQL to read
--
-- The model is not a service you call over the network.  It runs inside
-- this database.  embed() turns any text into 384 numbers; the <=> operator
-- measures how close two of those number-lists are.
--
-- The script stops after every step and waits for Enter.
-- ============================================================

\pset pager off
-- Print each statement before its result, so the query is on screen with its answer.
\set ECHO queries
\timing on

\echo ''
\echo '== [1] What a word looks like to a machine =================='
-- 384 numbers.  The model that produced them runs in this backend process.

SELECT embed('lemon');

\i /workshop/tui/pause.psql
\echo ''
\echo '== [2] Meaning has geometry ================================='
-- Close in meaning gives a small distance.  Nothing here touches the beer table.

SELECT embed('lemon') <=> embed('citrus zest')   AS lemon_vs_citrus_zest,
       embed('lemon') <=> embed('diesel engine') AS lemon_vs_diesel_engine;

\i /workshop/tui/pause.psql
\echo ''
\echo '== [3] Semantic search is an ORDER BY ======================='
-- Every beer already carries a vector.  Sort by distance to the question.
-- The word "lemon" does not have to appear in the text.

SELECT beer_name
FROM beers
ORDER BY embedding <=> embed('lemon')
LIMIT 5;

\i /workshop/tui/pause.psql
\echo ''
\echo '== [4] More like this ======================================='
-- No model call at all: beer 10462, Zywiec Lager, already carries its vector.

SELECT * FROM similar_to(10462);

\i /workshop/tui/pause.psql
\echo ''
\echo '== [5] There is no magic, only SQL =========================='
-- search() is the query from step [3] with a name.

\sf search

\echo ''
\echo '  YOUR TURN.  Type  :beer  and ask in your own words.'
\i /workshop/tui/more.psql
\if :more

\echo ''
\echo '== [6] Ask the way you would ask a friend ==================='

SELECT * FROM search('dark roasty coffee chocolate');
SELECT * FROM search('crisp refreshing beer for a hot summer day');
SELECT * FROM search('strong dark baltic porter smooth velvety');

\i /workshop/tui/pause.psql
\echo ''
\echo '== [7] Baltic Porter, a style with local roots =============='

SELECT * FROM similar_to(11149);

\i /workshop/tui/pause.psql
\echo ''
\echo '== [8] The plan behind search() ============================='

EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF, SUMMARY OFF)
SELECT * FROM search('lemon');

\echo ''
\echo '  More to try:'
\echo '    SELECT * FROM search(''something smoky to drink by a bonfire'');'
\echo '    SELECT * FROM search(''beer for someone who says they hate beer'', 10);'
\endif

\echo ''
\echo '  Next:  \\i /workshop/03_indexes.sql'
\echo ''
\set ECHO none
