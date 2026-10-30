import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict

from interdomain import config
from interdomain.storage.migrate import BASELINE, plan_migrations

FILES = ["002_add_collector_region", "003_rollups_partitioning", "004_future"]


def test_fresh_database_runs_schema_and_records_what_it_already_contains():
    plan = plan_migrations(set(), "fresh", FILES)

    assert plan.run_schema is True
    assert plan.record_only == [BASELINE, "002_add_collector_region", "003_rollups_partitioning"]
    assert plan.to_run == ["004_future"]


def test_existing_partitioned_database_is_recorded_without_running_anything_old():
    plan = plan_migrations(set(), "partitioned", FILES)

    assert plan.run_schema is False
    assert plan.record_only == [BASELINE, "002_add_collector_region", "003_rollups_partitioning"]
    assert plan.to_run == ["004_future"]


def test_legacy_database_upgrades_step_by_step():
    plan = plan_migrations(set(), "legacy", FILES)

    assert plan.run_schema is False
    assert plan.record_only == [BASELINE]
    assert plan.to_run == FILES


def test_tracked_database_runs_only_new_migrations():
    applied = {BASELINE, "002_add_collector_region", "003_rollups_partitioning"}

    plan = plan_migrations(applied, "partitioned", FILES)

    assert plan.run_schema is False
    assert plan.record_only == []
    assert plan.to_run == ["004_future"]


def test_dsn_requires_a_password(monkeypatch):
    monkeypatch.setattr(config, "POSTGRES_PASSWORD", "")

    with pytest.raises(RuntimeError, match="POSTGRES_PASSWORD"):
        config.postgres_dsn()


def test_dsn_survives_awkward_passwords(monkeypatch):
    monkeypatch.setattr(config, "POSTGRES_PASSWORD", "it's a \"tricky\" pass")

    parsed = conninfo_to_dict(config.postgres_dsn())

    assert parsed["password"] == "it's a \"tricky\" pass"
