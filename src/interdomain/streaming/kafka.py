import json

from confluent_kafka import Consumer, Producer

from interdomain.config import (
    KAFKA_BGP_TOPIC,
    KAFKA_BOOTSTRAP_SERVERS,
)


def create_producer() -> Producer:
    return Producer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "client.id": "interdomain-ripe-producer",
        }
    )


def create_consumer() -> Consumer:
    consumer = Consumer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "group.id": "interdomain-postgres-consumer",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )

    consumer.subscribe([KAFKA_BGP_TOPIC])

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