from fastapi import FastAPI
from interdomain.storage.postgres import get_connection

app = FastAPI(title="Interdomain API", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics/summary")
def summary():
    query = """
        SELECT
            COUNT(*) AS total_events,
            COUNT(*) FILTER (WHERE event_type = 'announcement') AS announcements,
            COUNT(*) FILTER (WHERE event_type = 'withdrawal') AS withdrawals,
            COUNT(DISTINCT peer_asn) AS unique_peer_asns,
            COUNT(DISTINCT prefix) AS unique_prefixes
        FROM bgp_events
        WHERE observed_at >= NOW() - INTERVAL '1 hour';
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            row = cur.fetchone()
    return {
        "window": "1 hour",
        "total_events": row[0],
        "announcements": row[1],
        "withdrawals": row[2],
        "unique_peer_asns": row[3],
        "unique_prefixes": row[4],
    }
