import json

from confluent_kafka import KafkaError

from interdomain.storage.postgres import _row_values
from interdomain.streaming.kafka import decode_batch


class FakeMessage:
    def __init__(self, value=None, error=None, offset=0, partition=0):
        self._value = value
        self._error = error
        self._offset = offset
        self._partition = partition

    def value(self):
        return self._value

    def error(self):
        return self._error

    def topic(self):
        return "bgp-updates"

    def partition(self):
        return self._partition

    def offset(self):
        return self._offset


EVENT = {
    "timestamp": 1700000000,
    "peer": "192.0.2.1",
    "peer_asn": "64500",
    "host": "rrc00.ripe.net",
    "path": [64500, 64496],
    "announcements": [{"next_hop": "192.0.2.2", "prefixes": ["203.0.113.0/24"]}],
    "withdrawals": ["198.51.100.0/24"],
}


def test_decodes_valid_batch():
    messages = [
        FakeMessage(json.dumps(EVENT).encode(), offset=offset)
        for offset in (10, 11, 12)
    ]

    rows, skipped, offsets = decode_batch(messages)

    assert len(rows) == 6
    assert skipped == 0
    assert offsets == {("bgp-updates", 0): 13}


def test_skips_malformed_message_but_still_advances_its_offset():
    messages = [
        FakeMessage(json.dumps(EVENT).encode(), offset=5),
        FakeMessage(b"{not json", offset=6),
    ]

    rows, skipped, offsets = decode_batch(messages)

    assert len(rows) == 2
    assert skipped == 1
    assert offsets == {("bgp-updates", 0): 7}


def test_skips_error_message_and_ignores_partition_eof():
    messages = [
        FakeMessage(error=KafkaError(KafkaError._PARTITION_EOF)),
        FakeMessage(error=KafkaError(KafkaError._TRANSPORT)),
        FakeMessage(json.dumps(EVENT).encode()),
    ]

    rows, skipped, _ = decode_batch(messages)

    assert len(rows) == 2
    assert skipped == 1


def test_row_values_casts_asn_and_flattens_as_sets():
    rows, _, _ = decode_batch(
        [FakeMessage(json.dumps({**EVENT, "path": [64500, [64501, 64502]]}).encode())]
    )

    values = _row_values(rows[0])

    assert values[2] == 64500
    assert values[7] == [64500, 64501, 64502]
