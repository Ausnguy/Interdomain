import json
from typing import Any, Callable, Iterable

from confluent_kafka import Consumer, KafkaError, Producer

from interdomain.config import (
    KAFKA_BGP_TOPIC,
    KAFKA_BOOTSTRAP_SERVERS,
)
from interdomain.processing.normalize import normalize_bgp_event


def create_producer() -> Producer:
    return Producer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "client.id": "interdomain-ripe-producer",
            # RIS JSON compresses well; batching for a few ms lets lz4
            # work on whole batches instead of single messages.
            "compression.type": "lz4",
            "linger.ms": 20,
        }
    )


def create_consumer(
    load_offsets: Callable[[], dict[int, int]] | None = None,
) -> Consumer:
    """Subscribe to the BGP topic.

    `load_offsets` returns {partition: next_offset} from Postgres. On every
    assignment the consumer seeks there, so the database (which stores
    offsets in the same transaction as the data) decides where to resume.
    Partitions without a stored offset use Kafka's committed offset.
    """
    consumer = Consumer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "group.id": "interdomain-postgres-consumer",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
            # Prefetch large chunks so consume() can return full batches.
            "fetch.min.bytes": 1_048_576,
            "fetch.wait.max.ms": 500,
            "queued.max.messages.kbytes": 65_536,
        }
    )

    def on_assign(consumer, partitions):
        stored = load_offsets() if load_offsets else {}

        for partition in partitions:
            if partition.partition in stored:
                partition.offset = stored[partition.partition]

        consumer.assign(partitions)

        print(
            "Assigned "
            + ", ".join(
                f"{p.topic}[{p.partition}] @ "
                + (f"{p.offset:,} (postgres)" if p.partition in stored else "committed")
                for p in partitions
            )
        )

    consumer.subscribe([KAFKA_BGP_TOPIC], on_assign=on_assign)

    return consumer


def produce_bgp_event(
    producer: Producer,
    event: dict,
) -> None:
    peer_asn = event.get("peer_asn")

    producer.produce(
        topic=KAFKA_BGP_TOPIC,
        key=str(peer_asn) if peer_asn else None,
        value=json.dumps(event),
    )

    producer.poll(0)


def decode_bgp_event(value: bytes) -> dict:
    return json.loads(value.decode("utf-8"))


def decode_batch(
    messages: Iterable[Any],
) -> tuple[list[dict], int, dict[tuple[str, int], int]]:
    """Decode and normalize a batch of Kafka messages.

    Returns the database rows, the number of messages skipped, and the next
    offset to read per (topic, partition). One bad message is logged and
    skipped rather than failing the whole batch; its offset still advances.
    """
    rows: list[dict] = []
    skipped = 0
    offsets: dict[tuple[str, int], int] = {}

    for message in messages:
        error = message.error()

        if error is not None:
            if error.code() != KafkaError._PARTITION_EOF:
                print(f"Kafka error: {error}")
                skipped += 1
            continue

        key = (message.topic(), message.partition())
        offsets[key] = max(offsets.get(key, 0), message.offset() + 1)

        try:
            rows.extend(
                normalize_bgp_event(
                    decode_bgp_event(message.value())
                )
            )
        except Exception as exc:
            print(f"Skipping undecodable Kafka message: {exc}")
            skipped += 1

    return rows, skipped, offsets
