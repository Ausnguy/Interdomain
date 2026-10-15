"""Read-only snapshot of pipeline health: API latency, table sizes,
ingest rate, and consumer lag. Run before and after changes to compare."""

from pathlib import Path
import statistics
import sys
import time
import urllib.request

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(PROJECT_ROOT / "src"),
)

from confluent_kafka import Consumer, TopicPartition

from interdomain.config import (
    KAFKA_BGP_TOPIC,
    KAFKA_BOOTSTRAP_SERVERS,
)
from interdomain.storage.postgres import get_connection


API = "http://127.0.0.1:8000"

ENDPOINTS = [
    "/metrics/summary",
    "/regions/summary",
    "/collectors/activity",
    "/metrics/activity",
    "/asns/active?limit=8",
    "/routes/recent?limit=15",
    "/routes/withdrawals?limit=8",
    "/health/ingestion",
]

RUNS = 3

CONSUMER_GROUP = "interdomain-postgres-consumer"


def time_endpoints():
    print(f"API latency (median of {RUNS})")

    for endpoint in ENDPOINTS:
        timings = []

        for _ in range(RUNS):
            started = time.perf_counter()

            with urllib.request.urlopen(f"{API}{endpoint}", timeout=120) as response:
                response.read()

            timings.append(time.perf_counter() - started)

        print(f"  {endpoint:<28} {statistics.median(timings) * 1000:>9.1f} ms")


def table_sizes(cur):
    print("\nTables")

    cur.execute(
        """
        SELECT
            c.relname,
            c.reltuples::bigint,
            pg_total_relation_size(c.oid)
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind IN ('r', 'p')
          AND (c.relname LIKE 'bgp_%' OR c.relname = 'kafka_offsets')
        ORDER BY c.relname
        """
    )

    total = 0

    for name, estimated_rows, size in cur.fetchall():
        total += size
        print(
            f"  {name:<34} ~{max(estimated_rows, 0):>12,} rows "
            f"{size / 1_048_576:>10,.1f} MB"
        )

    print(f"  {'total':<34} {'':>18} {total / 1_048_576:>10,.1f} MB")


def table_exists(cur, name):
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (name,))
    return cur.fetchone()[0]


def ingest_rate(cur):
    print("\nIngest rate")

    if table_exists(cur, "bgp_minute_stats"):
        cur.execute(
            """
            SELECT COALESCE(SUM(announcements + withdrawals), 0)
            FROM bgp_minute_stats
            WHERE minute = date_trunc('minute', NOW()) - INTERVAL '1 minute'
            """
        )
        source = "last complete minute, bgp_minute_stats"
    else:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM bgp_events
            WHERE inserted_at >= NOW() - INTERVAL '60 seconds'
            """
        )
        source = "last 60 s, bgp_events.inserted_at"

    rows = cur.fetchone()[0]

    print(f"  {rows / 60:,.0f} rows/s ({source})")


def consumer_lag(cur):
    print("\nConsumer lag")

    # Not subscribed, so this never joins or rebalances the real group.
    consumer = Consumer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "group.id": CONSUMER_GROUP,
            "enable.auto.commit": False,
        }
    )

    try:
        metadata = consumer.list_topics(KAFKA_BGP_TOPIC, timeout=10)
        partitions = sorted(metadata.topics[KAFKA_BGP_TOPIC].partitions)

        db_offsets = {}

        if table_exists(cur, "kafka_offsets"):
            cur.execute(
                "SELECT partition, next_offset FROM kafka_offsets WHERE topic = %s",
                (KAFKA_BGP_TOPIC,),
            )
            db_offsets = dict(cur.fetchall())

        committed = consumer.committed(
            [TopicPartition(KAFKA_BGP_TOPIC, p) for p in partitions],
            timeout=10,
        )

        total = 0

        for tp in committed:
            _, high = consumer.get_watermark_offsets(tp, timeout=10)
            position = db_offsets.get(tp.partition, tp.offset)
            source = "postgres" if tp.partition in db_offsets else "kafka"
            lag = high - position if position >= 0 else None
            total += lag or 0

            print(
                f"  partition {tp.partition}: end {high:,} "
                f"position {position:,} ({source}) lag {lag:,}"
                if lag is not None
                else f"  partition {tp.partition}: no committed offset"
            )

        print(f"  total lag {total:,} msgs")

    finally:
        consumer.close()


def main():
    time_endpoints()

    with get_connection() as conn:
        with conn.cursor() as cur:
            table_sizes(cur)
            ingest_rate(cur)
            consumer_lag(cur)


if __name__ == "__main__":
    main()
