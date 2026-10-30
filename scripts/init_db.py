from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from interdomain.storage.migrate import run_migrations
from interdomain.storage.postgres import connect


def main():
    conn = connect()

    try:
        applied = run_migrations(
            conn,
            ROOT / "sql" / "schema.sql",
            ROOT / "sql" / "migrations",
        )
    finally:
        conn.close()

    if applied:
        print(f"Applied: {', '.join(applied)}")
    else:
        print("Database is up to date.")


if __name__ == "__main__":
    main()
