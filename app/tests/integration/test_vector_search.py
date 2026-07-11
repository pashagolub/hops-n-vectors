"""Integration tests for vector-search ordering against a real pgvector DB.

Uses manually constructed unit vectors so results are deterministic without
downloading any ML model.  Also covers the incremental re-embed logic with a
mocked sentence-transformer model.
"""
from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Vector helpers
# ---------------------------------------------------------------------------


def _unit(dim: int, total: int = 384) -> list[float]:
    """Return a unit vector with 1.0 at *dim* and 0.0 elsewhere."""
    v = [0.0] * total
    v[dim] = 1.0
    return v


def _weighted(weights: dict[int, float], total: int = 384) -> list[float]:
    """Return a normalised vector from {dim: weight} pairs."""
    v = [0.0] * total
    for dim, w in weights.items():
        v[dim] = w
    mag = math.sqrt(sum(x * x for x in v))
    return [x / mag for x in v]


def _vec_literal(v: list[float]) -> str:
    return "[" + ",".join(str(x) for x in v) + "]"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def seeded_conn(conn):
    """Insert a small set of beers with deterministic embeddings and yield conn."""
    beers = [
        # (beer_name, brewery, style, info, vector)
        ("Lemon Wheat", "CitrusCo", "Wheat", "Lemon zesty citrus wheat beer", _unit(0)),
        ("Citrus IPA", "HopCo", "IPA", "Citrus orange grapefruit hops",
         _weighted({0: 0.9, 1: 0.1})),
        ("Chocolate Stout", "DarkCo", "Stout", "Rich dark chocolate malt stout", _unit(50)),
        ("Caramel Brown", "MaltCo", "Brown", "Sweet caramel toffee malt notes", _unit(51)),
        ("Neutral Lager", "PlainCo", "Lager", "Plain crisp refreshing lager",
         _weighted({100: 1.0})),
    ]
    with conn.cursor() as cur:
        for name, brewery, style, info, vec in beers:
            import hashlib
            h = hashlib.sha256(info.encode()).hexdigest()
            cur.execute(
                """
                INSERT INTO beers
                    (beer_name, brewery, style, info, text_hash, embedding, embedded_at)
                VALUES (%s, %s, %s, %s, %s, %s::vector, now())
                """,
                (name, brewery, style, info, h, _vec_literal(vec)),
            )
    conn.commit()
    yield conn


# ---------------------------------------------------------------------------
# Search ordering
# ---------------------------------------------------------------------------


def test_cosine_search_ordering(seeded_conn):
    """A query vector aligned with 'lemon' beers must rank them highest."""
    query = _vec_literal(_unit(0))  # identical to Lemon Wheat
    rows = seeded_conn.execute(
        """
        SELECT beer_name, embedding <=> %s::vector AS dist
        FROM   beers
        WHERE  embedding IS NOT NULL
        ORDER  BY dist
        LIMIT  3
        """,
        (query,),
    ).fetchall()
    assert len(rows) == 3
    names = [r[0] for r in rows]
    # Lemon Wheat (identical vector) must be first, Citrus IPA second.
    assert names[0] == "Lemon Wheat"
    assert names[1] == "Citrus IPA"
    # Chocolate and caramel-themed beers should NOT appear in top-2.
    assert "Chocolate Stout" not in names[:2]


def test_cosine_distance_self_is_zero(seeded_conn):
    """A beer's distance to its own vector must be 0 (identical vectors)."""
    query = _vec_literal(_unit(0))
    dist = seeded_conn.execute(
        "SELECT embedding <=> %s::vector FROM beers WHERE beer_name = 'Lemon Wheat'",
        (query,),
    ).fetchone()[0]
    assert abs(dist) < 1e-6


def test_orthogonal_vectors_have_max_distance(seeded_conn):
    """Two orthogonal unit vectors have cosine distance 1.0."""
    lemon_query = _vec_literal(_unit(0))
    dist = seeded_conn.execute(
        "SELECT embedding <=> %s::vector FROM beers WHERE beer_name = 'Neutral Lager'",
        (lemon_query,),
    ).fetchone()[0]
    assert abs(dist - 1.0) < 1e-5


def test_top_n_respected(seeded_conn):
    """LIMIT N must return exactly N rows."""
    query = _vec_literal(_unit(0))
    rows = seeded_conn.execute(
        "SELECT beer_name FROM beers WHERE embedding IS NOT NULL "
        "ORDER BY embedding <=> %s::vector LIMIT 2",
        (query,),
    ).fetchall()
    assert len(rows) == 2


# ---------------------------------------------------------------------------
# Incremental re-embed (mocked model)
# ---------------------------------------------------------------------------


