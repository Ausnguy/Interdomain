# Roadmap

Compiled from read-only audits and research. Web-sourced claims (free-tier terms, pricing, paper results) are
second-hand and need checking against official pages. Effort is rough, for one developer working part-time.

## Goal

A BGP observability platform that detects hijacks and leaks and explains them, built on a real streaming data
stack. Prior art exists (BGPalerter, ARTEMIS, Cloudflare Radar, and the BEAR paper), so the distinct angles are:

1. An explainer for detected events (BEAR-style path analysis plus RAG over RFCs and postmortems), with an
   evaluation set built from known incidents.
2. Data-engineering depth (Kafka, rollups, orchestrated history layer).
3. An investigation-focused UI.

## Phase 0: Measure and make it safe (about 1 week)

- Run `scripts/pipeline_stats.py` repeatedly to get the real event rate; the code comment says about 3k/s,
  far below the 10-30k assumed in sizing. Size everything from this number.
- Producer: websocket timeout and ping, reconnect with backoff and jitter, delivery callbacks, `BufferError`
  backpressure, idempotent producer, handle `ris_error`.
- Consumer: validate stored offsets against topic watermarks, add `on_revoke` and tracker reset, create the
  topic explicitly.
- Normalize host-bit CIDRs before COPY so one bad row cannot trigger the row-by-row fallback.
- Maintenance: advisory lock, per-step error handling, pre-create 24h of partitions.
- Delete or gate `scripts/run_ingestion.py` (bypasses Kafka, double-counts rollups).
- Remove default credentials; bind Postgres and Kafka to localhost; pin the Kafka image.
- Migration tool (Alembic or dbmate) with a version table; sync `schema.sql` with migrations 002/003.
- Postgres tuning for the box: `max_wal_size=8GB`, `wal_compression=on`; cut Kafka retention to 2h.

## Phase 1: Deployable (about 1 week)

- Dockerfiles, prod compose with healthchecks and restarts; drop or profile-gate the Spark service.
- `VITE_API_URL` instead of the hardcoded API address.
- GitHub Actions: ruff, pytest with a Postgres service, frontend build, image build.
- Split dev and runtime requirements; pin `confluent-kafka`; remove the stray root `package.json`.
- Host: Oracle Always Free ARM VM (allowance may now be 2 cores / 12 GB; verify), Cloudflare Tunnel for TLS,
  Cloudflare Pages for the frontend. Fallback: Hetzner (about EUR 6-15/mo).
- AWS for storage, not compute (credits expire, always-on instances get expensive): an S3 bucket with
  lifecycle rules for backups and Parquet history, a least-privilege IAM user for the VM, and a billing alert.
  R2 (10 GB free, no egress fees) is the fallback if costs matter.
- Terraform for the AWS resources (bucket, IAM, budget alert) so the setup is reproducible from the repo.
- Nightly `pg_dump` of non-raw tables to S3, with a restore test.

## Phase 2: API and operability (about 1-1.5 weeks)

- API: connection pool, statement timeout, exception handlers, DB-aware `/health`, key auth, configurable
  GET-only CORS, rate limits, response models, `/v1` prefix, short TTL cache.
- Indexes: `bgp_prefix_seen(last_seen)`, a partial index for withdrawals, prefix and peer lookups.
- Frontend: tolerate partial failures (`Promise.allSettled`), timeouts and backoff, lazy-load map and charts,
  accessibility pass, vitest for `signals.js` and the data hook.
- Structured logs, Prometheus metrics, Grafana alerts (stalled ingestion, lag, disk, failed maintenance).
- Integration tests for storage, consumer and API against real Postgres and Kafka; dead-letter topic.

## Phase 3: Detection (about 2-3 weeks)

Today there is no hijack detection: only per-minute counts and fixed withdrawal thresholds.

1. `bgp_alerts` table and a detector worker; move all thresholds server-side.
2. Preserve AS_SET boundaries in stored paths so origin extraction is unambiguous.
3. Prefix-to-origin state table; origin-change and MOAS detection.
4. RPKI route origin validation (a validator or published ROA list).
5. Rolling per-peer baselines for withdrawal and update-rate anomalies.
6. Bogon and AS-path sanity checks.
7. When an alert fires, save the surrounding AS-path history for that prefix (raw events expire after 2h).
8. Alerts UI with prefix and ASN investigation pages; notifications (webhook, Slack, email).

## Phase 4: Explainer (about 2 weeks)

- BEAR-style analysis: AS paths before, during and after the event, structured prompts, majority vote over
  several runs, classify hijack vs leak.
- RAG over RFCs, BGP docs and public postmortems, with citations; pgvector in Postgres.
- Build an evaluation set from known historical incidents; measure accuracy and grounding. Compare with BEAR's
  reported numbers only after reading the paper (secondhand figures disagree).
- Label output as a suggestion; show sources.

## Phase 5: History layer (about 2-3 weeks)

- Hourly export of closed hours to Parquet (keep 24h locally as a buffer); idempotent file names. Land the
  files in S3, partitioned by date and hour, and register them in the Glue Data Catalog.
- Query the S3 history with Athena (pay per scan, so keep files compressed and partitioned). Add dbt-athena
  or run dbt on DuckDB over the same Parquet.
- Rework `spark/bgp_stream.py` into a real batch job over the exported Parquet (the current prototype only
  prints to the console).
- dbt project: sources with freshness, staging views, marts, tests. Portable SQL; run on DuckDB in CI.
- Orchestration: one hourly DAG in the order partitions, export, data-quality checks, dbt, Databricks trigger,
  then drop expired partitions. Airflow 3 with LocalExecutor, or cron on a small box (Airflow needs about
  2-3 GB).
- Databricks Free: upload via Files API, Auto Loader (`availableNow`) into bronze, silver and gold Delta tables.
  First confirm Free Edition gives you API tokens, and assume it cannot reach Kafka or Postgres (push-in only).
- Decide the "top flapping prefixes" gap: flapping per prefix is not in the rollups; compute it from raw events
  within retention or save it during export.

## Later

- Route-leak detection (CAIDA AS relationships), flap damping heuristics, sub-prefix hijacks, RIPEstat
  enrichment, multi-partition consumers, `pg_partman`, Kafka TLS and SASL.
- Compare detections against BGPalerter's as a benchmark.

## Open items

- Verify: Oracle free allowance, Databricks Free token support, student-pack credits, AWS credit terms and
  expiry, BEAR results.
- Skills coverage vs. data-engineering job postings: SQL, Python, Kafka, Spark, Airflow, dbt, Databricks, AWS,
  Terraform and Docker are covered by this plan. Snowflake, Azure and GCP are deliberately skipped; one cloud
  used well beats three used thinly.
- The README still describes only the v1 pipeline; update it as phases land.
- Late events: rollups key on `observed_at`, raw partitions on `inserted_at`.
