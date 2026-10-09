from pathlib import Path
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(PROJECT_ROOT / "src"),
)

from interdomain.ingestion.ripe_client import RipeRisClient
from interdomain.streaming.kafka import (
    create_producer,
    produce_bgp_event,
)


def main():
    client = RipeRisClient()
    producer = create_producer()

    produced = 0

    while True:
        try:
            print("Connecting to RIPE RIS Live...")

            client.connect()

            print(
                "Connected. Publishing BGP updates to Kafka..."
            )

            for event in client.messages():
                produce_bgp_event(
                    producer,
                    event,
                )

                produced += 1

                if produced % 100 == 0:
                    print(
                        f"Published {produced:,} "
                        "BGP messages to Kafka"
                    )

        except KeyboardInterrupt:
            print("\nStopping producer.")
            break

        except Exception as exc:
            print(f"Producer error: {exc}")
            print("Reconnecting in 5 seconds...")
            time.sleep(5)

        finally:
            client.close()

    producer.flush()


if __name__ == "__main__":
    main()