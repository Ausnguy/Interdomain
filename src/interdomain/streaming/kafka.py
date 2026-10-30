import json
from typing import Any, Callable, Iterable

from confluent_kafka import Consumer, KafkaError, KafkaException, Producer

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
            # Retries cannot create duplicates or reorder messages: the broker
            # drops a resend it has already stored. Implies acks=all.
            "enable.idempotence": True,
        }
    )


class DeliveryStats:
    """Counts what the broker confirmed, not just what was queued.

    produce() only puts a message in a local queue. The broker's answer
    arrives later, as a callback fired from poll() or flush().
    """

    def __init__(self) -> None:
        self.delivered = 0
        self.failed = 0
        self.last_error: str | None = None

    def on_delivery(self, err, msg) -> None:
        if err is None:
            self.delivered += 1
        else:
            self.failed += 1
            self.last_error = str(err)


def resolve_start_offset(
    stored: int,
    low: int,
    high: int,
) -> tuple[int, str | None]:
    """Decide where to resume, given Postgres' offset and what Kafka still holds.

    `low` is the oldest offset Kafka retains and `high` is the next offset it
    will assign. Returns (offset to start at, warning or None).
    """
    if stored < low:
        return low, (
            f"stored offset {stored:,} is older than Kafka's oldest message "
            f"({low:,}); {low - stored:,} messages expired before they were "
            f"read. Resuming at {low:,}."
        )

    if stored > high:
        return low, (
            f"stored offset {stored:,} is past Kafka's newest ({high:,}); "
            f"the topic was probably recreated. Restarting at {low:,}."
        )

    return stored, None


def _checked_start(consumer: Consumer, partition, stored: int) -> int:
    try:
        low, high = consumer.get_watermark_offsets(partition, timeout=5.0)
    except KafkaException as exc:
        print(
            f"Could not check offsets for {partition.topic}[{partition.partition}] "
            f"({exc}); using stored offset {stored:,}"
        )
        return stored

    offset, warning = resolve_start_offset(stored, low, high)

    if warning:
        print(f"WARNING {partition.topic}[{partition.partition}]: {warning}")

    return offset


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
                partition.offset = _checked_start(
                    consumer,
                    partition,
                    stored[partition.partition],
                )

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
    on_delivery: Callable | None = None,
    queue_full_retries: int = 5,
) -> None:
    peer_asn = event.get("peer_asn")

    for _ in range(queue_full_retries):
        try:
            producer.produce(
                topic=KAFKA_BGP_TOPIC,
                key=str(peer_asn) if peer_asn else None,
                value=json.dumps(event),
                on_delivery=on_delivery,
            )
            break
        except BufferError:
            # The local queue is full: Kafka (or the network) is slower than
            # the feed. Block briefly so the queue can drain instead of
            # dropping the event or growing memory without limit.
            producer.poll(1.0)
    else:
        raise BufferError("Kafka producer queue stayed full; giving up on this event")

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
            print(
                f"Skipping undecodable message at "
                f"{key[0]}[{key[1]}]@{message.offset():,}: {exc}"
            )
            skipped += 1

    return rows, skipped, offsets
