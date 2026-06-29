#!/usr/bin/env bash
# Wrapper for 35-day pipeline backfill (run from repo root with Docker Compose up)
set -euo pipefail

START_DATE="${1:-2025-05-25}"
END_DATE="${2:-2025-06-28}"
SERVICE="${AIRFLOW_SERVICE:-airflow-webserver}"

echo "Backfilling netpulse pipeline: ${START_DATE} to ${END_DATE}"

for dag in netpulse_acquisition netpulse_staging netpulse_dbt netpulse_alerts; do
  echo "==> Backfilling ${dag}"
  docker compose exec "${SERVICE}" airflow dags backfill "${dag}" -s "${START_DATE}" -e "${END_DATE}"
done

echo "Backfill complete."
