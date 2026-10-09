from contextlib import contextmanager
from typing import Iterable
import psycopg
from interdomain.config import postgres_dsn


@contextmanager
def get_connection():
    connection = psycopg.connect(postgres_dsn())
    try:
        yield connection
    finally:
        connection.close()


def insert_events(rows: Iterable[dict]) -> int:
    rows = list(rows)
    if not rows:
        return 0

    sql = """
        INSERT INTO bgp_events (
            observed_at, peer, peer_asn, prefix, event_type, as_path, next_hop
        ) VALUES (
            %(observed_at)s, %(peer)s, %(peer_asn)s, %(prefix)s, %(event_type)s, %(path)s, %(next_hop)s
        )
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, rows)
        conn.commit()
    return len(rows)
