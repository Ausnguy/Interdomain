# Interdomain

Real-time BGP routing observability and anomaly detection platform.

## V1 architecture

```text
RIPE RIS Live
     ↓
Python ingestion
     ↓
Normalization
     ↓
PostgreSQL
     ↓
SQL analytics / FastAPI
```

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d
# copy .env.example to .env
python scripts/init_db.py
python scripts/run_ingestion.py
```

Run the API:

```bash
uvicorn interdomain.api.main:app --app-dir src --reload
```

Open `http://127.0.0.1:8000/docs`.

## Storage

RIPE RIS Live produces roughly 10–30k route events per second, so dashboard
metrics never scan raw events:

- `bgp_events`: raw events in hourly partitions, kept `RAW_RETENTION_HOURS`
  (default 2). Old partitions are dropped, not deleted from.
- `bgp_minute_stats`: per-minute announcement/withdrawal counts by collector
  and peer ASN, kept `ROLLUP_RETENTION_DAYS` (default 7). Written by the
  consumer in the same transaction as the raw rows.
- `bgp_prefix_seen` / `bgp_prefix_counts`: exact distinct-prefix counts for
  the last hour, refreshed every 30 seconds.
- `kafka_offsets`: the consumer's position, committed with the data so a
  crash never loses or double-counts a batch. To skip ahead in Kafka, update
  this row; resetting the Kafka consumer group alone has no effect.

Run `scripts/run_maintenance.py` alongside the consumer (it creates and drops
partitions and refreshes prefix counts), and `scripts/pipeline_stats.py` to
see API latency, table sizes, ingest rate and lag.

Regions and countries describe where RIPE collectors are located, not where
the affected prefixes are.

## Later

Add Kafka → Spark/Databricks → Delta Lake → dbt → Airflow → React only after V1 works.
