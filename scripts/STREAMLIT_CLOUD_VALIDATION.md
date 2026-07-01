# Streamlit cloud validation (manual checklist)

Run after cloud backfill completes and RDS tunnel is active.

## 1. Start RDS tunnel

```powershell
bash scripts/ssm_port_forward.sh <ec2-instance-id> <rds-endpoint> rds
```

## 2. Configure local env

Copy `.env.cloud.example` to `.env.cloud` and set:

```dotenv
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=15432
POSTGRES_PASSWORD=<from SSM /netpulse/db_password>
```

Ensure province GeoJSON exists locally:

```powershell
python scripts/download_boundaries.py
```

## 3. Launch dashboard

```powershell
$env:DOTENV_PATH=".env.cloud"   # optional if you symlink or copy to .env
streamlit run dashboard/app.py
```

Or load `.env.cloud` by copying to `.env` temporarily.

## 4. Pages to verify

- Network Health Map — province choropleth + tower markers
- Hotspot Leaderboard — tower and province tabs
- Province Drilldown — map click + tower details
- Tower Drilldown — PRB chart + peak-hour heatmap (7 days)
- Active Alerts — KPI row + filterable table

## 5. Screenshots for README

Capture each page with live RDS data before `terraform destroy`.
