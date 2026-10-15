from contextlib import contextmanager
import re
from datetime import datetime, timedelta
from typing import Any

import psycopg
from psycopg import sql

from interdomain.config import postgres_dsn
from interdomain.processing.rollups import (
    PrefixActivityTracker,
    aggregate_minute_stats,
)


@contextmanager
def get_connection():
    connection = psycopg.connect(postgres_dsn())
    try:
        yield connection
    finally:
        connection.close()


def connect() -> psycopg.Connection:
    # Autocommit, so every unit of work is an explicit conn.transaction()
    # block and nested blocks become savepoints.
    return psycopg.connect(postgres_dsn(), autocommit=True)


# ---------------------------------------------------------------------------
# Raw events
# ---------------------------------------------------------------------------

COPY_SQL = """
    COPY bgp_events (
        observed_at,
        peer,
        peer_asn,
        collector,
        collector_region,
        prefix,
        event_type,
        as_path,
        next_hop
    ) FROM STDIN
"""

COPY_TYPES = [
    "timestamptz",
    "text",
    "int8",
    "text",
    "text",
    "cidr",
    "text",
    "int8[]",
    "inet",
]

SINGLE_INSERT_SQL = """
    INSERT INTO bgp_events (
        observed_at,
        peer,
        peer_asn,
        collector,
        collector_region,
        prefix,
        event_type,
        as_path,
        next_hop
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

ROW_ERRORS = (psycopg.DataError, ValueError, TypeError)


def _flatten_path(path: Any) -> list[int] | None:
    # RIS paths can contain AS_SETs as nested lists, e.g. [64500, [64501, 64502]].
    # BIGINT[] cannot hold nested lists, so set members are inlined.
    if not path:
        return None

    flat: list[int] = []

    for hop in path:
        if isinstance(hop, list):
            flat.extend(int(asn) for asn in hop)
        else:
            flat.append(int(hop))

    return flat


def _row_values(row: dict) -> tuple:
    peer_asn = row.get("peer_asn")

    return (
        row["observed_at"],
        row.get("peer"),
        int(peer_asn) if peer_asn not in (None, "") else None,
        row.get("collector"),
        row.get("collector_region") or "unknown",
        row["prefix"],
        row["event_type"],
        _flatten_path(row.get("path")),
        row.get("next_hop"),
    )


def _copy_rows(
    conn: psycopg.Connection,
    rows: list[dict],
) -> list[dict]:
    """COPY rows inside the caller's transaction; return the rows stored.

    If COPY rejects the batch (e.g. an invalid CIDR), fall back to one
    savepoint per row so only the invalid rows are dropped.
    """
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                with cur.copy(COPY_SQL) as copy:
                    copy.set_types(COPY_TYPES)

                    for row in rows:
                        copy.write_row(_row_values(row))

        return rows

    except ROW_ERRORS as exc:
        print(
            f"COPY rejected a batch of {len(rows):,} rows ({exc}); "
            "inserting rows individually."
        )

    accepted = []

    with conn.cursor() as cur:
        for row in rows:
            try:
                with conn.transaction():
                    cur.execute(SINGLE_INSERT_SQL, _row_values(row))
                accepted.append(row)
            except ROW_ERRORS as exc:
                print(
                    f"Skipping invalid row (prefix={row.get('prefix')}): {exc}"
                )

    return accepted


# ---------------------------------------------------------------------------
# Batch writer: raw rows + rollups + Kafka offsets in one transaction
# ---------------------------------------------------------------------------

UPSERT_MINUTE_STATS_SQL = """
    INSERT INTO bgp_minute_stats (
        minute,
        collector,
        collector_region,
        peer_asn,
        announcements,
        withdrawals
    )
    SELECT * FROM unnest(
        %s::timestamptz[],
        %s::text[],
        %s::text[],
        %s::bigint[],
        %s::bigint[],
        %s::bigint[]
    )
    ON CONFLICT (minute, collector, peer_asn) DO UPDATE SET
        announcements = bgp_minute_stats.announcements + EXCLUDED.announcements,
        withdrawals = bgp_minute_stats.withdrawals + EXCLUDED.withdrawals
