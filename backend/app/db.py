from functools import lru_cache

from pgvector.psycopg import register_vector
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import get_settings


def _configure(conn: Connection) -> None:
    register_vector(conn)


@lru_cache
def get_pool() -> ConnectionPool:
    pool = ConnectionPool(
        get_settings().database_url,
        min_size=1,
        max_size=10,
        configure=_configure,
        kwargs={"row_factory": dict_row},
        open=False,
    )
    pool.open()
    return pool
