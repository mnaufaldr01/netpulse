#!/usr/bin/env bash
# 35-day pipeline backfill on EC2 (run via SSM on the Airflow host)
set -euo pipefail

START_DATE="${1:-2025-05-25}"
END_DATE="${2:-2025-06-28}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.cloud.yml}"
ENV_FILE="${ENV_FILE:-.env.cloud}"
SERVICE="${AIRFLOW_SERVICE:-airflow-scheduler}"
PROJECT_ROOT="${PROJECT_ROOT:-/opt/netpulse}"

cd "$PROJECT_ROOT"

BACKFILL_DAGS=(netpulse_acquisition netpulse_staging)
ALL_DAGS=(netpulse_acquisition netpulse_staging netpulse_dbt netpulse_alerts netpulse_seed_towers)

wait_for_scheduler() {
  echo "Waiting for Airflow scheduler..."
  for _ in $(seq 1 30); do
    if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec "$SERVICE" \
      curl -sf http://localhost:8974/health > /dev/null 2>&1; then
      echo "Scheduler is healthy."
      return 0
    fi
    sleep 2
  done
  echo "Scheduler did not become healthy in time."
  exit 1
}

dc() {
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec "$SERVICE" "$@"
}

echo "Pausing DAGs before backfill..."
for dag in "${ALL_DAGS[@]}"; do
  dc airflow dags pause "$dag" || true
done

echo "Backfilling acquisition + staging: ${START_DATE} to ${END_DATE}"
wait_for_scheduler

for dag in "${BACKFILL_DAGS[@]}"; do
  echo "==> Backfilling ${dag}"
  dc airflow dags backfill "$dag" -s "$START_DATE" -e "$END_DATE" -y --reset-dagruns
done

echo "==> Running dbt once (seed + run + test)"
dc bash -c "cd /opt/airflow/dbt && dbt seed --profiles-dir /opt/airflow/dbt && dbt run --profiles-dir /opt/airflow/dbt && dbt test --profiles-dir /opt/airflow/dbt"

echo "==> Running alerts once"
dc airflow tasks test netpulse_alerts evaluate_hotspot_alerts 2025-06-28
dc airflow tasks test netpulse_alerts evaluate_peak_hour_alerts 2025-06-28
dc airflow tasks test netpulse_alerts evaluate_neighbour_alerts 2025-06-28
dc airflow tasks test netpulse_alerts expire_resolved_alerts 2025-06-28

echo "Unpausing DAGs..."
for dag in "${ALL_DAGS[@]}"; do
  dc airflow dags unpause "$dag" || true
done

echo "Cloud backfill complete."