"""

UPSERT_PREFIX_SEEN_SQL = """
    INSERT INTO bgp_prefix_seen (
        collector,
        prefix,
        collector_region,
        last_seen
    )
    -- Different spellings of one prefix (e.g. IPv6 forms) only become
    -- equal after the cidr cast, so deduplicate here, not in Python.
    SELECT collector, prefix, MAX(collector_region), MAX(last_seen)
    FROM unnest(
        %s::text[],
        %s::cidr[],
        %s::text[],
        %s::timestamptz[]
    ) AS batch (collector, prefix, collector_region, last_seen)
    GROUP BY collector, prefix
    ON CONFLICT (collector, prefix) DO UPDATE SET
        last_seen = GREATEST(bgp_prefix_seen.last_seen, EXCLUDED.last_seen),
        collector_region = EXCLUDED.collector_region
"""

UPSERT_OFFSETS_SQL = """
    INSERT INTO kafka_offsets (topic, partition, next_offset, updated_at)
    VALUES (%s, %s, %s, NOW())
    ON CONFLICT (topic, partition) DO UPDATE SET
        next_offset = EXCLUDED.next_offset,
        updated_at = EXCLUDED.updated_at
"""


def _columns(tuples: list[tuple]) -> list[list]:
    return [list(column) for column in zip(*tuples)]


def write_batch(
    conn: psycopg.Connection,
    rows: list[dict],
    tracker: PrefixActivityTracker,
    offsets: dict[tuple[str, int], int] | None = None,
) -> int:
    """Store a batch atomically and return the number of raw rows stored.

    Raw events, minute rollups, prefix activity and (when given) the next
    Kafka offset per partition commit together, so a crash or retry can
    neither lose a batch nor count it twice. `conn` must be in autocommit
    mode (see connect()).

    Raises psycopg.OperationalError when the database is unreachable and
    psycopg.errors.CheckViolation when no partition exists for the rows.
    """
    with conn.transaction():
        accepted = _copy_rows(conn, rows) if rows else []

        stats = aggregate_minute_stats(accepted)
        prefix_plan = tracker.plan(accepted)

        with conn.cursor() as cur:
            if stats:
                cur.execute(UPSERT_MINUTE_STATS_SQL, _columns(stats))

            if prefix_plan.pairs:
                cur.execute(UPSERT_PREFIX_SEEN_SQL, _columns(prefix_plan.pairs))

            for (topic, partition), next_offset in (offsets or {}).items():
                cur.execute(UPSERT_OFFSETS_SQL, (topic, partition, next_offset))

    tracker.apply(prefix_plan)

    return len(accepted)


def load_offsets(
    conn: psycopg.Connection,
    topic: str,
) -> dict[int, int]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT partition, next_offset FROM kafka_offsets WHERE topic = %s",
            (topic,),
        )
        return dict(cur.fetchall())


# ---------------------------------------------------------------------------
# Partitions and retention
# ---------------------------------------------------------------------------

PARTITION_PREFIX = "bgp_events_p"
PARTITION_NAME = re.compile(r"^bgp_events_p(\d{10})$")


def _partition_name(hour_start: datetime) -> str:
    return f"{PARTITION_PREFIX}{hour_start:%Y%m%d%H}"


def ensure_partitions(
    conn: psycopg.Connection,
    hours_ahead: int,
) -> list[str]:
    """Create hourly bgp_events partitions from the current hour (database
    clock, UTC) through `hours_ahead` hours later. Returns names created."""
    created = []

    with conn.cursor() as cur:
        cur.execute("SELECT date_trunc('hour', NOW() AT TIME ZONE 'UTC')")
        current_hour = cur.fetchone()[0]

        cur.execute(
            "SELECT relname FROM pg_class WHERE relname LIKE %s",
            (f"{PARTITION_PREFIX}%",),
        )
        existing = {name for (name,) in cur.fetchall()}

        for offset in range(hours_ahead + 1):
            start = current_hour + timedelta(hours=offset)
            name = _partition_name(start)

            if name in existing:
                continue

            cur.execute(
                sql.SQL(
                    "CREATE TABLE IF NOT EXISTS {} PARTITION OF bgp_events "
                    "FOR VALUES FROM ({}) TO ({})"
                ).format(
                    sql.Identifier(name),
                    sql.Literal(f"{start:%Y-%m-%d %H}:00:00+00"),
                    sql.Literal(f"{start + timedelta(hours=1):%Y-%m-%d %H}:00:00+00"),
                )
            )
            created.append(name)

    return created


def drop_partitions_older_than(
    conn: psycopg.Connection,
    hours: float,
) -> list[str]:
    """Drop hourly partitions whose whole range ended more than `hours` ago.

    Only tables attached to bgp_events whose names match the hourly pattern
    are considered; the range end is derived from the name.
    """
    dropped = []

    with conn.cursor() as cur:
        cur.execute("SELECT NOW() AT TIME ZONE 'UTC'")
        now_utc = cur.fetchone()[0]

        cur.execute(
            """
            SELECT child.relname
            FROM pg_inherits
            JOIN pg_class parent ON parent.oid = pg_inherits.inhparent
            JOIN pg_class child ON child.oid = pg_inherits.inhrelid
            WHERE parent.relname = 'bgp_events'
            """
        )

        for (name,) in cur.fetchall():
            match = PARTITION_NAME.match(name)

            if not match:
                continue

            range_end = datetime.strptime(match.group(1), "%Y%m%d%H") + timedelta(hours=1)

            if range_end <= now_utc - timedelta(hours=hours):
                with conn.transaction():
                    # Don't queue behind long queries while holding up others.
                    cur.execute("SET LOCAL lock_timeout = '5s'")
                    cur.execute(sql.SQL("DROP TABLE {}").format(sql.Identifier(name)))
                dropped.append(name)

    return dropped


def delete_minute_stats_older_than(
    conn: psycopg.Connection,
    days: float,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM bgp_minute_stats WHERE minute < NOW() - make_interval(secs => %s)",
            (days * 86400,),
        )
        return cur.rowcount


# The dashboard window is 60 one-minute buckets; keep a little slack so a
# refresh never races the cleanup.
PREFIX_SEEN_KEEP_MINUTES = 65

DASHBOARD_WINDOW_SQL = "date_trunc('minute', NOW()) - INTERVAL '59 minutes'"


def delete_stale_prefix_seen(conn: psycopg.Connection) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM bgp_prefix_seen WHERE last_seen < NOW() - make_interval(mins => %s)",
            (PREFIX_SEEN_KEEP_MINUTES,),
        )
        return cur.rowcount


def refresh_prefix_counts(conn: psycopg.Connection) -> None:
    """Recompute exact distinct-prefix counts for the dashboard window."""
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("SET LOCAL work_mem = '64MB'")
            cur.execute("DELETE FROM bgp_prefix_counts")
            cur.execute(
                f"""
                WITH recent AS MATERIALIZED (
                    SELECT collector, collector_region, prefix
                    FROM bgp_prefix_seen
                    WHERE last_seen >= {DASHBOARD_WINDOW_SQL}
                )
                INSERT INTO bgp_prefix_counts (scope, key, unique_prefixes, computed_at)
                SELECT 'collector', collector, COUNT(*), NOW()
                FROM recent
                GROUP BY collector
                UNION ALL
                SELECT 'region', collector_region, COUNT(DISTINCT prefix), NOW()
                FROM recent
                GROUP BY collector_region
                UNION ALL
                SELECT 'global', 'all', COUNT(DISTINCT prefix), NOW()
                FROM recent
                """
            )
