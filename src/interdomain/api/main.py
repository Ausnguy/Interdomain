from fastapi import FastAPI, Query

from interdomain.storage.postgres import get_connection

app = FastAPI(
    title="Interdomain API",
    version="0.1.0",
    description="API for live BGP routing analytics.",
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics/summary")
def summary():
    query = """
        SELECT
            COUNT(*) AS total_events,
            COUNT(*) FILTER (
                WHERE event_type = 'announcement'
            ) AS announcements,
            COUNT(*) FILTER (
                WHERE event_type = 'withdrawal'
            ) AS withdrawals,
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


@app.get("/routes/recent")
def recent_routes(
    limit: int = Query(default=25, ge=1, le=200)
):
    query = """
        SELECT
            observed_at,
            peer_asn,
            prefix::text,
            event_type,
            as_path,
            next_hop::text
        FROM bgp_events
        ORDER BY observed_at DESC
        LIMIT %s;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (limit,))
            rows = cur.fetchall()

    return [
        {
            "observed_at": row[0],
            "peer_asn": row[1],
            "prefix": row[2],
            "event_type": row[3],
            "as_path": row[4],
            "next_hop": row[5],
        }
        for row in rows
    ]


@app.get("/routes/withdrawals")
def withdrawals(
    limit: int = Query(default=25, ge=1, le=200)
):
    query = """
        SELECT
            observed_at,
            peer_asn,
            prefix::text,
            as_path
        FROM bgp_events
        WHERE event_type = 'withdrawal'
        ORDER BY observed_at DESC
        LIMIT %s;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (limit,))
            rows = cur.fetchall()

    return [
        {
            "observed_at": row[0],
            "peer_asn": row[1],
            "prefix": row[2],
            "as_path": row[3],
        }
        for row in rows
    ]


@app.get("/asns/active")
def active_asns(
    limit: int = Query(default=10, ge=1, le=100)
):
    query = """
        SELECT
            peer_asn,
            COUNT(*) AS update_count
        FROM bgp_events
        WHERE observed_at >= NOW() - INTERVAL '1 hour'
        GROUP BY peer_asn
        ORDER BY update_count DESC
        LIMIT %s;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (limit,))
            rows = cur.fetchall()

    return [
        {
            "peer_asn": row[0],
            "update_count": row[1],
        }
        for row in rows
    ]