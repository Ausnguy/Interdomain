from pathlib import Path
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(PROJECT_ROOT / "src"),
)

from interdomain.ingestion.backoff import backoff_delay
from interdomain.ingestion.ripe_client import RipeRisClient
from interdomain.streaming.kafka import (
    DeliveryStats,
    create_producer,
    produce_bgp_event,
)


def main():
    client = RipeRisClient()
    producer = create_producer()

    stats = DeliveryStats()
    produced = 0
    failures = 0

    while True:
        try:
            print("Connecting to RIPE RIS Live...")

            client.connect()

            print(
                "Connected. Publishing BGP updates to Kafka..."
            )

            for event in client.messages():
                # A message arrived, so the connection is healthy again.
                failures = 0

                produce_bgp_event(
                    producer,
                    event,
                    on_delivery=stats.on_delivery,
                )

                produced += 1

                if produced % 10_000 == 0:
                    print(
                        f"Queued {produced:,} | "
                        f"confirmed {stats.delivered:,} | "
                        f"failed {stats.failed:,}"
                    )

        except KeyboardInterrupt:
            print("\nStopping producer.")
            break

        except Exception as exc:
            delay = backoff_delay(failures)
            failures += 1

            print(f"Producer error: {exc}")
            print(f"Reconnecting in {delay:.1f} seconds...")
            time.sleep(delay)

        finally:
            client.close()

    # flush() waits for outstanding messages and fires their callbacks;
    # it returns how many are still unconfirmed after the timeout.
    unconfirmed = producer.flush(10)

    print(
        f"Stopped. Queued {produced:,} | confirmed {stats.delivered:,} | "
        f"failed {stats.failed:,} | unconfirmed {unconfirmed}"
    )


if __name__ == "__main__":
    main()