import pytest

from interdomain.streaming.kafka import DeliveryStats, produce_bgp_event


class FakeProducer:
    def __init__(self, full_times: int = 0):
        self.full_times = full_times
        self.produced: list[dict] = []
        self.polls: list[float] = []

    def produce(self, **kwargs):
        if self.full_times > 0:
            self.full_times -= 1
            raise BufferError("queue full")
        self.produced.append(kwargs)

    def poll(self, timeout):
        self.polls.append(timeout)


def test_event_is_queued_with_delivery_callback():
    producer = FakeProducer()
    stats = DeliveryStats()

    produce_bgp_event(producer, {"peer_asn": 64500}, on_delivery=stats.on_delivery)

    assert producer.produced[0]["key"] == "64500"
    assert producer.produced[0]["on_delivery"] == stats.on_delivery


def test_full_queue_waits_then_succeeds():
    producer = FakeProducer(full_times=2)

    produce_bgp_event(producer, {"peer_asn": 1})

    assert len(producer.produced) == 1
    # two blocking polls to drain the queue, then the normal poll(0)
    assert producer.polls == [1.0, 1.0, 0]


def test_queue_that_never_drains_raises():
    producer = FakeProducer(full_times=100)

    with pytest.raises(BufferError):
        produce_bgp_event(producer, {"peer_asn": 1}, queue_full_retries=3)

    assert producer.produced == []


def test_delivery_stats_count_success_and_failure():
    stats = DeliveryStats()

    stats.on_delivery(None, object())
    stats.on_delivery(None, object())
    stats.on_delivery("broker down", object())

    assert stats.delivered == 2
    assert stats.failed == 1
    assert stats.last_error == "broker down"
