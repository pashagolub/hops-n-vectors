"""Integration tests for loader upsert idempotency against a real pgvector DB.

Tests cover:
- Schema bootstrap (beers + dataset_meta tables exist after init SQL)
- First-load inserts rows with correct columns
- Second load of the same CSV is idempotent (row count unchanged)
- Text change on a row marks it for re-embedding (text_hash drifts)
- Dataset provenance written to dataset_meta on every load
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from hopsnvectors import loader as loader_module

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_csv(rows: list[dict], path: Path) -> Path:
    """Write a minimal valid beer CSV to *path*."""
    cols = [
        "Name", "Style", "Brewery", "Beer Name (Full)", "Description",
        "ABV", "Min IBU", "Max IBU",
        "Astringency", "Body", "Alcohol", "Bitter", "Sweet", "Sour", "Salty",
        "Fruits", "Hoppy", "Spices", "Malty",
        "review_aroma", "review_appearance", "review_palate",
        "review_taste", "review_overall", "number_of_reviews",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _beer(name="Alpha", brewery="Acme", style="IPA", desc="Hoppy") -> dict:
    return {
        "Name": name, "Style": style, "Brewery": brewery,
        "Beer Name (Full)": f"{brewery} {name}",
        "Description": desc, "ABV": "6.0", "Min IBU": "40", "Max IBU": "60",
        "Astringency": "5", "Body": "20", "Alcohol": "10",
        "Bitter": "60", "Sweet": "20", "Sour": "5", "Salty": "0",
        "Fruits": "10", "Hoppy": "70", "Spices": "5", "Malty": "15",
        "review_aroma": "3.5", "review_appearance": "3.8",
        "review_palate": "3.6", "review_taste": "3.7",
        "review_overall": "3.8", "number_of_reviews": "100",
    }


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------


def test_schema_bootstrap(conn):
    """beers and dataset_meta tables must exist after schema init."""
    rows = conn.execute(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name IN ('beers', 'dataset_meta')
        ORDER BY table_name
        """
    ).fetchall()
    names = {r[0] for r in rows}
    assert "beers" in names
    assert "dataset_meta" in names


def test_vector_extension_loaded(conn):
    """The vector extension must be installed (REQ-002)."""
    result = conn.execute(
        "SELECT extname FROM pg_extension WHERE extname = 'vector'"
    ).fetchone()
    assert result is not None, "pgvector extension not loaded"


# ---------------------------------------------------------------------------
# First load
# ---------------------------------------------------------------------------


def test_first_load_inserts_rows(conn, tmp_path, db_env):
    """Loading a CSV for the first time should insert the expected row count."""
    csv_path = _write_csv(
        [_beer("A"), _beer("B", brewery="Brews"), _beer("C")], tmp_path / "beers.csv"
    )
    loader_module.load(csv_path)
    count = conn.execute("SELECT count(*) FROM beers").fetchone()[0]
    assert count == 3


def test_first_load_sets_info(conn, tmp_path):
    """Each loaded row must have a non-empty info field."""
    csv_path = _write_csv([_beer()], tmp_path / "beers.csv")
    loader_module.load(csv_path)
    info = conn.execute("SELECT info FROM beers LIMIT 1").fetchone()[0]
    assert info and len(info) > 0


def test_first_load_sets_text_hash(conn, tmp_path):
    """text_hash must equal sha256(info) on first load (hex string)."""
    csv_path = _write_csv([_beer()], tmp_path / "beers.csv")
    loader_module.load(csv_path)
    mismatch = conn.execute(
        """
        SELECT count(*) FROM beers
        WHERE text_hash IS DISTINCT FROM
              encode(sha256(convert_to(info, 'UTF8')), 'hex')
        """
    ).fetchone()[0]
    assert mismatch == 0


# ---------------------------------------------------------------------------
# Idempotency (second load of same data)
# ---------------------------------------------------------------------------


