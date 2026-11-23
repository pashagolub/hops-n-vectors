-- Maintainer/CI acceptance checks.  Fails loudly via ASSERT; attendees use
-- /workshop/00_check.sql instead, which explains rather than aborts.
\set ON_ERROR_STOP on
\pset pager off

SELECT extname, extversion FROM pg_extension
WHERE extname IN ('vector', 'plpython3u', 'pg_cron') ORDER BY extname;

SELECT * FROM embed_model_info();

DO $$
DECLARE
    expected constant int := 12656;
    n int;
BEGIN
    ASSERT vector_dims(embed('lemon')) = 384, 'embed() must return 384 dimensions';
    ASSERT round((embed('lemon') <=> embed('lemon'))::numeric, 6) = 0,
        'identical texts must have zero cosine distance';
    ASSERT (embed('lemon') <=> embed('citrus zest')) < (embed('lemon') <=> embed('diesel engine')),
        'related texts must be closer than unrelated ones';
    ASSERT array_length(embed_batch(ARRAY['a', 'b', 'c']), 1) = 3,
        'embed_batch() must return one vector per input';

    SELECT count(*) INTO n FROM beers;
    IF n = 0 THEN
        RAISE NOTICE 'no dataset in this image - skipping data assertions';
        RETURN;
    END IF;

    ASSERT n = expected, format('expected %s beers, found %s', expected, n);

    SELECT count(*) INTO n FROM beers WHERE embedding IS NULL;
    ASSERT n = 0, format('%s beers are missing an embedding', n);

    SELECT count(*) INTO n FROM stale_beers;
    ASSERT n = 0, format('%s beers are stale on a fresh image', n);

    ASSERT (SELECT beer_name FROM beers WHERE id = 10462) = 'Zywiec Lager',
        'id 10462 must be Zywiec Lager (identity values drifted)';
    ASSERT (SELECT beer_name FROM beers WHERE id = 11149) LIKE 'Komes%',
        'id 11149 must be the Komes Baltic Porter';
    ASSERT (SELECT beer_name FROM beers WHERE id = 1573) = 'Bud Light',
        'id 1573 must be Bud Light (used by the similarity-limits exercise)';
    ASSERT (SELECT last_value FROM beers_id_seq) >= expected,
        'the identity sequence must be ahead of the loaded rows';

    ASSERT EXISTS (SELECT 1 FROM pg_indexes
                   WHERE tablename = 'beers' AND indexname = 'beers_embedding_hnsw'),
        'the HNSW index must ship with the image';
    ASSERT EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'refresh-embeddings'),
        'the pg_cron refresh job must be registered';

    SELECT count(*) INTO n FROM search('lemon', 5);
    ASSERT n = 5, format('search() returned %s rows, expected 5', n);

    SELECT count(*) INTO n FROM similar_to(10462, 5) WHERE id = 10462;
    ASSERT n = 0, 'similar_to() must exclude the beer itself';

    RAISE NOTICE 'all workshop image checks passed';
END;
$$;
