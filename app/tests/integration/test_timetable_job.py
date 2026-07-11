"""Integration tests for pg_timetable job SQL.

Tests cover:
- 02_timetable_job.sql executes without error when timetable schema is absent
  (should raise NOTICE and return gracefully — PostgreSQL init phase guard)
- The incremental re-embed SQL logic doesn't require pg_timetable at runtime

The full pg_timetable chain registration is validated in the E2E test via
`docker compose run --rm scheduler psql -c "SELECT * FROM timetable.chain"`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_TIMETABLE_SQL = Path(__file__).parents[3] / "init" / "02_timetable_job.sql"


def test_timetable_sql_graceful_when_schema_absent(conn):
    """Running 02_timetable_job.sql when timetable schema is absent must not raise.

    The DO block detects the missing schema and exits with a NOTICE rather than
    crashing — this is the PostgreSQL init-phase guard path.
    """
    sql = _TIMETABLE_SQL.read_text()
    # Must not raise any exception; NOTICE is expected but not an error.
    conn.execute(sql)
    conn.commit()


def test_timetable_sql_is_idempotent_without_schema(conn):
    """Running 02_timetable_job.sql twice with no timetable schema must succeed."""
    sql = _TIMETABLE_SQL.read_text()
    conn.execute(sql)
    conn.commit()
    conn.execute(sql)  # second run
    conn.commit()


def test_pending_embed_query_runs_cleanly(conn):
    """The pending-rows predicate used by the embedder must execute against the schema."""
    # Just assert the query parses and runs without error on an empty table.
    rows = conn.execute(
        """
        SELECT id, info
        FROM beers
        WHERE info <> ''
          AND (
              embedding IS NULL
              OR embedded_at IS NULL
              OR text_hash IS DISTINCT FROM encode(sha256(convert_to(info, 'UTF8')), 'hex')
          )
        LIMIT 1
        """
    ).fetchall()
    assert rows == []  # empty table → no pending rows


def test_hnsw_index_creation_idempotent(conn):
    """CREATE INDEX IF NOT EXISTS for the HNSW index must be safe to run repeatedly."""
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS beers_embedding_hnsw
        ON beers USING hnsw (embedding vector_cosine_ops)
        """
    )
    conn.commit()
    # Second run must also succeed.
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS beers_embedding_hnsw
        ON beers USING hnsw (embedding vector_cosine_ops)
        """
    )
    conn.commit()
    result = conn.execute(
        "SELECT indexname FROM pg_indexes WHERE indexname = 'beers_embedding_hnsw'"
    ).fetchone()
    assert result is not None

