from collections.abc import Sequence


def withdrawal_ratio(event_types: Sequence[str]) -> float:
    if not event_types:
        return 0.0
    return sum(1 for x in event_types if x == "withdrawal") / len(event_types)


def is_withdrawal_spike(event_types: Sequence[str], threshold: float = 0.40, minimum_events: int = 20) -> bool:
    return len(event_types) >= minimum_events and withdrawal_ratio(event_types) >= threshold
