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
