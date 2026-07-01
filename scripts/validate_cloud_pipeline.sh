#!/usr/bin/env bash
# Validate RDS marts and alerts after cloud backfill (run with SSM RDS tunnel or on EC2)
set -euo pipefail

HOST="${POSTGRES_HOST:-127.0.0.1}"
PORT="${POSTGRES_PORT:-15432}"
DB="${POSTGRES_DB:-netpulse}"
USER="${POSTGRES_USER:-netpulse}"
export PGPASSWORD="${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD}"

PSQL="psql -h $HOST -p $PORT -U $USER -d $DB -t -A"

echo "=== Tower master ==="
$PSQL -c "SELECT COUNT(*) FROM tower_master;"

echo "=== Subscriber master ==="
$PSQL -c "SELECT COUNT(*) FROM subscriber_master;"

MARTS=(
  mart_congestion_events
  mart_hotspot_summary
  mart_peak_hour_patterns
  mart_neighbour_impact
  mart_subscriber_impact
  mart_network_health_snapshot
  mart_province_summary
)

echo "=== dbt marts ==="
for mart in "${MARTS[@]}"; do
  count=$($PSQL -c "SELECT COUNT(*) FROM public_marts.$mart;")
  echo "  $mart: $count rows"
done

echo "=== Active alerts ==="
$PSQL -c "SELECT COUNT(*) FROM alerts WHERE status = 'ACTIVE';"

echo "=== Sample telemetry day volume ==="
$PSQL -c "
  SELECT partition_date, COUNT(*)
  FROM public_staging.stg_tower_telemetry
  GROUP BY 1
  ORDER BY 1
  LIMIT 5;
"

echo "Validation queries complete."
