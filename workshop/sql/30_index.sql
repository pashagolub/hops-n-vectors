-- Approximate nearest-neighbour index over the beer embeddings.
--
-- Same definition the exercises re-create in 03_indexes.sql, so what attendees
-- build by hand is exactly what the image ships with.
CREATE INDEX IF NOT EXISTS beers_embedding_hnsw
    ON beers USING hnsw (embedding vector_cosine_ops);

-- Identity values arrive from the dump with explicit ids; keep the sequence
-- ahead of them so attendee INSERTs get fresh ids.
SELECT setval(
    pg_get_serial_sequence('beers', 'id'),
    GREATEST(coalesce((SELECT max(id) FROM beers), 1), 1)
);

ANALYZE beers;
