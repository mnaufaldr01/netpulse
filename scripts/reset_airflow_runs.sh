#!/usr/bin/env bash
# Clear all netpulse DAG runs from Airflow metadata DB (local dev reset)
set -euo pipefail

echo "Stopping scheduler..."
docker compose stop airflow-scheduler

echo "Deleting netpulse DAG runs and task instances..."
docker compose exec -T postgres psql -U netpulse -d netpulse -f - < scripts/reset_airflow_runs.sql

echo "Done. Restart scheduler and run backfill:"
echo "  docker compose start airflow-scheduler"
echo "  bash scripts/backfill_pipeline.sh 2025-05-25 2025-06-28"
