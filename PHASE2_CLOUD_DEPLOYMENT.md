# Phase 2: Cloud Deployment — Todo List

**Goal:** Validate the full netpulse pipeline on real AWS infrastructure, then tear down compute resources to minimize cost.

**Prerequisites:** Phase 1 complete — local pipeline end-to-end validated (DAGs 1–4, all dbt marts, alerts, Streamlit dashboard).

**Reference:** [PRD_netpulse.md](PRD_netpulse.md) — Sections 6.2 (DAG 0), 8 (Terraform), 11 (Stage 2), 12 (Week 2 Days 10–12)

**Estimated session:** Under 3 hours active work; total AWS cost well under $1 if destroyed promptly.

---

## Pre-Flight Checklist

- [ ] Phase 1 pipeline passes end-to-end locally (35-day backfill, dbt tests green, dashboard renders)
- [ ] AWS account with billing alerts configured
- [ ] AWS CLI configured locally (`aws sts get-caller-identity` succeeds)
- [ ] Terraform >= 1.5 installed
- [ ] OpenCelliD account registered; API key obtained from opencellid.org
- [ ] Phase 1 `.env` backed up; cloud `.env` will be a separate file (e.g. `.env.cloud`)

---

## 1. Terraform Infrastructure

All HCL files live in [`terraform/`](terraform/) per PRD Section 8.3.

### 1.1 Core Terraform Files

- [ ] `terraform/main.tf` — provider config, AWS region, optional S3 remote state backend
- [ ] `terraform/variables.tf` — region, CIDRs, instance types, DB config, tags
- [ ] `terraform/outputs.tf` — RDS endpoint, S3 bucket name, VPC ID, EC2 instance ID
- [ ] `terraform/vpc.tf` — VPC, public/private subnets, IGW, NAT Gateway, route tables, **S3 VPC Gateway Endpoint**
- [ ] `terraform/security_groups.tf` — `airflow_sg` (no inbound from internet), `rds_sg` (5432 from airflow_sg only)
- [ ] `terraform/s3.tf` — bucket, versioning, 90-day lifecycle to S3-IA for raw/staging, VPC-endpoint-only bucket policy
- [ ] `terraform/rds.tf` — PostgreSQL 15 (`db.t3.micro`, 20 GB gp2), subnet group spanning two private AZs
- [ ] `terraform/ec2.tf` — `t3.small` Airflow host in private subnet, Amazon Linux 2, instance profile
- [ ] `terraform/iam.tf` — Airflow role + policies: S3 read/write (scoped to lake bucket), RDS connect, SSM Session Manager, SSM parameter read

### 1.2 Network Architecture Validation

- [ ] VPC CIDR `10.0.0.0/16` with public subnet (`10.0.1.0/24`) for NAT only
- [ ] Private subnets `10.0.2.0/24` (EC2) and `10.0.3.0/24` (RDS subnet group)
- [ ] NAT Gateway in public subnet; private route table default route → NAT
- [ ] S3 Gateway Endpoint attached to private route table (S3 traffic bypasses NAT)
- [ ] EC2 reachable only via **SSM Session Manager** (no SSH port 22, no bastion)

### 1.3 S3 Data Lake

- [ ] Bucket name output (e.g. `netpulse-lake-<suffix>`) matches `S3_BUCKET` in cloud `.env`
- [ ] Zone prefixes created: `raw/`, `staging/`, `curated/` (or created on first pipeline run)
- [ ] Bucket versioning enabled
- [ ] Lifecycle rule: raw + staging → S3-IA after 90 days
- [ ] `lifecycle { prevent_destroy = true }` on S3 bucket so data survives `terraform destroy`

### 1.4 RDS PostgreSQL

- [ ] PostgreSQL 15 instance in private subnet
- [ ] Security group allows 5432 inbound from Airflow EC2 security group only
- [ ] DB password stored in SSM Parameter Store (`aws_ssm_parameter.db_password`), not in Terraform plaintext
- [ ] Run [`sql/init/01_schemas.sql`](sql/init/01_schemas.sql) against RDS (same schema as local)

### 1.5 Apply & Verify

- [ ] `terraform init`
- [ ] `terraform plan` — review all resources and estimated cost
- [ ] `terraform apply`
- [ ] Capture outputs: RDS endpoint, S3 bucket, EC2 instance ID, VPC ID
- [ ] Confirm EC2 accessible via `aws ssm start-session --target <instance-id>`
- [ ] Confirm RDS **not** publicly accessible

