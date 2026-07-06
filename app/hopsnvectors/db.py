"""Environment-driven PostgreSQL connection factory."""
from __future__ import annotations

import os

import psycopg


def get_connection(**kwargs) -> psycopg.Connection:
    """Return a new psycopg connection driven by environment variables.

    Variables used:
      POSTGRES_HOST     (default: postgres)
      POSTGRES_PORT     (default: 5432)
      POSTGRES_USER     (required)
      POSTGRES_PASSWORD (required)
      POSTGRES_DB       (required)

    Additional keyword arguments are forwarded to psycopg.connect.
    """
    conninfo = (
        f"host={os.environ.get('POSTGRES_HOST', 'postgres')} "
        f"port={os.environ.get('POSTGRES_PORT', '5432')} "
        f"dbname={os.environ['POSTGRES_DB']} "
        f"user={os.environ['POSTGRES_USER']} "
        f"password={os.environ['POSTGRES_PASSWORD']}"
    )
    return psycopg.connect(conninfo, **kwargs)

