-- ============================================================
-- 02 | Teach PostgreSQL to read
--
-- The model is not a service you call over the network.  It runs inside
-- this database.  embed() turns any text into 384 numbers; the <=> operator
-- measures how close two of those number-lists are.
--
-- Run it, then STOP READING and type your own questions.
-- ============================================================

\pset pager off
\timing on

\echo ''
\echo '== [1] What a sentence looks like to a machine =============='

SELECT left(embed('a crisp golden lager')::text, 90) || ' ...' AS the_first_few_dimensions;
SELECT vector_dims(embed('a crisp golden lager')) AS dimensions;

\echo ''
\echo '== [2] Meaning has geometry ================================='
-- Close in meaning => small distance.  Nothing here touches the beer table.

SELECT pair, round(distance::numeric, 4) AS cosine_distance
FROM (
    VALUES
        ('lemon        vs citrus zest',   (embed('lemon') <=> embed('citrus zest'))::float),
        ('lemon        vs grapefruit',    (embed('lemon') <=> embed('grapefruit'))::float),
        ('lemon        vs diesel engine', (embed('lemon') <=> embed('diesel engine'))::float)
) t(pair, distance);

\echo ''
\echo '== [3] Search, in one function call ========================='
-- The word "lemon" never has to appear in the text.

SELECT * FROM search('lemon');

\echo ''
\echo '== [4] Ask the way you would ask a friend ==================='

SELECT * FROM search('dark roasty coffee chocolate');
SELECT * FROM search('crisp refreshing beer for a hot summer day');
SELECT * FROM search('strong dark baltic porter smooth velvety');

\echo ''
\echo '== [5] More like this ======================================='
-- No model call at all: beer 10462 already carries its vector.

SELECT beer_name, brewery, style FROM beers WHERE id = 10462;
SELECT * FROM similar_to(10462);

\echo ''
\echo '== [6] There is no magic, only SQL =========================='

\sf search

EXPLAIN (ANALYZE, COSTS OFF, TIMING OFF, SUMMARY OFF)
SELECT * FROM search('lemon');

\echo ''
\echo '  YOUR TURN.  Try, and invent your own:'
\echo '    SELECT * FROM search(''something smoky to drink by a bonfire'');'
\echo '    SELECT * FROM search(''beer for someone who says they hate beer'', 10);'
\echo '    SELECT * FROM similar_to(11149);   -- Komes Baltic Porter'
\echo ''
\echo '  Next:  \i /workshop/03_indexes.sql'
\echo ''
