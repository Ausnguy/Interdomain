from collections.abc import Callable
from typing import TypeVar

import psycopg

T = TypeVar("T")


def run_step(name: str, action: Callable[[], T], default: T) -> T:
    """Run one maintenance step so a single failure cannot stop the others.

    Connection problems are re-raised: the caller owns the connection and
    reconnects. Anything else the database reports is printed and the step's
    `default` is returned, so the remaining steps still run this cycle.
    """
    try:
        return action()

    # LockNotAvailable subclasses OperationalError, so it comes first.
    except psycopg.errors.LockNotAvailable as exc:
        print(f"{name} deferred (lock busy): {exc}")

    except psycopg.OperationalError:
        raise

    except psycopg.Error as exc:
        print(f"{name} failed: {exc}")

    return default
