"""Batch embedding pipeline for beer rows.

Selects rows needing embeddings (new or stale) and updates them in batches
using the sentence-transformers all-MiniLM-L12-v2 model.  After the embedding
pass, creates the HNSW index on beers.embedding idempotently.

Entry points:
  python -m hopsnvectors.embedder          # embed pending rows + create index
  python -m hopsnvectors.embedder --once   # same (alias used by Phase 5 scheduler)
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import psycopg
from pgvector.psycopg import register_vector

from hopsnvectors.db import get_connection


_MODEL_NAME = "all-MiniLM-L12-v2"
_DEFAULT_BATCH_SIZE = int(os.environ.get("EMBED_BATCH_SIZE", "64"))

# Pending-row predicate reused by count and fetch queries.
_PENDING_WHERE = """
    info <> ''
    AND (
        embedding IS NULL
        OR embedded_at IS NULL
        OR text_hash IS DISTINCT FROM encode(sha256(convert_to(info, 'UTF8')), 'hex')
    )
"""


def _load_model():
    """Load the sentence-transformer model, caching it on the model-cache volume.

    Raises SystemExit with a human-readable message when the model cannot be
    loaded (e.g. cold cache with no network access, edge case 10).
    """
    os.environ.setdefault("HF_HOME", "/model-cache")
    try:
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415
        return SentenceTransformer(_MODEL_NAME)
    except Exception as exc:
        raise SystemExit(
            f"ERROR: Could not load model '{_MODEL_NAME}'.\n"
            "On first run the model is downloaded from Hugging Face (~90 MB).\n"
            "Ensure network access is available, then retry.\n"
            f"Detail: {exc}"
        ) from exc


def _count_pending(conn: psycopg.Connection) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM beers WHERE {_PENDING_WHERE}")
        row = cur.fetchone()
        return row[0] if row else 0


def embed_pending(batch_size: int = _DEFAULT_BATCH_SIZE) -> int:
    """Embed all pending beer rows and persist vectors to the database.

    Processes rows in batches with FOR UPDATE SKIP LOCKED so that concurrent
    invocations skip rows already being embedded (edge case 7).  Each batch is
    committed independently, so an interrupted run loses at most one batch and
    resumes cleanly on the next invocation (edge case 6).

    Returns the total number of rows embedded in this call.
    """
    model = _load_model()

    conn = get_connection(autocommit=True)
    register_vector(conn)

    total = _count_pending(conn)
    if total == 0:
        print("No rows pending embedding.", flush=True)
        conn.close()
        return 0

    print(f"Embedding {total} row(s) in batches of {batch_size}…", flush=True)
    embedded = 0

    while True:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, info
                    FROM beers
                    WHERE {_PENDING_WHERE}
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                    """,
                    (batch_size,),
                )
                rows = cur.fetchall()

            if not rows:
                break

            ids = [r[0] for r in rows]
            texts = [r[1] for r in rows]
            vectors = model.encode(texts, show_progress_bar=False)
            now = datetime.now(timezone.utc)

            with conn.cursor() as cur:
                cur.executemany(
                    """
                    UPDATE beers
                    SET embedding   = %s,
                        embedded_at = %s,
                        text_hash   = encode(sha256(convert_to(info, 'UTF8')), 'hex')
                    WHERE id = %s
                    """,
                    [(vectors[i], now, ids[i]) for i in range(len(ids))],
                )

        embedded += len(ids)
        pct = embedded * 100 // total
        print(f"embedding {embedded}/{total} ({pct}%)", flush=True)

    conn.close()
    return embedded


def create_hnsw_index() -> None:
    """Idempotently create the HNSW cosine-distance index on beers.embedding.

    IVFFlat is intentionally omitted — it is created and destroyed only within
    the demo scripts (demo/04_ivfflat.sql) per REQ-006.
    """
    conn = get_connection(autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS beers_embedding_hnsw
                ON beers USING hnsw (embedding vector_cosine_ops)
                """
            )
        print("HNSW index ready (beers_embedding_hnsw).", flush=True)
    finally:
        conn.close()


def main() -> None:
    embedded = embed_pending()
    create_hnsw_index()
    if embedded > 0:
        print(f"Done — embedded {embedded} row(s).", flush=True)
    print(
        "\nStack ready.  Next steps:\n"
        "  docker compose run --rm scheduler tui                  # interactive recommender\n"
        "  docker compose exec postgres psql -U beer -d beer     # explore with psql",
        flush=True,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Embed pending beer rows.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Embed all pending rows and exit (used by Phase 5 scheduler).",
    )
    parser.parse_args()
    main()
