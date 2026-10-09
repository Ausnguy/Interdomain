# Architecture

## V1

```text
RIPE RIS Live → Python WebSocket client → normalization → PostgreSQL → SQL/FastAPI
```

## Future

```text
RIPE RIS Live → Python → Kafka → Spark Structured Streaming → Databricks/Delta Lake → dbt → PostgreSQL → FastAPI → React
```

Potential reliability checks: withdrawal spikes, abnormal update volume, rapidly changing AS paths, duplicate events, malformed records, stale ingestion, source disconnects, consumer lag.