---

## 2. Secrets & Environment Configuration

- [ ] Store RDS password in SSM: `/netpulse/db_password` (SecureString)
- [ ] Store OpenCelliD API key in SSM: `/netpulse/opencellid_api_key` (SecureString)
- [ ] Create `.env.cloud` (gitignored) with cloud values:
  - [ ] `POSTGRES_HOST=<rds-endpoint>`
  - [ ] `POSTGRES_PORT=5432`
  - [ ] `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` (from SSM at runtime, not committed)
  - [ ] `S3_BUCKET=<terraform-output>`
  - [ ] `S3_ENDPOINT_URL=` **unset** (boto3 uses real AWS S3)
  - [ ] `AWS_DEFAULT_REGION=<region>`
  - [ ] Remove MinIO-specific vars
- [ ] Verify [`netpulse/config.py`](netpulse/config.py) reads cloud env without code changes
- [ ] IAM role on EC2 grants SSM parameter read for DB password and OpenCelliD key

---

## 3. Airflow on EC2

### 3.1 EC2 Bootstrap

- [ ] Install Docker / Airflow (or use user-data script in `ec2.tf` to automate)
- [ ] Clone or sync netpulse repo to EC2 (private subnet — outbound via NAT)
- [ ] Install Python dependencies from [`requirements.txt`](requirements.txt)
- [ ] Copy DAGs, `netpulse/`, generators, transforms, dbt project to Airflow paths
- [ ] Configure Airflow connection: PostgreSQL → RDS
- [ ] Configure Airflow Variables/connections for S3 (uses instance IAM role, no static keys)
- [ ] Start Airflow scheduler + webserver (or Docker Compose adapted for EC2)
- [ ] Access Airflow UI via SSM port forwarding (no public IP on EC2)

### 3.2 Province Boundary Data on EC2

- [ ] Download simplified Indonesia province GeoJSON to EC2 filesystem (e.g. `/opt/netpulse/data/boundaries/`)
- [ ] Used by DAG 0 seed tasks and Streamlit dashboard at runtime
- [ ] Not stored in S3 or PostgreSQL (PRD Section 5.3)

---

## 4. DAG 0 — Tower Seeding (Cloud Only)

Implement [`dags/netpulse_seed_towers.py`](dags/netpulse_seed_towers.py) per PRD Section 6.2.

- [ ] `fetch_opencellid_indonesia` — call OpenCelliD download API with key from SSM; write raw CSV to `s3://<bucket>/raw/opencellid/YYYY/MM/DD/`
- [ ] `sample_towers` — reuse sampling logic from [`scripts/seed_opencellid_local.py`](scripts/seed_opencellid_local.py) / [`netpulse/geo.py`](netpulse/geo.py): MCC 510, 100 towers, deterministic seed, MNC diversity
- [ ] `load_tower_master` — upsert into RDS `tower_master` and `province_master`
- [ ] `validate_tower_master` — assert row count = 100, lat/long non-null, cell types assigned
- [ ] Schedule: manual trigger (initial) + `@monthly` (refresh)
- [ ] Trigger DAG 0 manually for initial seed
- [ ] Verify 100 towers in RDS with real OpenCelliD coordinates and province assignments

---

## 5. Pipeline Migration (DAGs 1–4)

No code changes expected — only `.env` swap per PRD Section 11.

### 5.1 Environment Swap

- [ ] Point all pipeline components at RDS + real S3 (unset `S3_ENDPOINT_URL`)
- [ ] Confirm boto3 on EC2 uses instance IAM role (no hardcoded AWS keys)
- [ ] Run smoke test: single-day DAG 1 manual trigger → verify Parquet in S3 raw zone

### 5.2 Subscriber Master Seed on Cloud

- [ ] Run `seed_subscriber_master.py` against RDS (one-time, 50,000 subscribers)
- [ ] Or add one-time task to DAG 0 / separate init script on EC2

### 5.3 35-Day Backfill

Use [`scripts/backfill_pipeline_cloud.sh`](scripts/backfill_pipeline_cloud.sh) on EC2 (same pattern as local):