def test_embed_pending_only_processes_unembedded(conn, tmp_path):
    """embed_pending() must only update rows where embedding IS NULL."""
    # Insert two rows: one pre-embedded (with correct text_hash), one pending.
    conn.execute(
        """
        INSERT INTO beers (beer_name, brewery, style, info, text_hash, embedding, embedded_at)
        VALUES (
            'Already Done', 'Co', 'IPA', 'some info',
            encode(sha256(convert_to('some info', 'UTF8')), 'hex'),
            %s::vector, now()
        )
        """,
        (_vec_literal(_unit(1)),),
    )
    conn.execute(
        """
        INSERT INTO beers (beer_name, brewery, style, info, text_hash)
        VALUES ('Needs Embed', 'Co', 'Stout', 'dark rich chocolate', 'stale_hash')
        """
    )
    conn.commit()

    fake_vector = np.array([_unit(2)], dtype=np.float32)

    mock_model = MagicMock()
    mock_model.encode.return_value = fake_vector

    with patch("hopsnvectors.embedder._load_model", return_value=mock_model):
        from hopsnvectors import embedder
        embedded = embedder.embed_pending(batch_size=10)

    assert embedded == 1, "Only the pending row should be embedded"
    # Pre-embedded row must retain its embedded_at timestamp (not NULL).
    pre = conn.execute(
        "SELECT embedded_at FROM beers WHERE beer_name = 'Already Done'"
    ).fetchone()[0]
    assert pre is not None


def test_embed_pending_updates_text_hash(conn):
    """After embedding, text_hash must match sha256(info)."""
    conn.execute(
        """
        INSERT INTO beers (beer_name, brewery, style, info, text_hash)
        VALUES ('Hash Test', 'Co', 'Lager', 'crisp lager info text', 'old_hash')
        """
    )
    conn.commit()

    fake_vector = np.array([[0.1] * 384], dtype=np.float32)
    mock_model = MagicMock()
    mock_model.encode.return_value = fake_vector

    with patch("hopsnvectors.embedder._load_model", return_value=mock_model):
        from hopsnvectors import embedder
        embedder.embed_pending(batch_size=10)

    mismatch = conn.execute(
        """
        SELECT count(*) FROM beers
        WHERE text_hash IS DISTINCT FROM
              encode(sha256(convert_to(info, 'UTF8')), 'hex')
        """
    ).fetchone()[0]
    assert mismatch == 0


def test_embed_pending_resumable(conn):
    """embed_pending() called twice on the same data must embed 0 rows second time."""
    conn.execute(
        """
        INSERT INTO beers (beer_name, brewery, style, info, text_hash)
        VALUES ('Resume Test', 'Co', 'IPA', 'info for resumable test', 'stale')
        """
    )
    conn.commit()

    fake_vector = np.array([[0.5] * 384], dtype=np.float32)
    mock_model = MagicMock()
    mock_model.encode.return_value = fake_vector

    with patch("hopsnvectors.embedder._load_model", return_value=mock_model):
        from hopsnvectors import embedder
        first = embedder.embed_pending(batch_size=10)
        second = embedder.embed_pending(batch_size=10)

    assert first == 1
    assert second == 0



# ---------------------------------------------------------------------------
# embed_pending with no pending rows + create_hnsw_index
# ---------------------------------------------------------------------------


def test_embed_pending_no_rows_returns_zero(conn):
    """embed_pending() must return 0 when no rows are pending."""
    # Insert a row that is already fully embedded and hash-synced.
    conn.execute(
        """
        INSERT INTO beers (beer_name, brewery, style, info, text_hash, embedding, embedded_at)
        VALUES (
            'Synced Beer', 'Co', 'IPA', 'fully embedded already',
            encode(sha256(convert_to('fully embedded already', 'UTF8')), 'hex'),
            %s::vector, now()
        )
        """,
        (_vec_literal(_unit(3)),),
    )
    conn.commit()

    mock_model = MagicMock()
    with patch("hopsnvectors.embedder._load_model", return_value=mock_model):
        from hopsnvectors import embedder
        result = embedder.embed_pending(batch_size=10)

    assert result == 0
    mock_model.encode.assert_not_called()


def test_create_hnsw_index_runs_cleanly(conn):
    """create_hnsw_index() must succeed idempotently on the test DB."""
    from hopsnvectors import embedder
    embedder.create_hnsw_index()  # first call
    embedder.create_hnsw_index()  # second call — IF NOT EXISTS guard

    result = conn.execute(
        "SELECT indexname FROM pg_indexes WHERE indexname = 'beers_embedding_hnsw'"
    ).fetchone()
    assert result is not None
