from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(PROJECT_ROOT / "src"),
)

from interdomain.processing.normalize import (
    normalize_bgp_event,
)

from interdomain.storage.postgres import (
    insert_events,
)

from interdomain.streaming.kafka import (
    create_consumer,
    decode_bgp_event,
)


def main():
    consumer = create_consumer()

    consumed = 0
    inserted_total = 0

    print("Waiting for BGP events from Kafka...")

    try:
        while True:
            message = consumer.poll(1.0)

            if message is None:
                continue

            if message.error():
                print(
                    f"Kafka error: {message.error()}"
                )
                continue

            try:
                event = decode_bgp_event(
                    message.value()
                )

                rows = normalize_bgp_event(
                    event
                )

                inserted = insert_events(rows)

                consumer.commit(
                    message=message,
                    asynchronous=False,
                )

                consumed += 1
                inserted_total += inserted

                if consumed % 100 == 0:
                    print(
                        f"Consumed {consumed:,} Kafka messages "
                        f"| Inserted {inserted_total:,} rows"
                    )

            except Exception as exc:
                print(
                    f"Failed to process Kafka message: {exc}"
                )

    except KeyboardInterrupt:
        print("\nStopping consumer.")

    finally:
        consumer.close()


if __name__ == "__main__":
    main()