- [ ] `netpulse_acquisition` + `netpulse_staging` backfill per day (`2025-05-25` → `2025-06-28`)
- [ ] **dbt + alerts run once** at the end (not per-day backfill)
- [ ] `bash scripts/backfill_pipeline_cloud.sh 2025-05-25 2025-06-28`
- [ ] `bash scripts/validate_cloud_pipeline.sh` with RDS credentials

### 5.4 Data Validation

- [ ] All 7 dbt marts populated in RDS:
  - [ ] `mart_congestion_events`
  - [ ] `mart_hotspot_summary`
  - [ ] `mart_peak_hour_patterns`
  - [ ] `mart_neighbour_impact`
  - [ ] `mart_subscriber_impact`
  - [ ] `mart_network_health_snapshot`
  - [ ] `mart_province_summary`
- [ ] `dbt test` passes against RDS
- [ ] `alerts` table has ACTIVE records from alert DAG
- [ ] Row counts within expected ranges (~2,400 telemetry rows/day, ~150,000 session rows/day)

---

## 6. Streamlit Dashboard (Cloud)

See [scripts/STREAMLIT_CLOUD_VALIDATION.md](scripts/STREAMLIT_CLOUD_VALIDATION.md).

- [ ] SSM tunnel RDS to `localhost:15432`
- [ ] `.env.cloud` with tunnel host/port
- [ ] Run `streamlit run dashboard/app.py` against RDS
- [ ] **Page 1:** Network Health Map
- [ ] **Page 2:** Hotspot Leaderboard
- [ ] **Page 3:** Province Drilldown
- [ ] **Page 4:** Tower Drilldown
- [ ] **Page 5:** Active Alerts
- [ ] Screenshot all pages for README

---

## 7. Documentation & Evidence

- [ ] Architecture diagram: VPC, subnets, NAT GW, S3 endpoint, EC2, RDS (Mermaid or draw.io)
- [ ] README **Cloud Deployment** section:
  - [ ] Prerequisites (AWS CLI, Terraform, OpenCelliD API key)
  - [ ] Step-by-step: `terraform apply` → SSM secrets → DAG 0 → backfill → dashboard
  - [ ] SSM Session Manager access to Airflow EC2
  - [ ] Cost profile and destroy instructions
- [ ] README **Spark/EMR Scale-Up** section (PRD Section 6.3 — documentation only, not implemented)
- [ ] Screenshot: Airflow DAG graph (all 5 DAGs)
- [ ] Screenshot: successful pipeline run / backfill completion
- [ ] Screenshot: dashboard pages with live RDS data
- [ ] Document limitations (PRD Section 13) in README

---

## 8. Teardown & Cost Control

- [ ] Confirm S3 bucket has `prevent_destroy` — data persists after destroy
- [ ] `terraform destroy` — removes EC2, RDS, NAT Gateway, VPC (compute + networking)
- [ ] Verify no orphaned NAT Gateway or Elastic IP charges
- [ ] S3 bucket and data remain for optional re-run without re-backfill
- [ ] Document re-deploy workflow: `terraform apply` → restore from existing S3 raw/staging if desired

---

## 9. Optional Hardening (Out of PRD Scope — Skip Unless Needed)

- [ ] Terraform remote state in S3 + DynamoDB lock table
- [ ] CloudWatch alarms on EC2/RDS
- [ ] Airflow email/Slack on DAG failure
- [ ] Multi-environment Terraform workspaces

---

## Suggested Execution Order (Week 2, Days 10–12)

| Day | Focus | Key todos |
|-----|-------|-----------|
| **Day 10** | Terraform | Sections 1 + 2 — write HCL, apply, bootstrap EC2 |
| **Day 11** | Pipeline on AWS | Sections 3 + 4 + 5 — DAG 0, env swap, 35-day backfill, validate marts |
| **Day 12** | Dashboard + docs + destroy | Sections 6 + 7 + 8 — Streamlit against RDS, README, screenshots, teardown |

---

## Exit Criteria (Phase 2 Complete)

- [ ] All AWS resources provisioned via Terraform (custom VPC, private subnets, NAT, S3 endpoint)
- [ ] DAG 0 seeded 100 real towers into RDS from OpenCelliD API
- [ ] Full 35-day backfill completed on AWS; all marts and alerts populated
- [ ] Streamlit dashboard validated against RDS with screenshots captured
- [ ] README cloud deployment guide and architecture diagram published
- [ ] `terraform destroy` executed; S3 lake data retained
- [ ] Total session cost documented and under $1 target
