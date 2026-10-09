from datetime import datetime, timezone
from typing import Any


def normalize_next_hop(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, list):
        return value[0] if value else None

    if isinstance(value, str):
        return value.split(",")[0].strip()

    return str(value)


def normalize_bgp_event(event: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    timestamp = event.get("timestamp")
    observed_at = (
        datetime.fromtimestamp(timestamp, tz=timezone.utc)
        if timestamp is not None
        else datetime.now(timezone.utc)
    )

    common = {
        "observed_at": observed_at,
        "peer": event.get("peer"),
        "peer_asn": event.get("peer_asn"),
        "path": event.get("path"),
    }

    for announcement in event.get("announcements", []) or []:
        for prefix in announcement.get("prefixes", []) or []:
            rows.append(
                {
                    **common,
                    "event_type": "announcement",
                    "prefix": prefix,
                    "next_hop": normalize_next_hop(
                        announcement.get("next_hop")
                    ),
                }
            )

    for prefix in event.get("withdrawals", []) or []:
        rows.append(
            {
                **common,
                "event_type": "withdrawal",
                "prefix": prefix,
                "next_hop": None,
            }
        )

    return rows