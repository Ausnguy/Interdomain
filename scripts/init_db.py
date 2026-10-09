from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from interdomain.storage.postgres import get_connection

schema_sql = (ROOT / "sql" / "schema.sql").read_text(encoding="utf-8")
with get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute(schema_sql)
    conn.commit()
print("Database schema initialized.")
