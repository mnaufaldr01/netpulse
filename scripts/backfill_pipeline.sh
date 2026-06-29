#!/usr/bin/env bash
# Wrapper for 35-day pipeline backfill (run from repo root with Docker Compose up)
set -euo pipefail

START_DATE="${1:-2025-05-25}"
END_DATE="${2:-2025-06-28}"
SERVICE="${AIRFLOW_SERVICE:-airflow-scheduler}"

# dbt and alerts rebuild from all staging data — run once, not per partition date
BACKFILL_DAGS=(netpulse_acquisition netpulse_staging)
ALL_DAGS=(netpulse_acquisition netpulse_staging netpulse_dbt netpulse_alerts)

wait_for_scheduler() {
  echo "Waiting for Airflow scheduler..."
  for _ in $(seq 1 30); do
    if docker compose exec "${SERVICE}" curl -sf http://localhost:8974/health > /dev/null 2>&1; then
      echo "Scheduler is healthy."
      return 0
    fi
    sleep 2
  done
  echo "Scheduler did not become healthy in time."
  exit 1
}

echo "Pausing DAGs before backfill..."
for dag in "${ALL_DAGS[@]}"; do
  docker compose exec "${SERVICE}" airflow dags pause "${dag}" || true
done

echo "Stopping scheduler and clearing existing netpulse DAG runs..."
docker compose stop airflow-scheduler
docker compose exec -T postgres psql -U netpulse -d netpulse -f - < scripts/reset_airflow_runs.sql

echo "Backfilling acquisition + staging: ${START_DATE} to ${END_DATE}"
docker compose start airflow-scheduler
wait_for_scheduler

for dag in "${BACKFILL_DAGS[@]}"; do
  echo "==> Backfilling ${dag}"
  docker compose exec "${SERVICE}" airflow dags backfill "${dag}" \
    -s "${START_DATE}" -e "${END_DATE}" -y --reset-dagruns
done

echo "==> Running dbt once (seed + run + test)"
docker compose exec "${SERVICE}" bash -c \
  "cd /opt/airflow/dbt && dbt seed --profiles-dir /opt/airflow/dbt && dbt run --profiles-dir /opt/airflow/dbt && dbt test --profiles-dir /opt/airflow/dbt"

echo "==> Running alerts once"
docker compose exec "${SERVICE}" airflow tasks test netpulse_alerts evaluate_hotspot_alerts 2025-06-28
docker compose exec "${SERVICE}" airflow tasks test netpulse_alerts evaluate_peak_hour_alerts 2025-06-28
docker compose exec "${SERVICE}" airflow tasks test netpulse_alerts evaluate_neighbour_alerts 2025-06-28
docker compose exec "${SERVICE}" airflow tasks test netpulse_alerts expire_resolved_alerts 2025-06-28

echo "Unpausing DAGs..."
for dag in "${ALL_DAGS[@]}"; do
  docker compose exec "${SERVICE}" airflow dags unpause "${dag}" || true
done

echo "Backfill complete."
