import re
from dataclasses import dataclass
from pathlib import Path

import psycopg

MIGRATION_LOCK_KEY = 4_821_002
BASELINE = "001_baseline"
# schema.sql already contains everything these migrations add, so a database
# created from it must not run them.
BASELINE_COVERS_THROUGH = "003"

VERSION_FILE = re.compile(r"^(\d{3})_.+\.sql$")


@dataclass
class MigrationPlan:
    run_schema: bool
    record_only: list[str]
    to_run: list[str]


def discover(migrations_dir: Path) -> list[str]:
    """Migration versions (file stems) in numeric order."""
    return sorted(
        path.stem
        for path in migrations_dir.iterdir()
        if VERSION_FILE.match(path.name)
    )


def detect_state(conn: psycopg.Connection) -> str:
    """'fresh' (no tables), 'partitioned' (current layout) or 'legacy'."""
    with conn.cursor() as cur:
        cur.execute("SELECT relkind FROM pg_class WHERE relname = 'bgp_events'")
        row = cur.fetchone()

    if row is None:
        return "fresh"

    return "partitioned" if row[0] == "p" else "legacy"


def plan_migrations(
    applied: set[str],
    state: str,
    discovered: list[str],
) -> MigrationPlan:
    """Decide what to run. Pure, so it can be tested without a database."""
    if applied:
        return MigrationPlan(False, [], [v for v in discovered if v not in applied])

    covered = [v for v in discovered if v[:3] <= BASELINE_COVERS_THROUGH]
    later = [v for v in discovered if v[:3] > BASELINE_COVERS_THROUGH]

    if state == "fresh":
        # schema.sql creates the current layout in one go.
        return MigrationPlan(True, [BASELINE, *covered], later)

    if state == "partitioned":
        # An existing database that already went through those upgrades.
        return MigrationPlan(False, [BASELINE, *covered], later)

    # legacy: the original v1 table. Upgrade it step by step.
    return MigrationPlan(False, [BASELINE], covered + later)


def _has_own_transaction(sql_text: str) -> bool:
    return any(line.strip().upper() == "BEGIN;" for line in sql_text.splitlines())


def _record(cur, version: str) -> None:
    cur.execute(
        "INSERT INTO schema_migrations (version) VALUES (%s) ON CONFLICT DO NOTHING",
        (version,),
    )


def run_migrations(
    conn: psycopg.Connection,
    schema_path: Path,
    migrations_dir: Path,
) -> list[str]:
    """Bring the database up to date. `conn` must be in autocommit mode.

    Returns the versions that were applied (not merely recorded).
    """
    applied_now: list[str] = []

    with conn.cursor() as cur:
        # Block, don't skip: two runners at once would apply a migration twice.
        cur.execute("SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK_KEY,))

        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute("SELECT version FROM schema_migrations")
            applied = {version for (version,) in cur.fetchall()}

            plan = plan_migrations(
                applied,
                detect_state(conn),
                discover(migrations_dir),
            )

            if plan.run_schema:
                cur.execute(schema_path.read_text(encoding="utf-8"))
                applied_now.append(BASELINE)

            for version in plan.record_only:
                _record(cur, version)

            for version in plan.to_run:
                sql_text = (migrations_dir / f"{version}.sql").read_text(encoding="utf-8")

                if _has_own_transaction(sql_text):
                    # The file manages its own BEGIN/COMMIT.
                    cur.execute(sql_text)
                    _record(cur, version)
                else:
                    with conn.transaction():
                        cur.execute(sql_text)
                        _record(cur, version)

                applied_now.append(version)

        finally:
            cur.execute("SELECT pg_advisory_unlock(%s)", (MIGRATION_LOCK_KEY,))

    return applied_now
