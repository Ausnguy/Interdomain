import random
from collections.abc import Callable


def backoff_delay(
    attempt: int,
    base: float = 1.0,
    cap: float = 60.0,
    rng: Callable[[], float] = random.random,
) -> float:
    """Seconds to wait before reconnect number `attempt` (0 = first retry).

    Exponential growth (base, 2*base, 4*base, ...) capped at `cap`, then
    "full jitter": a random point between 0 and that ceiling, so many clients
    that dropped at the same moment do not all retry at the same moment.
    """
    ceiling = min(cap, base * (2 ** max(attempt, 0)))
    return ceiling * rng()
