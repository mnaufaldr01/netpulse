#!/bin/bash
# EC2 user-data bootstrap — rendered by Terraform templatefile()
set -euo pipefail
exec > /var/log/netpulse-bootstrap.log 2>&1

AWS_REGION="${aws_region}"
RDS_ENDPOINT="${rds_endpoint}"
S3_BUCKET="${s3_bucket}"
DB_NAME="${db_name}"
DB_USERNAME="${db_username}"
DB_PASSWORD_SSM="${db_password_ssm}"
PROJECT_ROOT="${project_root}"
GIT_REPO_URL="${git_repo_url}"

echo "=== netpulse EC2 bootstrap starting ==="

dnf update -y
dnf install -y docker git postgresql15 python3-pip
systemctl enable --now docker

mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL https://github.com/docker/compose/releases/download/v2.24.6/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

if [ -n "$GIT_REPO_URL" ] && [ ! -f "$PROJECT_ROOT/docker-compose.cloud.yml" ]; then
  echo "Cloning repository from $GIT_REPO_URL"
  git clone "$GIT_REPO_URL" "$PROJECT_ROOT" || echo "Clone failed — sync code manually via SSM"
fi

mkdir -p "$PROJECT_ROOT/data/boundaries" "$PROJECT_ROOT/data/opencellid"

echo "Fetching RDS password from SSM..."
DB_PASSWORD=$(aws ssm get-parameter \
  --name "$DB_PASSWORD_SSM" \
  --with-decryption \
  --query Parameter.Value \
  --output text \
  --region "$AWS_REGION")

pip3 install cryptography --quiet
FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

SQL_ALCHEMY_CONN="postgresql+psycopg2://${db_username}:$DB_PASSWORD@${rds_endpoint}:5432/${db_name}"

cat > "$PROJECT_ROOT/.env.cloud" <<EOF
POSTGRES_HOST=$RDS_ENDPOINT
POSTGRES_PORT=5432
POSTGRES_DB=$DB_NAME
POSTGRES_USER=$DB_USERNAME
POSTGRES_PASSWORD=$DB_PASSWORD
S3_BUCKET=$S3_BUCKET
AWS_DEFAULT_REGION=$AWS_REGION
TOWER_SAMPLE_SIZE=100
RANDOM_SEED=42
BACKFILL_DAYS=35
SUBSCRIBER_COUNT=50000
BOUNDARIES_DATA_PATH=$PROJECT_ROOT/data/boundaries
OPENCELLID_DATA_PATH=$PROJECT_ROOT/data/opencellid
# OPENCELLID_API_KEY=pk.xxx  # add your token here before running DAG 0 (do not commit)
AIRFLOW__CORE__LOAD_EXAMPLES=False
AIRFLOW__CORE__FERNET_KEY=$FERNET_KEY
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=$SQL_ALCHEMY_CONN
AIRFLOW_UID=50000
_AIRFLOW_WWW_USER_USERNAME=airflow
_AIRFLOW_WWW_USER_PASSWORD=airflow
EOF

chmod 600 "$PROJECT_ROOT/.env.cloud"

if [ -f "$PROJECT_ROOT/sql/init/01_schemas.sql" ]; then
  echo "Initializing RDS schema..."
  PGPASSWORD="$DB_PASSWORD" psql -h "$RDS_ENDPOINT" -U "$DB_USERNAME" -d "$DB_NAME" \
    -f "$PROJECT_ROOT/sql/init/01_schemas.sql"
  PGPASSWORD="$DB_PASSWORD" psql -h "$RDS_ENDPOINT" -U "$DB_USERNAME" -d "$DB_NAME" \
    -f "$PROJECT_ROOT/sql/init/02_grants.sql"
fi

if [ -f "$PROJECT_ROOT/scripts/download_boundaries.py" ]; then
  echo "Downloading province boundaries..."
  cd "$PROJECT_ROOT"
  pip3 install pydantic-settings python-dotenv shapely geopandas --quiet || true
  PYTHONPATH="$PROJECT_ROOT" python3 scripts/download_boundaries.py || true
fi

if [ -f "$PROJECT_ROOT/docker-compose.cloud.yml" ]; then
  echo "Starting Airflow (cloud compose)..."
  cd "$PROJECT_ROOT"
  docker compose -f docker-compose.cloud.yml --env-file .env.cloud up -d --build
fi

echo "=== netpulse EC2 bootstrap complete ==="
