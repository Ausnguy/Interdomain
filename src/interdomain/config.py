import os
from dotenv import load_dotenv

load_dotenv()

RIPE_WS_URL = os.getenv("RIPE_WS_URL", "wss://ris-live.ripe.net/v1/ws/?client=interdomain")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "interdomain")
POSTGRES_USER = os.getenv("POSTGRES_USER", "interdomain")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "interdomain")


def postgres_dsn() -> str:
    return (
        f"host={POSTGRES_HOST} port={POSTGRES_PORT} dbname={POSTGRES_DB} "
        f"user={POSTGRES_USER} password={POSTGRES_PASSWORD}"
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