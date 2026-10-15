from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from interdomain.storage.postgres import get_connection


app = FastAPI(
    title="Interdomain API",
    version="0.1.0",
    description=(
        "API for live BGP routing analytics. Aggregate endpoints cover the "
        "last 60 one-minute buckets, read from pre-aggregated tables. "
        "Regions and countries describe where RIPE RIS collectors are "
        "located, not where the affected prefixes are."
    ),
)


app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# The current (partial) minute plus the 59 before it. Same buckets as the
# /metrics/activity series.
WINDOW_START = "date_trunc('minute', NOW()) - INTERVAL '59 minutes'"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/ingestion")
def ingestion_health():
    query = """
        SELECT
            MAX(observed_at),
            EXTRACT(
                EPOCH FROM (NOW() - MAX(observed_at))
            )
        FROM bgp_events;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            row = cur.fetchone()

    last_event = row[0]
    age_seconds = float(row[1]) if row[1] is not None else None

    if age_seconds is None:
        status = "offline"
    elif age_seconds < 15:
        status = "live"
    elif age_seconds < 60:
        status = "stale"
    else:
        status = "offline"

    return {
        "status": status,
        "last_event": last_event,
        "age_seconds": age_seconds,
    }


@app.get("/metrics/summary")
def summary():
    query = f"""
        SELECT
            COALESCE(SUM(announcements + withdrawals), 0)::bigint AS total_events,
            COALESCE(SUM(announcements), 0)::bigint AS announcements,
            COALESCE(SUM(withdrawals), 0)::bigint AS withdrawals,
            COUNT(DISTINCT peer_asn) FILTER (
                WHERE peer_asn <> 0
            ) AS unique_peer_asns,
            COALESCE((
                SELECT unique_prefixes
                FROM bgp_prefix_counts
                WHERE scope = 'global' AND key = 'all'
            ), 0) AS unique_prefixes
        FROM bgp_minute_stats
        WHERE minute >= {WINDOW_START};
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

@app.get("/regions/summary")
def regional_summary():
    query = f"""
        SELECT
            stats.collector_region AS region,
            SUM(stats.announcements + stats.withdrawals)::bigint AS total_events,
            SUM(stats.announcements)::bigint AS announcements,
            SUM(stats.withdrawals)::bigint AS withdrawals,
            COUNT(DISTINCT stats.collector) FILTER (
                WHERE stats.collector <> 'unknown'
            ) AS collectors,
            COUNT(DISTINCT stats.peer_asn) FILTER (
                WHERE stats.peer_asn <> 0
            ) AS unique_peer_asns,
            COALESCE(MAX(counts.unique_prefixes), 0) AS unique_prefixes
        FROM bgp_minute_stats AS stats
        LEFT JOIN bgp_prefix_counts AS counts
            ON counts.scope = 'region'
            AND counts.key = stats.collector_region
        WHERE stats.minute >= {WINDOW_START}
        GROUP BY stats.collector_region
        ORDER BY total_events DESC;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()

    return [
        {
            "region": row[0],
            "total_events": row[1],
            "announcements": row[2],
            "withdrawals": row[3],
            "collectors": row[4],
            "unique_peer_asns": row[5],
            "unique_prefixes": row[6],
        }
        for row in rows
    ]
@app.get("/metrics/activity")
def routing_activity():
    query = f"""
        WITH minutes AS (
            SELECT generate_series(
                {WINDOW_START},
                date_trunc('minute', NOW()),
                INTERVAL '1 minute'
            ) AS minute
        ),
        activity AS (
            SELECT
                minute,
                SUM(announcements + withdrawals)::bigint AS updates,
                SUM(announcements)::bigint AS announcements,
                SUM(withdrawals)::bigint AS withdrawals
            FROM bgp_minute_stats
            WHERE minute >= {WINDOW_START}
            GROUP BY minute
        )
        SELECT
            minutes.minute,
            COALESCE(activity.updates, 0),
            COALESCE(activity.announcements, 0),
            COALESCE(activity.withdrawals, 0)
        FROM minutes
        LEFT JOIN activity USING (minute)
        ORDER BY minutes.minute;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()

    return [
        {
            "minute": row[0],
            "updates": row[1],
            "announcements": row[2],
            "withdrawals": row[3],
        }
        for row in rows
    ]


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
            next_hop::text,
            collector,
            collector_region
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
            "collector": row[6],
            "collector_region": row[7],
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
    query = f"""
        SELECT
            NULLIF(peer_asn, 0) AS peer_asn,
            SUM(announcements + withdrawals)::bigint AS update_count
        FROM bgp_minute_stats
        WHERE minute >= {WINDOW_START}
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

@app.get("/collectors/activity")
def collector_activity():
    query = f"""
        SELECT
            stats.collector,
            stats.collector_region,
            SUM(stats.announcements + stats.withdrawals)::bigint AS total_events,
            SUM(stats.announcements)::bigint AS announcements,
            SUM(stats.withdrawals)::bigint AS withdrawals,
            COUNT(DISTINCT stats.peer_asn) FILTER (
                WHERE stats.peer_asn <> 0
            ) AS unique_peer_asns,
            COALESCE(MAX(counts.unique_prefixes), 0) AS unique_prefixes
        FROM bgp_minute_stats AS stats
        LEFT JOIN bgp_prefix_counts AS counts
            ON counts.scope = 'collector'
            AND counts.key = stats.collector
        WHERE
            stats.minute >= {WINDOW_START}
            AND stats.collector <> 'unknown'
        GROUP BY
            stats.collector,
            stats.collector_region
        ORDER BY
            total_events DESC;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()

    return [
        {
            "collector": row[0],
            "collector_region": row[1],
            "total_events": row[2],
            "announcements": row[3],
            "withdrawals": row[4],
            "unique_peer_asns": row[5],
            "unique_prefixes": row[6],
        }
        for row in rows
    ]
