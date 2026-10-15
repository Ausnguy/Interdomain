"""Pre-aggregation of normalized BGP rows for the dashboard tables.

Rows are the dicts produced by normalize_bgp_event. Everything here is pure
and in-memory so the consumer can write raw rows and their aggregates in one
database transaction.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable


# Primary-key columns can't be NULL, so unknown values get sentinels.
UNKNOWN_COLLECTOR = "unknown"
UNKNOWN_PEER_ASN = 0


def minute_of(value: datetime) -> datetime:
    return value.replace(second=0, microsecond=0)


def collector_key(row: dict[str, Any]) -> str:
    return row.get("collector") or UNKNOWN_COLLECTOR


def peer_key(row: dict[str, Any]) -> int:
    peer_asn = row.get("peer_asn")

    if peer_asn in (None, ""):
        return UNKNOWN_PEER_ASN

    return int(peer_asn)


def aggregate_minute_stats(
    rows: Iterable[dict[str, Any]],
) -> list[tuple]:
    """Count announcements and withdrawals per (minute, collector, peer).

    Returns (minute, collector, collector_region, peer_asn, announcements,
    withdrawals) tuples, one per key, sorted by key.
    """
    counts: dict[tuple, list] = {}

    for row in rows:
        key = (
            minute_of(row["observed_at"]),
            collector_key(row),
            peer_key(row),
        )

        entry = counts.get(key)

        if entry is None:
            entry = counts[key] = [
                row.get("collector_region") or "unknown",
                0,
                0,
            ]

        if row["event_type"] == "announcement":
            entry[1] += 1
        else:
            entry[2] += 1

    return [
        (minute, collector, region, peer, announcements, withdrawals)
        for (minute, collector, peer), (region, announcements, withdrawals)
        in sorted(counts.items())
    ]


@dataclass
class PrefixPlan:
    pairs: list[tuple]
    written: dict[tuple, datetime]
    minute: datetime | None


@dataclass
class PrefixActivityTracker:
    """Limits bgp_prefix_seen upserts to one per (collector, prefix) per minute.

    The table only needs minute precision to answer "seen in the last hour",
    and most prefixes repeat many times a minute. plan() is side-effect free;
    apply() is called only after the database transaction commits, so a
    rolled-back batch is written again on retry.
    """

    written: dict[tuple, datetime] = field(default_factory=dict)
    minute: datetime | None = None

    def plan(self, rows: Iterable[dict[str, Any]]) -> PrefixPlan:
        latest: dict[tuple, list] = {}
        current = self.minute

        for row in rows:
            observed = row["observed_at"]
            row_minute = minute_of(observed)

            if current is None or row_minute > current:
                current = row_minute

            key = (collector_key(row), row["prefix"])
            entry = latest.get(key)

            if entry is None:
                latest[key] = [row.get("collector_region") or "unknown", observed]
            elif observed > entry[1]:
                entry[1] = observed

        # A new minute starts with an empty set, so every pair is written
        # at least once per minute.
        previous = self.written if current == self.minute else {}

        pairs = []
        written = {}

        for (collector, prefix), (region, observed) in latest.items():
            row_minute = minute_of(observed)
            already = previous.get((collector, prefix))

            if already is None or already < row_minute:
                pairs.append((collector, prefix, region, observed))
                written[(collector, prefix)] = row_minute

        pairs.sort()

        return PrefixPlan(pairs=pairs, written=written, minute=current)

    def apply(self, plan: PrefixPlan) -> None:
        if plan.minute != self.minute:
            self.written = {}
            self.minute = plan.minute

        self.written.update(plan.written)
