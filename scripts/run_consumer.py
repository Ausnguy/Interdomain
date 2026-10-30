from pathlib import Path
import sys
import time
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(PROJECT_ROOT / "src"),
)

import psycopg
from confluent_kafka import KafkaException

from interdomain.config import (
    CONSUMER_BATCH_SIZE,
    KAFKA_BGP_TOPIC,
)

from interdomain.processing.rollups import PrefixActivityTracker

from interdomain.storage.postgres import (
    connect,
    ensure_partitions,
    load_offsets,
    write_batch,
)

from interdomain.streaming.kafka import (
    create_consumer,
    decode_batch,
)


REPORT_INTERVAL_SECONDS = 10
MAX_RETRY_DELAY_SECONDS = 30
PARTITION_HOURS_AHEAD = 1


class Database:
    """One long-lived Postgres connection that reconnects on demand."""

    def __init__(self):
        self.conn = None

    def get(self):
        if self.conn is None or self.conn.closed:
            self.conn = connect()

        return self.conn

    def reset(self):
        if self.conn is not None:
            self.conn.close()

        self.conn = None


def with_retry(db, action, description):
    """Run action(conn) until it succeeds.

    Nothing is acknowledged to Kafka until this returns, so a database outage
    pauses consumption instead of losing messages.
    """
    delay = 1

    while True:
        try:
            return action(db.get())

        except psycopg.errors.CheckViolation as exc:
            if "no partition" not in str(exc):
                raise

            print("No bgp_events partition for this hour; creating it...")
            ensure_partitions(db.get(), PARTITION_HOURS_AHEAD)

        except psycopg.OperationalError as exc:
            print(
                f"Postgres unavailable while {description} ({exc}). "
                f"Retrying in {delay}s..."
            )

            db.reset()
            time.sleep(delay)
            delay = min(delay * 2, MAX_RETRY_DELAY_SECONDS)


def current_lag(consumer) -> int | None:
    try:
        total = 0

        for partition in consumer.position(consumer.assignment()):
            if partition.offset < 0:
                continue

            _, high = consumer.get_watermark_offsets(
                partition,
                timeout=1.0,
            )
            total += high - partition.offset

        return total

    except KafkaException:
        return None


def main():
    db = Database()
    tracker = PrefixActivityTracker()

    with_retry(
        db,
        lambda conn: ensure_partitions(conn, PARTITION_HOURS_AHEAD),
        "creating partitions",
    )
    ensured_hour = datetime.now(timezone.utc).hour

    consumer = create_consumer(
        load_offsets=lambda: with_retry(
            db,
            lambda conn: load_offsets(conn, KAFKA_BGP_TOPIC),
            "loading offsets",
        )
    )

    consumed = 0
    inserted_total = 0
    skipped_total = 0

    window_started = time.monotonic()
    window_consumed = 0
    window_inserted = 0

    print(
        f"Waiting for BGP events from Kafka "
        f"(batches of up to {CONSUMER_BATCH_SIZE:,})..."
    )

    try:
        while True:
            hour = datetime.now(timezone.utc).hour

            if hour != ensured_hour:
                with_retry(
                    db,
                    lambda conn: ensure_partitions(conn, PARTITION_HOURS_AHEAD),
                    "creating partitions",
                )
                ensured_hour = hour

            messages = consumer.consume(
                num_messages=CONSUMER_BATCH_SIZE,
                timeout=1.0,
            )

            if messages:
                rows, skipped, offsets = decode_batch(messages)

                inserted = with_retry(
                    db,
                    lambda conn: write_batch(conn, rows, tracker, offsets),
                    "writing a batch",
                )

                # Postgres holds the authoritative offsets; this commit only
                # keeps Kafka's own lag tooling accurate.
                try:
                    consumer.commit(asynchronous=True)
                except KafkaException as exc:
                    print(f"Kafka offset commit failed: {exc}")

                consumed += len(messages)
                inserted_total += inserted
                skipped_total += skipped
                window_consumed += len(messages)
                window_inserted += inserted

            elapsed = time.monotonic() - window_started

            if elapsed >= REPORT_INTERVAL_SECONDS:
                lag = current_lag(consumer)
                lag_text = (
                    f"{lag:,} msgs" if lag is not None else "unknown"
                )

                print(
                    f"{window_consumed / elapsed:,.0f} msg/s "
                    f"| {window_inserted / elapsed:,.0f} rows/s "
                    f"| lag {lag_text} "
                    f"| total {consumed:,} msgs, {inserted_total:,} rows, "
                    f"{skipped_total:,} skipped"
                )

                window_started = time.monotonic()
                window_consumed = 0
                window_inserted = 0

    except KeyboardInterrupt:
        print("\nStopping consumer.")

    finally:
        consumer.close()
        db.reset()


if __name__ == "__main__":
    main()
