import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg2
from psycopg2.extensions import connection, cursor as Cursor
from psycopg2.extras import execute_values

from config import config, require_database_url

logger = logging.getLogger(__name__)


@contextmanager
def get_connection() -> Iterator[connection]:
    conn = psycopg2.connect(require_database_url(config))
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_cursor(conn: connection) -> Iterator[Cursor]:
    cur = conn.cursor()
    try:
        yield cur
    finally:
        cur.close()


def init_schema(conn: connection) -> None:
    logger.debug("Applying database schema")

    schema_sql = """
        CREATE TABLE IF NOT EXISTS types (
            id INTEGER PRIMARY KEY,
            group_id INTEGER NOT NULL,
            faction_id INTEGER,
            name VARCHAR(150) NOT NULL,
            description TEXT,
            published BOOL NOT NULL,
            last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE EXTENSION IF NOT EXISTS pg_trgm;
        CREATE INDEX IF NOT EXISTS idx_types_name_trgm ON types USING gin (name gin_trgm_ops);
    """

    with get_cursor(conn) as cursor:
        cursor.execute(schema_sql)
    conn.commit()
    logger.debug("Database schema initialized")


def insert_types_batch(conn: connection, types: list[dict[str, Any]]) -> int:
    if not types:
        logger.debug("insert_types_batch called with empty list, nothing to insert")
        return 0
    logger.debug("Upserting batch of %d types", len(types))

    sql = """
        INSERT INTO types (id, group_id, faction_id, name, description, published, last_updated)
        VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            group_id    = EXCLUDED.group_id,
            faction_id  = EXCLUDED.faction_id,
            name        = EXCLUDED.name,
            description = EXCLUDED.description,
            published   = EXCLUDED.published,
            last_updated = NOW()
        WHERE (
            types.group_id,
            types.faction_id,
            types.name,
            types.description,
            types.published
        ) IS DISTINCT FROM (
            EXCLUDED.group_id,
            EXCLUDED.faction_id,
            EXCLUDED.name,
            EXCLUDED.description,
            EXCLUDED.published
        )
        RETURNING id
    """

    values = [
        (
            t["id"],
            t["group_id"],
            t["faction_id"],
            t["name"],
            t["description"],
            t["published"],
        )
        for t in types
    ]

    with get_cursor(conn) as cursor:
        rows = execute_values(
            cursor, sql, values, template="(%s, %s, %s, %s, %s, %s, NOW())", fetch=True
        )

    conn.commit()
    return len(rows)
