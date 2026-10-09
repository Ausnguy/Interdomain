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

## Later

Add Kafka → Spark/Databricks → Delta Lake → dbt → Airflow → React only after V1 works.
