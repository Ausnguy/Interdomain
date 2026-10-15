from pathlib import Path
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(PROJECT_ROOT / "src"),
)

import psycopg

from interdomain.config import (
    RAW_RETENTION_HOURS,
    ROLLUP_RETENTION_DAYS,
)

from interdomain.storage.postgres import (
    connect,
    delete_minute_stats_older_than,
    delete_stale_prefix_seen,
    drop_partitions_older_than,
    ensure_partitions,
    refresh_prefix_counts,
)


PREFIX_COUNTS_INTERVAL_SECONDS = 30
RETENTION_INTERVAL_SECONDS = 60
PARTITION_HOURS_AHEAD = 3


def run_retention(conn) -> None:
    created = ensure_partitions(conn, PARTITION_HOURS_AHEAD)
    dropped = drop_partitions_older_than(conn, RAW_RETENTION_HOURS)
    stats_deleted = delete_minute_stats_older_than(conn, ROLLUP_RETENTION_DAYS)
    prefixes_deleted = delete_stale_prefix_seen(conn)

    print(
        f"Retention: created {created or 'no'} partitions, "
        f"dropped {dropped or 'no'} partitions, "
        f"deleted {stats_deleted:,} minute rows "
        f"and {prefixes_deleted:,} stale prefix rows"
    )


def main():
    print(
        f"Maintenance: prefix counts every {PREFIX_COUNTS_INTERVAL_SECONDS}s; "
        f"raw events kept {RAW_RETENTION_HOURS:g} h, "
        f"minute stats kept {ROLLUP_RETENTION_DAYS:g} days."
    )

    conn = None
    last_retention = 0.0

    try:
        while True:
            try:
                if conn is None or conn.closed:
                    conn = connect()

                started = time.monotonic()
                refresh_prefix_counts(conn)
                refresh_ms = (time.monotonic() - started) * 1000

                if time.monotonic() - last_retention >= RETENTION_INTERVAL_SECONDS:
                    print(f"Prefix counts refreshed in {refresh_ms:,.0f} ms")
                    run_retention(conn)
                    last_retention = time.monotonic()

            # LockNotAvailable subclasses OperationalError, so it comes first.
            except psycopg.errors.LockNotAvailable as exc:
                print(f"Partition drop deferred (lock busy): {exc}")

            except psycopg.OperationalError as exc:
                print(f"Maintenance skipped, Postgres unavailable: {exc}")

                if conn is not None:
                    conn.close()
                    conn = None

            time.sleep(PREFIX_COUNTS_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\nStopping maintenance.")

    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    main()
