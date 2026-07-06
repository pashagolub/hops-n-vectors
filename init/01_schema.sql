CREATE EXTENSION IF NOT EXISTS vector;

-- The bundled dataset is UTF-8 CSV. The upstream snapshot currently includes a
-- UTF-8 BOM on the first header field, so loader code must normalize headers
-- before strict validation rather than relying on raw byte-for-byte matching.
-- PostgreSQL stores text as UTF-8 in this database; no additional encoding
-- conversion is performed in the schema layer.

CREATE TABLE IF NOT EXISTS beers (
	id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	beer_name text NOT NULL,
	brewery text,
	style text,
	abv numeric(5,2),
	min_ibu integer,
	max_ibu integer,
	astringency integer,
	body integer,
	alcohol integer,
	bitter integer,
	sweet integer,
	sour integer,
	salty integer,
	fruits integer,
	hoppy integer,
	spices integer,
	malty integer,
	review_aroma numeric(4,3),
	review_appearance numeric(4,3),
	review_palate numeric(4,3),
	review_taste numeric(4,3),
	review_overall numeric(4,3),
	number_of_reviews integer,
	info text,
	text_hash text,
	embedding vector(384),
	embedded_at timestamptz,
	updated_at timestamptz NOT NULL DEFAULT now(),
	UNIQUE (beer_name, brewery, style)
);

COMMENT ON TABLE beers IS 'Bundled beer showcase dataset loaded from the Kaggle Beer Profile and Ratings snapshot.';
COMMENT ON COLUMN beers.info IS 'Composed embedding source text: name, style, description/notes, and key taste attributes.';
COMMENT ON COLUMN beers.text_hash IS 'sha256(info), used to detect rows requiring re-embedding.';
COMMENT ON COLUMN beers.embedding IS '384-dimensional sentence-transformers/all-MiniLM-L12-v2 vector.';

CREATE TABLE IF NOT EXISTS dataset_meta (
	key text PRIMARY KEY,
	value text
);

COMMENT ON TABLE dataset_meta IS 'Dataset provenance and load metadata for the bundled beer CSV snapshot.';
