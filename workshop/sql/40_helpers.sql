-- The whole recommender, in SQL.
--
-- Everything here is a thin wrapper over `embed()` and the `<=>` cosine
-- distance operator.  `\sf search` on stage is the point: the application is
-- six lines of SQL, not a service.

-- The vector of an existing beer, for "more like this".
CREATE OR REPLACE FUNCTION beer_vec(beer_id integer)
RETURNS vector(384)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v vector(384);
BEGIN
    SELECT embedding INTO v FROM beers WHERE id = beer_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'beer % not found', beer_id
            USING HINT = 'List candidates with: SELECT id, beer_name FROM beers LIMIT 10;';
    END IF;
    IF v IS NULL THEN
        RAISE EXCEPTION 'beer % has no embedding yet', beer_id
            USING HINT = 'Embed it with: SELECT refresh_embeddings();';
    END IF;
    RETURN v;
END;
$$;

-- Semantic search over free text.  Single-statement SQL so the planner inlines
-- it: EXPLAIN shows the HNSW index scan, not a black box.  The query is
-- embedded once per call, in an InitPlan, not once per row.
CREATE OR REPLACE FUNCTION search(q text, n integer DEFAULT 5)
RETURNS TABLE (id integer, beer_name text, brewery text, style text, distance numeric)
LANGUAGE sql
STABLE
AS $$
    SELECT b.id,
           b.beer_name,
           b.brewery,
           b.style,
           round((b.embedding <=> (SELECT embed(q)))::numeric, 4)
    FROM beers b
    ORDER BY b.embedding <=> (SELECT embed(q))
    LIMIT n
$$;

COMMENT ON FUNCTION search(text, integer) IS
    'Top-n beers by cosine distance to the embedding of the given text.';

-- "More like this" for a row that is already embedded: no model call at all.
CREATE OR REPLACE FUNCTION similar_to(beer_id integer, n integer DEFAULT 5)
RETURNS TABLE (id integer, beer_name text, brewery text, style text, distance numeric)
LANGUAGE sql
STABLE
AS $$
    SELECT b.id,
           b.beer_name,
           b.brewery,
           b.style,
           round((b.embedding <=> (SELECT beer_vec(beer_id)))::numeric, 4)
    FROM beers b
    WHERE b.id <> beer_id
    ORDER BY b.embedding <=> (SELECT beer_vec(beer_id))
    LIMIT n
$$;

COMMENT ON FUNCTION similar_to(integer, integer) IS
    'Top-n beers nearest to an existing beer, reusing its stored vector.';

-- Rows whose text has no embedding, or whose text changed since it was made.
CREATE OR REPLACE VIEW stale_beers AS
    SELECT id, beer_name, brewery, style, embedded_at
    FROM beers
    WHERE info <> ''
      AND (
            embedding IS NULL
         OR embedded_at IS NULL
         OR text_hash IS DISTINCT FROM encode(sha256(convert_to(info, 'UTF8')), 'hex')
      );

COMMENT ON VIEW stale_beers IS
    'Beers waiting to be embedded: new rows, or rows whose info text changed.';

-- Asynchronous refresh, called every minute by pg_cron.  One ONNX Runtime
-- call per batch rather than one per row.
CREATE OR REPLACE FUNCTION refresh_embeddings(batch_size integer DEFAULT 64)
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
    ids       integer[];
    infos     text[];
    vectors   vector(384)[];
    processed integer := 0;
    n         integer;
BEGIN
    LOOP
        SELECT array_agg(s.id ORDER BY s.id), array_agg(s.info ORDER BY s.id)
        INTO ids, infos
        FROM (
            SELECT b.id, b.info
            FROM beers b
            WHERE b.id IN (SELECT st.id FROM stale_beers st)
            ORDER BY b.id
            LIMIT batch_size
        ) s;

        EXIT WHEN ids IS NULL;

        vectors := embed_batch(infos);

        UPDATE beers b
        SET embedding   = vectors[i.ord],
            text_hash   = encode(sha256(convert_to(b.info, 'UTF8')), 'hex'),
            embedded_at = now()
        FROM unnest(ids) WITH ORDINALITY AS i(id, ord)
        WHERE b.id = i.id;

        n := array_length(ids, 1);
        processed := processed + n;
        EXIT WHEN n < batch_size;
    END LOOP;

    RETURN processed;
END;
$$;

COMMENT ON FUNCTION refresh_embeddings(integer) IS
    'Embed every stale beer in batches; returns how many rows were refreshed.';

-- Synchronous alternative, attached by attendees in exercise 05.
CREATE OR REPLACE FUNCTION embed_on_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.embedding   := embed_document(NEW.info);
    NEW.text_hash   := encode(sha256(convert_to(NEW.info, 'UTF8')), 'hex');
    NEW.embedded_at := now();
    NEW.updated_at  := now();
    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION embed_on_write() IS
    'BEFORE INSERT OR UPDATE trigger function: embed the row as it is written.';
