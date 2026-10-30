import psycopg
import pytest

from interdomain.storage.maintenance import run_step


def test_returns_the_steps_result():
    assert run_step("step", lambda: ["bgp_events_p2026103003"], []) == ["bgp_events_p2026103003"]


def test_database_error_returns_default_so_other_steps_can_run():
    def duplicate():
        raise psycopg.errors.DuplicateTable("already exists")

    assert run_step("Creating partitions", duplicate, []) == []


def test_busy_lock_is_deferred_not_fatal():
    def busy():
        raise psycopg.errors.LockNotAvailable("lock timeout")

    assert run_step("Dropping partitions", busy, []) == []


def test_connection_problems_propagate_so_the_caller_reconnects():
    def down():
        raise psycopg.OperationalError("server closed the connection")

    with pytest.raises(psycopg.OperationalError):
        run_step("Deleting minute stats", down, 0)
