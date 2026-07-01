#!/usr/bin/env bash
# SSM port-forward helpers for Phase 2 (run from repo root with AWS CLI configured)
set -euo pipefail

REGION="${AWS_REGION:-ap-southeast-2}"
INSTANCE_ID="${1:-}"
RDS_HOST="${2:-}"
MODE="${3:-rds}"

usage() {
  cat <<EOF
Usage:
  bash scripts/ssm_port_forward.sh <ec2-instance-id> <rds-endpoint> [rds|airflow]

Modes:
  rds      Forward RDS PostgreSQL to localhost:15432 (default)
  airflow  Forward Airflow UI to localhost:8080

Examples:
  bash scripts/ssm_port_forward.sh i-0abc123 netpulse-postgres.xxx.ap-southeast-2.rds.amazonaws.com rds
  bash scripts/ssm_port_forward.sh i-0abc123 - airflow

Terraform outputs provide instance ID and RDS endpoint after apply.
EOF
}

if [ -z "$INSTANCE_ID" ] || { [ "$MODE" = "rds" ] && [ -z "$RDS_HOST" ]; }; then
  usage
  exit 1
fi

if [ "$MODE" = "airflow" ]; then
  echo "Forwarding Airflow UI: localhost:8080 -> EC2:8080"
  exec aws ssm start-session \
    --target "$INSTANCE_ID" \
    --region "$REGION" \
    --document-name AWS-StartPortForwardingSession \
    --parameters "portNumber=8080,localPortNumber=8080"
fi

echo "Forwarding RDS: localhost:15432 -> $RDS_HOST:5432 via $INSTANCE_ID"
exec aws ssm start-session \
  --target "$INSTANCE_ID" \
  --region "$REGION" \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters "host=$RDS_HOST,portNumber=5432,localPortNumber=15432"
