-- ============================================================
-- 04 | Sharp edges
--
-- Two things that will bite you in production, and both are demonstrated
-- here in about thirty seconds each.
--
--   A. An approximate index plus a WHERE clause can silently lose rows.
--   B. Semantic search only knows what you put in the text.
-- ============================================================

\pset pager off
\timing on

\echo ''
\echo '== A1. The honest answer: 10 strong beers, no index used ===='

SELECT count(*) AS beers_above_12_percent FROM beers WHERE abv > 12;

SET enable_indexscan = off;
SET enable_bitmapscan = off;

SELECT b.beer_name, b.abv, round((b.embedding <=> (SELECT embed('strong sweet dessert beer')))::numeric, 4) AS distance
FROM beers b
WHERE b.abv > 12
ORDER BY b.embedding <=> (SELECT embed('strong sweet dessert beer'))
LIMIT 10;

RESET enable_indexscan;
RESET enable_bitmapscan;

\echo ''
\echo '== A2. The same query, using the HNSW index ================='
-- The index fetches ef_search candidates FIRST, then applies WHERE.
-- Only 181 of 12,656 beers are above 12% - so the candidates all get filtered away.

SET enable_seqscan = off;
SET hnsw.iterative_scan = off;
SHOW hnsw.ef_search;

SELECT b.beer_name, b.abv
FROM beers b
WHERE b.abv > 12
ORDER BY b.embedding <=> (SELECT embed('strong sweet dessert beer'))
LIMIT 10;

\echo ''
\echo '  No error.  No warning.  Just missing rows. This is the bug you ship.'

\echo ''
\echo '== A3. The fix: let the index keep walking =================='

SET hnsw.iterative_scan = relaxed_order;

SELECT b.beer_name, b.abv, round((b.embedding <=> (SELECT embed('strong sweet dessert beer')))::numeric, 4) AS distance
FROM beers b
WHERE b.abv > 12
ORDER BY b.embedding <=> (SELECT embed('strong sweet dessert beer'))
LIMIT 10;

RESET ALL;

\echo ''
\echo '== B. Vectors only know the text you gave them =============='
-- The Warsaw question.  The dataset says "Cured Meats", never "kielbasa",
-- and only 1,196 of 12,656 beers list any food pairing at all.

SELECT * FROM search('something to pair with grilled kielbasa and pierogi', 5);

\echo ''
\echo '  Kombucha. Because most rows have no food data, and the model'
\echo '  latched onto "grilled" and "pineapple".'
\echo ''
\echo '  Combine meaning with a plain old WHERE clause and it behaves:'

SELECT b.beer_name, b.style,
       round((b.embedding <=> (SELECT embed('rich malty beer for smoked sausage')))::numeric, 4) AS distance
FROM beers b
WHERE b.info ILIKE '%Cured Meats%'
ORDER BY b.embedding <=> (SELECT embed('rich malty beer for smoked sausage'))
LIMIT 5;

\echo ''
\echo '  Lesson: embeddings are a ranking tool, not a knowledge base.'
\echo '  SQL is very good at the parts they are bad at.'
\echo ''
\echo '  Next:  \i /workshop/05_keep_it_fresh.sql'
\echo ''
