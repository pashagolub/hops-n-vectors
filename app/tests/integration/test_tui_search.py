"""Integration tests for TUI search execution against a real pgvector DB.

Tests the Searcher class and run_query_json() with a mocked sentence-transformer
model and a real pgvector container.  This brings TUI coverage into the
≥ 80 % band required by the spec (§6 Coverage Requirements).
"""
from __future__ import annotations

import hashlib
import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Vector helpers
# ---------------------------------------------------------------------------


def _unit(dim: int, total: int = 384) -> list[float]:
    v = [0.0] * total
    v[dim] = 1.0
    return v


def _vec_literal(v: list[float]) -> str:
    return "[" + ",".join(str(x) for x in v) + "]"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def beer_db(conn):
    """Seed beers with deterministic embeddings and return conn."""
    beers = [
        ("Lemon Wheat", "CitrusCo", "Wheat", "Lemon citrus zesty wheat beer", _unit(0)),
        ("Citrus IPA",  "HopCo",    "IPA",   "Orange grapefruit hops citrus", _unit(0)),
        ("Chocolate Stout", "DarkCo", "Stout", "Rich dark chocolate malt", _unit(50)),
        ("Caramel Brown",   "MaltCo", "Brown", "Sweet caramel toffee notes",   _unit(51)),
        ("Neutral Lager",   "PlainCo","Lager", "Crisp refreshing plain lager", _unit(100)),
    ]
    with conn.cursor() as cur:
        for name, brewery, style, info, vec in beers:
            h = _sha256(info)
            cur.execute(
                """
                INSERT INTO beers
                    (beer_name, brewery, style, info, text_hash, embedding, embedded_at)
                VALUES (%s, %s, %s, %s, %s, %s::vector, now())
                """,
                (name, brewery, style, info, h, _vec_literal(vec)),
            )
    conn.commit()
    return conn


def _mock_model(query_dim: int = 0):
    """Return a mock SentenceTransformer that encodes any text as _unit(query_dim)."""
    m = MagicMock()
    m.encode.return_value = np.array(_unit(query_dim), dtype=np.float32)
    return m


# ---------------------------------------------------------------------------
# Searcher.by_prompt
# ---------------------------------------------------------------------------


def test_by_prompt_returns_results(beer_db):
    """by_prompt() must return a non-empty list of dicts with expected keys."""
    from hopsnvectors.tui import Searcher

    with patch("hopsnvectors.embedder._load_model", return_value=_mock_model(0)):
        searcher = Searcher()
        results = searcher.by_prompt("lemon", top=5)

    assert len(results) > 0
    assert "beer_name" in results[0]
    assert "distance" in results[0]


def test_by_prompt_ordering(beer_db):
    """Results closest to the query vector must rank first."""
    from hopsnvectors.tui import Searcher

    with patch("hopsnvectors.embedder._load_model", return_value=_mock_model(0)):
        searcher = Searcher()
        results = searcher.by_prompt("lemon", top=5)

    names = [r["beer_name"] for r in results]
    # Lemon Wheat and Citrus IPA both use _unit(0) — they must appear before stout/brown.
    assert names.index("Chocolate Stout") > 1
    assert names.index("Caramel Brown") > 1


def test_by_prompt_top_n(beer_db):
    """top=2 must return exactly 2 rows."""
    from hopsnvectors.tui import Searcher

    with patch("hopsnvectors.embedder._load_model", return_value=_mock_model(0)):
        results = Searcher().by_prompt("lemon", top=2)

    assert len(results) == 2


# ---------------------------------------------------------------------------
# Searcher.by_beer
# ---------------------------------------------------------------------------


def test_by_beer_returns_similar_beers(beer_db):
    """by_beer() must return beers similar to the reference beer."""
    # Get the ID of Lemon Wheat.
    beer_id = beer_db.execute(
        "SELECT id FROM beers WHERE beer_name = 'Lemon Wheat'"
    ).fetchone()[0]

    from hopsnvectors.tui import Searcher

    results = Searcher().by_beer(beer_id, top=3)
    assert len(results) > 0
    names = [r["beer_name"] for r in results]
    # Citrus IPA (same unit vector) should rank near top.
    assert "Citrus IPA" in names


def test_by_beer_invalid_id_raises(beer_db):
    """by_beer() with a non-existent ID must raise LookupError."""
    from hopsnvectors.tui import Searcher

    with pytest.raises(LookupError, match="not found"):
        Searcher().by_beer(999999, top=3)


# ---------------------------------------------------------------------------
# Searcher.explain
# ---------------------------------------------------------------------------


def test_explain_prompt_returns_plan(beer_db):
    """explain_prompt() must return a non-empty EXPLAIN ANALYZE plan string."""
    from hopsnvectors.tui import Searcher

    with patch("hopsnvectors.embedder._load_model", return_value=_mock_model(0)):
        plan = Searcher().explain_prompt("lemon", top=3)

    assert "Seq Scan" in plan or "Index Scan" in plan or "Bitmap" in plan or "Gather" in plan


# ---------------------------------------------------------------------------
# run_query_json  (non-interactive CI mode)
# ---------------------------------------------------------------------------


def test_run_query_json_valid(beer_db):
    """run_query_json must return valid JSON with ≥ 1 result for a valid prompt."""
    from hopsnvectors.tui import run_query_json

    with patch("hopsnvectors.embedder._load_model", return_value=_mock_model(0)):
        output = run_query_json("lemon", top=5)

    results = json.loads(output)
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "beer_name" in results[0]
    assert isinstance(results[0]["distance"], float)


def test_run_query_json_empty_prompt_raises(beer_db):
    """run_query_json must reject an empty prompt."""
    from hopsnvectors.tui import run_query_json

    with pytest.raises(SystemExit):
        run_query_json("", top=5)


def test_run_query_json_overlong_prompt_raises(beer_db):
    """run_query_json must reject prompts longer than 4,000 chars (edge case 4)."""
    from hopsnvectors.tui import run_query_json

    with pytest.raises(SystemExit):
        run_query_json("x" * 4001, top=5)


# ---------------------------------------------------------------------------
# explain_beer (coverage for Searcher.explain_beer)
# ---------------------------------------------------------------------------


def test_explain_beer_returns_plan(beer_db):
    """explain_beer() must return a non-empty query plan string."""
    beer_id = beer_db.execute(
        "SELECT id FROM beers WHERE beer_name = 'Lemon Wheat'"
    ).fetchone()[0]

    from hopsnvectors.tui import Searcher

    plan = Searcher().explain_beer(beer_id, top=3)
    assert len(plan) > 0
    assert "Seq Scan" in plan or "Index" in plan or "Sort" in plan


# ---------------------------------------------------------------------------
# main() non-interactive mode (coverage for tui.main argparse path)
# ---------------------------------------------------------------------------


def test_main_query_json_mode(beer_db):
    """main(['--query', 'lemon', '--json']) must print valid JSON to stdout."""
    import json as _json

    from hopsnvectors.tui import main

    with patch("hopsnvectors.embedder._load_model", return_value=_mock_model(0)):
        import io
        import sys as _sys
        buf = io.StringIO()
        old_stdout = _sys.stdout
        _sys.stdout = buf
        try:
            main(["--query", "lemon", "--json", "--top", "3"])
        finally:
            _sys.stdout = old_stdout
        output = buf.getvalue().strip()

    results = _json.loads(output)
    assert isinstance(results, list)
    assert len(results) >= 1
