from datetime import datetime, timezone

from interdomain.processing.rollups import (
    PrefixActivityTracker,
    aggregate_minute_stats,
)


def at(minute, second=0):
    return datetime(2026, 10, 15, 6, minute, second, tzinfo=timezone.utc)


def row(observed_at, prefix="203.0.113.0/24", event_type="announcement",
        collector="rrc00.ripe.net", peer_asn="64500", region="global"):
    return {
        "observed_at": observed_at,
        "prefix": prefix,
        "event_type": event_type,
        "collector": collector,
        "collector_region": region,
        "peer_asn": peer_asn,
    }


def test_counts_per_minute_collector_and_peer():
    rows = [
        row(at(1, 5)),
        row(at(1, 50), event_type="withdrawal"),
        row(at(1, 59), peer_asn="64501"),
        row(at(2, 0)),
        row(at(1, 30), collector="rrc11.ripe.net", region="north_america"),
    ]

    stats = aggregate_minute_stats(rows)

    assert stats == [
        (at(1), "rrc00.ripe.net", "global", 64500, 1, 1),
        (at(1), "rrc00.ripe.net", "global", 64501, 1, 0),
        (at(1), "rrc11.ripe.net", "north_america", 64500, 1, 0),
        (at(2), "rrc00.ripe.net", "global", 64500, 1, 0),
    ]


def test_every_row_is_counted_exactly_once():
    rows = [row(at(m % 3, m), event_type=("withdrawal" if m % 4 else "announcement"))
            for m in range(50)]

    stats = aggregate_minute_stats(rows)

    assert sum(s[4] + s[5] for s in stats) == len(rows)


def test_unknown_peer_and_collector_use_sentinels():
    stats = aggregate_minute_stats([row(at(1), collector=None, peer_asn=None)])

    assert stats == [(at(1), "unknown", "global", 0, 1, 0)]


def test_prefix_written_once_per_minute():
    tracker = PrefixActivityTracker()

    first = tracker.plan([row(at(1, 5)), row(at(1, 40))])
    tracker.apply(first)
    again = tracker.plan([row(at(1, 50))])
    tracker.apply(again)
    next_minute = tracker.plan([row(at(2, 1))])

    assert first.pairs == [("rrc00.ripe.net", "203.0.113.0/24", "global", at(1, 40))]
    assert again.pairs == []
    assert next_minute.pairs == [("rrc00.ripe.net", "203.0.113.0/24", "global", at(2, 1))]


def test_unapplied_plan_is_planned_again_after_a_failed_write():
    tracker = PrefixActivityTracker()

    failed = tracker.plan([row(at(1, 5))])
    retried = tracker.plan([row(at(1, 5))])

    assert failed.pairs == retried.pairs != []


def test_late_row_does_not_hide_a_newer_sighting():
    tracker = PrefixActivityTracker()

    tracker.apply(tracker.plan([row(at(2, 0), prefix="198.51.100.0/24")]))
    late = tracker.plan([row(at(1, 59))])
    tracker.apply(late)
    newer = tracker.plan([row(at(2, 10))])

    assert late.pairs == [("rrc00.ripe.net", "203.0.113.0/24", "global", at(1, 59))]
    assert newer.pairs == [("rrc00.ripe.net", "203.0.113.0/24", "global", at(2, 10))]
