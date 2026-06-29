# netpulse

Telco network congestion hotspot intelligence pipeline — batch-oriented data engineering project with Airflow orchestration, a three-zone data lake, dbt marts, and a Streamlit dashboard.

See [PRD_netpulse.md](PRD_netpulse.md) for full product requirements.

## Phase 1: Local Development

### Prerequisites

- Docker Desktop
- Python 3.11+
- OpenCelliD Indonesia slice CSV (MCC 510) from [opencellid.org](https://opencellid.org)
- Simplified Indonesia province GeoJSON from [chmdznr/indonesia-geojson](https://github.com/chmdznr/indonesia-geojson)

Create and activate a virtual environment, then install dependencies:

```powershell
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-local.txt
pip install -e .
```

```bash
# macOS / Linux
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-local.txt
pip install -e .
```

### First-Run Setup

1. Copy environment file:
   ```bash
   cp .env.example .env
   ```

2. Place data files (not committed to git):
   - OpenCelliD CSV → `data/opencellid/` (e.g. `510.csv`)
   - Province GeoJSON → `data/boundaries/indonesia_provinces_simplified.geojson`
     ```bash
     python scripts/download_boundaries.py
     ```

3. Start local stack:
   ```bash
   docker compose up -d
   ```

4. Initialize MinIO bucket:
   ```bash
   python scripts/init_minio_buckets.py
   ```

5. Seed reference data (with venv activated):
   ```bash
   python scripts/seed_opencellid_local.py
   python scripts/seed_subscriber_master.py
   ```

   `.env.example` defaults to **portfolio demo** settings (`TOWER_SAMPLE_SIZE=100`, `SUBSCRIBER_COUNT=50000`). Re-seed after changing either value.

6. Run pipeline backfill (keep DAGs **paused** in the Airflow UI until backfill completes).

   Run from a **bash terminal** (Git Bash or WSL on Windows — not PowerShell):

   **Reset** (only if you see `RUNNING` conflicts from unpausing DAGs too early):
   ```bash
   bash scripts/reset_airflow_runs.sh
   ```

   **Backfill all DAGs** (recommended):

   Acquisition and staging backfill per day; **dbt and alerts run once** at the end (they rebuild from all staging data):

   ```bash
   bash scripts/backfill_pipeline.sh 2025-05-25 2025-06-28
   ```

   If acquisition + staging already finished and only dbt failed, run these manually:

   ```bash
   docker compose exec airflow-webserver bash -c "cd /opt/airflow/dbt && dbt seed --profiles-dir /opt/airflow/dbt && dbt run --profiles-dir /opt/airflow/dbt && dbt test --profiles-dir /opt/airflow/dbt"
   docker compose exec airflow-webserver airflow tasks test netpulse_alerts evaluate_hotspot_alerts 2025-06-28
   docker compose exec airflow-webserver airflow tasks test netpulse_alerts evaluate_peak_hour_alerts 2025-06-28
   docker compose exec airflow-webserver airflow tasks test netpulse_alerts evaluate_neighbour_alerts 2025-06-28
   docker compose exec airflow-webserver airflow tasks test netpulse_alerts expire_resolved_alerts 2025-06-28
   ```

   **Or backfill acquisition + staging only**, then dbt/alerts manually:
   ```bash
   docker compose exec airflow-webserver airflow dags backfill netpulse_acquisition -s 2025-05-25 -e 2025-06-28 -y
   docker compose exec airflow-webserver airflow dags backfill netpulse_staging -s 2025-05-25 -e 2025-06-28 -y
   # then dbt + alerts once (see commands above)
   ```

   DAGs use `catchup=False` — historical data is loaded via explicit backfill only, not the scheduler.

7. Run dashboard (on host):
   ```bash
   pip install -e .
   streamlit run dashboard/app.py
   ```

### Local Services

| Service    | URL                          |
|------------|------------------------------|
| Airflow UI | http://localhost:8080        |
| MinIO API  | http://localhost:9000        |
| MinIO Console | http://localhost:9001     |
| PostgreSQL | localhost:5433               |

Default Airflow credentials: `airflow` / `airflow`

## Scale assumptions

Portfolio demo settings (`.env.example`): **100 real towers**, **50,000 subscribers**, **35-day backfill**.

| Metric | Demo value | Notes |
|--------|------------|--------|
| Tower telemetry rows / day | 2,400 | 100 towers × 24 hourly readings |
| Subscriber session rows / day | 150,000 | 50,000 subscribers × 3 sessions |
| Total raw events / day | ~152,000 | Matches resume / PRD narrative |
| 35-day backfill volume | ~5.3M rows | Acquisition + staging per day; dbt/alerts once at end |
| Typical backfill time (local) | ~45–90 min | Docker Desktop, demo settings; varies by machine |
| CI / unit tests | Minimal fixture | [`tests/fixtures/seed_ci.sql`](tests/fixtures/seed_ci.sql) — 3 towers, 2 subscribers |

**Production path (not implemented — documented for scope):** Spark/EMR for large staging transforms, CeleryExecutor for horizontal Airflow workers, incremental dbt models, Postgres table partitioning, and right-sized RDS. See [PRD §13 Limitations](PRD_netpulse.md) and [PHASE2_CLOUD_DEPLOYMENT.md](PHASE2_CLOUD_DEPLOYMENT.md).

To stress-test locally, raise `SUBSCRIBER_COUNT` or set `TOWER_SAMPLE_SIZE=0` (full OpenCelliD slice). Generators are vectorized, but staging Postgres loads and dbt runtime still grow quickly — not recommended for portfolio demos.

## Testing

Install dev dependencies:

```powershell
pip install -r requirements-dev.txt
```

**Unit tests** (no external services):

```powershell
pytest -m "not integration"
```

**Integration tests** (requires Postgres and MinIO):

```powershell
docker compose up -d postgres minio
pytest -m integration
```

Local integration uses port **5433** from `.env`; CI uses **5432** on service containers.

**dbt tests** (requires Postgres with seed data):

```powershell
docker compose up -d postgres
psql -h localhost -p 5433 -U netpulse -d netpulse -f sql/init/01_schemas.sql
psql -h localhost -p 5433 -U netpulse -d netpulse -f sql/init/02_grants.sql
psql -h localhost -p 5433 -U netpulse -d netpulse -f tests/fixtures/seed_ci.sql
cd dbt
dbt seed --profiles-dir .
dbt run --profiles-dir .
dbt test --profiles-dir .
```

CI runs unit, integration, and dbt jobs in parallel via [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## Phase 2: Cloud Deployment

See [PHASE2_CLOUD_DEPLOYMENT.md](PHASE2_CLOUD_DEPLOYMENT.md).

## Project Structure

```
netpulse/          # Shared Python package (config, db, storage, geo)
dags/              # Airflow DAGs
generators/        # Synthetic data generators
transforms/        # Staging clean transforms
dbt/               # dbt models, seeds, tests
dashboard/         # Streamlit app
scripts/           # Local seed and init scripts
sql/init/          # PostgreSQL bootstrap schemas
terraform/         # AWS IaC (Phase 2)
```
