-- Hops'n'Vectors workshop: the embedding model lives inside PostgreSQL.
--
-- No external service, no GPU, no network.  A quantized ONNX export of
-- sentence-transformers/all-MiniLM-L12-v2 is baked into the image and executed
-- by ONNX Runtime inside the PostgreSQL backend through plpython3u.
--
--   SELECT embed('lemon');                    -- 384-dimensional unit vector
--   SELECT embed_batch(ARRAY['lemon','oak']); -- one session.run() for many texts
--
-- The model and tokenizer are loaded lazily, once per backend, and cached in
-- the plpython3u session dictionary (GD), so the first call in a session costs
-- ~0.5-1 s and every later call is milliseconds.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS plpython3u;

-- Loads tokenizer + ONNX Runtime session into GD and publishes a single
-- `encode(list[str]) -> list[str]` callable that the SQL-facing functions use.
-- GD is shared by every plpython3u function in the same session, so embed()
-- and embed_batch() share one model instance.
CREATE OR REPLACE FUNCTION hnv_init()
RETURNS void
LANGUAGE plpython3u
AS $py$
if "hnv_encode" in GD:
    return

import os

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

model_dir = os.environ.get("HNV_MODEL_DIR", "/opt/model")
max_len = int(os.environ.get("HNV_MAX_SEQ_LENGTH", "128"))
threads = int(os.environ.get("HNV_ORT_THREADS", "2"))

tokenizer = Tokenizer.from_file(os.path.join(model_dir, "tokenizer.json"))
tokenizer.enable_truncation(max_length=max_len)
tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")

opts = ort.SessionOptions()
opts.intra_op_num_threads = threads
opts.inter_op_num_threads = 1
opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
session = ort.InferenceSession(
    os.path.join(model_dir, "model.onnx"),
    sess_options=opts,
    providers=["CPUExecutionProvider"],
)
wanted = {i.name for i in session.get_inputs()}


def encode(texts, prefix=""):
    """Mean-pooled, L2-normalised sentence embeddings as pgvector literals.

    Retrieval models are often asymmetric: the question and the document are
    embedded with different instructions.  `prefix` carries that instruction.
    """
    if prefix:
        texts = [prefix + t for t in texts]
    encodings = tokenizer.encode_batch(list(texts))
    ids = np.array([e.ids for e in encodings], dtype=np.int64)
    mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
    feed = {"input_ids": ids, "attention_mask": mask}
    if "token_type_ids" in wanted:
        feed["token_type_ids"] = np.array(
            [e.type_ids for e in encodings], dtype=np.int64
        )
    feed = {k: v for k, v in feed.items() if k in wanted}

    hidden = session.run(None, feed)[0]                      # (batch, tokens, 384)
    weights = mask[..., None].astype(np.float32)
    pooled = (hidden * weights).sum(axis=1) / np.clip(
        weights.sum(axis=1), 1e-9, None
    )                                                        # masked mean pooling
    pooled /= np.clip(
        np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12, None
    )                                                        # unit length
    return ["[" + ",".join(repr(float(v)) for v in row) + "]" for row in pooled]


GD["hnv_encode"] = encode
GD["hnv_query_prefix"] = os.environ.get("HNV_QUERY_PREFIX", "")
GD["hnv_document_prefix"] = os.environ.get("HNV_DOCUMENT_PREFIX", "")
GD["hnv_model"] = os.path.basename(os.path.realpath(os.path.join(model_dir, "model.onnx")))
$py$;

COMMENT ON FUNCTION hnv_init() IS
    'Lazily loads the ONNX embedding model into the backend session (GD).';

-- Embed one text.  IMMUTABLE so the planner can fold it into an InitPlan and
-- evaluate it once per query instead of once per row.
CREATE OR REPLACE FUNCTION embed(t text)
RETURNS vector(384)
LANGUAGE plpython3u
IMMUTABLE
STRICT
PARALLEL RESTRICTED
AS $py$
if "hnv_encode" not in GD:
    plpy.execute("SELECT hnv_init()")
return GD["hnv_encode"]([t], GD["hnv_query_prefix"])[0]
$py$;

COMMENT ON FUNCTION embed(text) IS
    'Embed a search question into a 384-dimensional unit vector, in-database.';

-- The same model, asked to encode a document rather than a question.
CREATE OR REPLACE FUNCTION embed_document(t text)
RETURNS vector(384)
LANGUAGE plpython3u
IMMUTABLE
STRICT
PARALLEL RESTRICTED
AS $py$
if "hnv_encode" not in GD:
    plpy.execute("SELECT hnv_init()")
return GD["hnv_encode"]([t], GD["hnv_document_prefix"])[0]
$py$;

COMMENT ON FUNCTION embed_document(text) IS
    'Embed a stored document; retrieval models encode questions and documents differently.';

-- Embed many texts with a single ONNX Runtime call: the data pipeline and
-- refresh_embeddings() use this instead of calling embed() row by row.
CREATE OR REPLACE FUNCTION embed_batch(texts text[])
RETURNS vector(384)[]
LANGUAGE plpython3u
IMMUTABLE
STRICT
PARALLEL RESTRICTED
AS $py$
if "hnv_encode" not in GD:
    plpy.execute("SELECT hnv_init()")
items = [t if t is not None else "" for t in texts]
if not items:
    return []
return GD["hnv_encode"](items, GD["hnv_document_prefix"])
$py$;

COMMENT ON FUNCTION embed_batch(text[]) IS
    'Embed an array of documents in one ONNX Runtime call; NULLs embed as empty text.';

-- Model provenance, surfaced by 00_check.sql and verify.sql.
CREATE OR REPLACE FUNCTION embed_model_info()
RETURNS TABLE (setting text, value text)
LANGUAGE plpython3u
AS $py$
import os

import onnxruntime as ort
import tokenizers

if "hnv_encode" not in GD:
    plpy.execute("SELECT hnv_init()")

model_dir = os.environ.get("HNV_MODEL_DIR", "/opt/model")
model_path = os.path.join(model_dir, "model.onnx")
return [
    ("model", os.environ.get("HNV_MODEL_NAME", "unknown")),
    ("model_file", GD.get("hnv_model", "model.onnx")),
    ("model_bytes", str(os.path.getsize(model_path))),
    ("dimensions", "384"),
    ("max_seq_length", os.environ.get("HNV_MAX_SEQ_LENGTH", "128")),
    ("onnxruntime", ort.__version__),
    ("tokenizers", tokenizers.__version__),
]
$py$;

COMMENT ON FUNCTION embed_model_info() IS
    'Reports which embedding model and runtime versions this image carries.';
