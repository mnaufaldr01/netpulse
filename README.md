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

6. Run pipeline backfill (after DAGs are enabled in Airflow UI at http://localhost:8080):
   ```bash
   docker compose exec airflow-webserver airflow dags backfill netpulse_acquisition -s 2025-05-25 -e 2025-06-28
   docker compose exec airflow-webserver airflow dags backfill netpulse_staging -s 2025-05-25 -e 2025-06-28
   docker compose exec airflow-webserver airflow dags backfill netpulse_dbt -s 2025-05-25 -e 2025-06-28
   docker compose exec airflow-webserver airflow dags backfill netpulse_alerts -s 2025-05-25 -e 2025-06-28
   ```

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
