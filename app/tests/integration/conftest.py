"""Shared fixtures for integration tests.

All integration tests run against a real pgvector/pgvector:pg18 container
created once per test session.  Individual tests use a function-scoped
``conn`` fixture that auto-truncates the ``beers`` and ``dataset_meta`` tables
before each test to ensure isolation.
"""
from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest
from pgvector.psycopg import register_vector
from testcontainers.postgres import PostgresContainer

_IMAGE = "pgvector/pgvector:pg18"
_SCHEMA = Path(__file__).parents[3] / "init" / "01_schema.sql"

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Session-scoped container + schema bootstrap
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pg_container():
    """Start a pgvector container for the whole test session."""
    with PostgresContainer(
        image=_IMAGE,
        dbname="beer",
        username="beer",
        password="beer",
    ) as container:
        yield container


@pytest.fixture(scope="session")
def _schema_conn(pg_container):
    """Apply the schema SQL once per session and close the connection."""
    conn = psycopg.connect(
        host=pg_container.get_container_host_ip(),
        port=pg_container.get_exposed_port(5432),
        dbname="beer",
        user="beer",
        password="beer",
        autocommit=True,
    )
    conn.execute(_SCHEMA.read_text())
    conn.close()


@pytest.fixture(scope="session")
def db_env(pg_container, _schema_conn):
    """Expose connection env-vars and return a dict of them.

    Also patches ``os.environ`` so that ``hopsnvectors.db.get_connection()``
    transparently connects to the test container.
    """
    env = {
        "POSTGRES_HOST": pg_container.get_container_host_ip(),
        "POSTGRES_PORT": str(pg_container.get_exposed_port(5432)),
        "POSTGRES_DB": "beer",
        "POSTGRES_USER": "beer",
        "POSTGRES_PASSWORD": "beer",
    }
    saved = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    yield env
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


# ---------------------------------------------------------------------------
# Function-scoped connection (clean tables before each test)
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn(db_env):
    """Yield a fresh psycopg connection, truncating tables before each test."""
    c = psycopg.connect(
        host=db_env["POSTGRES_HOST"],
        port=db_env["POSTGRES_PORT"],
        dbname=db_env["POSTGRES_DB"],
        user=db_env["POSTGRES_USER"],
        password=db_env["POSTGRES_PASSWORD"],
    )
    register_vector(c)
    c.execute("TRUNCATE TABLE beers, dataset_meta RESTART IDENTITY CASCADE")
    c.commit()
    yield c
    c.close()
