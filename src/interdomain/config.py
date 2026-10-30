import os
from dotenv import load_dotenv
from psycopg.conninfo import make_conninfo

load_dotenv()

RIPE_WS_URL = os.getenv("RIPE_WS_URL", "wss://ris-live.ripe.net/v1/ws/?client=interdomain")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "interdomain")
POSTGRES_USER = os.getenv("POSTGRES_USER", "interdomain")
# No default: a password shipped in the code is a password everyone knows.
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")


def postgres_dsn() -> str:
    if not POSTGRES_PASSWORD:
        raise RuntimeError(
            "POSTGRES_PASSWORD is not set. Copy .env.example to .env and "
            "choose a password."
        )

    # make_conninfo quotes values, so a password with spaces or quotes works.
    return make_conninfo(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
    )

KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "localhost:9092",
)

KAFKA_BGP_TOPIC = os.getenv(
    "KAFKA_BGP_TOPIC",
    "bgp-updates",
)

# Kafka messages written to Postgres per COPY + offset commit.
CONSUMER_BATCH_SIZE = int(
    os.getenv("CONSUMER_BATCH_SIZE", "5000")
)

# Raw bgp_events partitions older than this are dropped by
# scripts/run_maintenance.py. Dashboard metrics come from the rollups.
RAW_RETENTION_HOURS = float(
    os.getenv("RAW_RETENTION_HOURS", "2")
)

# bgp_minute_stats rows older than this are deleted.
ROLLUP_RETENTION_DAYS = float(
    os.getenv("ROLLUP_RETENTION_DAYS", "7")
)