def test_second_load_idempotent(conn, tmp_path):
    """Loading the same CSV twice must not change the row count (REQ-003)."""
    csv_path = _write_csv([_beer("A"), _beer("B", brewery="Brews")], tmp_path / "beers.csv")
    loader_module.load(csv_path)
    before = conn.execute("SELECT count(*) FROM beers").fetchone()[0]
    loader_module.load(csv_path)
    after = conn.execute("SELECT count(*) FROM beers").fetchone()[0]
    assert before == after == 2


def test_unchanged_row_keeps_hash(conn, tmp_path):
    """A row whose text did not change must retain the same text_hash."""
    csv_path = _write_csv([_beer()], tmp_path / "beers.csv")
    loader_module.load(csv_path)
    hash1 = conn.execute("SELECT text_hash FROM beers LIMIT 1").fetchone()[0]
    loader_module.load(csv_path)
    hash2 = conn.execute("SELECT text_hash FROM beers LIMIT 1").fetchone()[0]
    assert hash1 == hash2


# ---------------------------------------------------------------------------
# Text change → stale hash (triggers re-embedding on next embedder run)
# ---------------------------------------------------------------------------


def test_text_change_invalidates_hash(conn, tmp_path):
    """Changing description should update info and text_hash on re-load."""
    csv1 = _write_csv([_beer(desc="Original taste")], tmp_path / "v1.csv")
    loader_module.load(csv1)
    hash1 = conn.execute("SELECT text_hash FROM beers LIMIT 1").fetchone()[0]

    csv2 = _write_csv([_beer(desc="New improved taste")], tmp_path / "v2.csv")
    loader_module.load(csv2)
    hash2 = conn.execute("SELECT text_hash FROM beers LIMIT 1").fetchone()[0]

    assert hash1 != hash2


def test_direct_info_edit_marks_row_for_reembed(conn, tmp_path):
    """Direct info edit without updating text_hash marks the row for re-embed (AC-005).

    This mirrors the psql-edit workflow: `UPDATE beers SET info = '...'`
    leaves text_hash stale so the embedder detects and re-embeds the row.
    """
    csv_path = _write_csv([_beer()], tmp_path / "beers.csv")
    loader_module.load(csv_path)
    # Synchronise text_hash (as embedder would after embedding).
    conn.execute(
        "UPDATE beers SET text_hash = encode(sha256(convert_to(info, 'UTF8')), 'hex')"
    )
    conn.commit()

    # Simulate a psql edit that only changes info — NOT text_hash.
    conn.execute("UPDATE beers SET info = info || ' (edited)'")
    conn.commit()

    # Now text_hash is stale → the embedder will detect and re-embed.
    stale = conn.execute(
        """
        SELECT count(*) FROM beers
        WHERE text_hash IS DISTINCT FROM
              encode(sha256(convert_to(info, 'UTF8')), 'hex')
        """
    ).fetchone()[0]
    assert stale == 1, "Direct info edit should produce a stale text_hash (pending re-embed)"


# ---------------------------------------------------------------------------
# Dataset provenance
# ---------------------------------------------------------------------------


def test_dataset_meta_written(conn, tmp_path):
    """dataset_meta must contain source_url and license after load."""
    csv_path = _write_csv([_beer()], tmp_path / "beers.csv")
    loader_module.load(csv_path)
    keys = {r[0] for r in conn.execute("SELECT key FROM dataset_meta").fetchall()}
    assert "source_url" in keys
    assert "license" in keys


def test_dataset_meta_idempotent(conn, tmp_path):
    """Re-loading must not duplicate dataset_meta rows."""
    csv_path = _write_csv([_beer()], tmp_path / "beers.csv")
    loader_module.load(csv_path)
    loader_module.load(csv_path)
    count = conn.execute(
        "SELECT count(*) FROM dataset_meta WHERE key = 'source_url'"
    ).fetchone()[0]
    assert count == 1

