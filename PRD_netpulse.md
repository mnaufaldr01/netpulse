# PRD: netpulse
### Telco Network Congestion Hotspot Intelligence Pipeline

**Author:** Muhammad Naufal Dzakki Rauf
**Target completion:** 2 weeks
**Status:** Final

---

## 1. Background & Motivation

Cell towers have a finite radio capacity. When too many subscribers connect simultaneously, the network degrades — calls drop, data speeds slow, latency spikes. Telco network operations teams currently identify congestion reactively: they find out a tower is struggling after subscribers complain, not before.

`netpulse` builds the proactive intelligence layer. It is a batch-oriented data pipeline that ingests hourly tower telemetry and subscriber session data, identifies congestion events and chronic hotspot patterns, and surfaces operational insights to network planning teams through an automated alert system and an interactive monitoring dashboard.

The project is directly inspired by real telco use cases shared by practitioners in the industry, specifically: network congestion hotspot identification and cell site coverage and capacity intelligence. Tower reference data (location, cell type, radio type) is sourced from OpenCelliD — the world's largest open cell tower database — scoped to Indonesia (MCC 510), grounding the project in real network geography.

---

## 2. Problem Statement

**Operational problem:** Network operations teams lack an automated, reliable pipeline that translates raw tower telemetry into congestion intelligence — identifying which towers are chronically overloaded, at what times, and how many subscribers are affected. This intelligence is currently produced manually and inconsistently, if at all.

**Portfolio problem:** Existing projects demonstrate event-driven architecture (capstone) and lambda architecture with ML (fraud detection). `netpulse` fills a deliberate gap: batch orchestration depth, data lake zone management, real external data ingestion, and cloud infrastructure provisioning — skills directly relevant to DE roles in telco and financial services.

---

## 3. Goals

- Build a fully Airflow-orchestrated batch pipeline covering tower reference seeding, daily data acquisition, staging transforms, dbt mart runs, and automated alerting across five distinct DAGs
- Ingest real tower reference data from OpenCelliD (Indonesia slice, MCC 510) as the geographic foundation for all synthetic telemetry generation
- Implement a three-zone S3 data lake (raw / staging / curated) with explicit zone semantics
- Model congestion intelligence through dbt marts covering hotspot identification, peak hour patterns, neighbour impact, and subscriber impact
- Use a configurable `tower_thresholds` dbt seed table for per-tower-type congestion thresholds (not hardcoded)
- Write congestion alerts to a PostgreSQL alerts table, consumable by the dashboard
- Provision all AWS infrastructure via Terraform with a custom VPC, private subnets, NAT Gateway, and S3 VPC Gateway Endpoint
- Surface insights through a Streamlit dashboard with a pydeck tower map, hotspot leaderboard, tower drilldown, and active alerts panel
- Develop in two stages: local (Docker Compose + MinIO) then cloud (AWS)
- Document Apache Spark on EMR as the designated scale-up path for production-volume telemetry

---

## 4. Non-Goals

- Real-time or streaming ingestion — this is batch-first by design
- Apache Spark implementation — cost prohibitive for portfolio; documented as scale-up path
- Multi-environment Terraform workspaces — single environment, `terraform destroy` after testing
- ML-based anomaly detection — threshold-based congestion flagging is sufficient; DS layer is out of scope
- Authentication or multi-user access on the dashboard
- Real tower telemetry — hourly PRB, latency, and session data is synthetically generated against real tower IDs from OpenCelliD

---

## 5. Data Model & Sources

### 5.1 Data Sources Overview

`netpulse` combines one real external dataset with synthetically generated operational data:

| Source | Type | Description | Cadence |
|--------|------|-------------|---------|
| OpenCelliD Indonesia (MCC 510) | Real, external | Tower ID, lat/long, radio type (GSM/LTE/UMTS/NR), MNC — scoped to 100 towers sampled from Indonesian operators | One-time seed; refreshable via cloud DAG |
| Indonesia Province Boundaries (chmdznr/indonesia-geojson) | Real, external | GeoJSON polygon boundaries for all 38 Indonesian provinces (2022/2023 boundaries). Used for point-in-polygon province assignment during tower seeding and as pydeck GeoJsonLayer overlay. | One-time download; static |
| Tower Telemetry | Synthetic | Hourly per-tower metrics generated against real OpenCelliD tower IDs: PRB utilization, throughput, latency, dropped call rate, handover count, connected subscriber count | 100 towers × 24h = 2,400 rows/day |
| Subscriber Sessions | Synthetic | Per-subscriber session records: tower connected to, session duration, service type (voice/data/SMS), bytes transferred | ~50,000 subscribers × ~3 sessions/day = ~150,000 rows/day |
| Tower Thresholds | Config (dbt seed) | Per-cell-type congestion thresholds: PRB warn %, PRB critical %, latency warn ms, dropped call warn % | Static; manually updated |
| Subscriber Master | Synthetic seed | Subscriber ID, plan tier, home region | One-time seed |

### 5.2 OpenCelliD Integration

OpenCelliD is the world's largest open database of cell tower locations, licensed under Creative Commons Attribution-ShareAlike 4.0. It provides real tower IDs, coordinates, radio types, and operator metadata for Indonesia.

**Why this matters for the project:**
- The pydeck tower map renders real geographic coordinates — towers appear where Indonesian cell sites actually exist
- Synthetic telemetry is generated anchored to real tower IDs, making congestion patterns geographically plausible
- The pipeline has a genuine external data dependency managed by Airflow — closer to production than a fully synthetic setup

**Raw column schema (from OpenCelliD CSV):**

| Column | Type | Description | Used in netpulse |
|--------|------|-------------|-----------------|
| `radio` | string | Network type: GSM, UMTS, LTE, or CDMA | Yes — maps to `radio_type` in tower master; drives cell type classification |
| `mcc` | integer | Mobile Country Code (510 for Indonesia) | Yes — filter criterion for Indonesia slice |
| `net` | integer | Mobile Network Code (MNC) for GSM/UMTS/LTE; SID for CDMA | Yes — maps to `operator_mnc`; used in sampling to ensure operator diversity |
| `area` | integer | LAC (GSM/UMTS), TAC (LTE), or NID (CDMA) | Yes — part of composite tower key |
| `cell` | integer | Cell ID (GSM/LTE), UTRAN Cell ID (UMTS), or BID (CDMA) | Yes — part of composite tower key |
| `unit` | integer | PSC (UMTS) or PCI (LTE); empty for GSM/CDMA | No — not needed for this project |
| `lon` | double | Longitude (-180.0 to 180.0) | Yes — pydeck map rendering |
| `lat` | double | Latitude (-90.0 to 90.0) | Yes — pydeck map rendering, haversine neighbour detection |
| `range` | integer | Estimated cell range in metres | Yes — used in cell type classification heuristic (see below) |
| `samples` | integer | Number of measurements used to position the tower | Yes — quality filter: exclude towers with samples < 2 |
| `changeable` | integer | 0 = exact GPS position; 1 = averaged from measurements | Yes — quality flag stored in tower master |
| `created` | integer | Unix timestamp of first observation | No |
| `updated` | integer | Unix timestamp of last observation | Yes — used to prefer recently active towers in sampling |
| `averageSignal` | integer | Average signal strength in dBm | No |

**Composite tower key:** OpenCelliD does not have a single unique tower ID column. The natural key is the combination of `(radio, mcc, net, area, cell)`. The seed script generates a synthetic `tower_id` as a stable hash of this composite key (e.g. `SHA256(radio|mcc|net|area|cell)[:12]`) for use as the primary key throughout the pipeline.

**Sampling strategy (100 towers from Indonesia slice):**
- Filter: `mcc = 510`, `samples >= 2`, `lat` and `lon` non-null
- Prefer recently updated towers: sort by `updated` descending
- Sample across radio types (LTE, UMTS, GSM) and major Indonesian MNCs (Telkomsel MNC 01/08, Indosat MNC 01/21, XL Axiata MNC 11) to ensure operator and technology diversity
- Sampling is deterministic (fixed random seed) so the 100-tower set is reproducible across local and cloud environments

**Cell type classification heuristic:**
Cell type (urban/suburban/rural) is not directly available in OpenCelliD. It is inferred during seeding using two signals:

- **Radio type:** LTE and NR towers are predominantly urban/suburban; GSM towers are more likely rural — but this is not absolute
- **Range estimate:** OpenCelliD's `range` field gives an estimated coverage radius in metres. Small range (< 1 km) indicates a dense urban micro-cell; large range (> 5 km) indicates a rural macro-cell

Classification rules applied in `seed_opencellid_local.py` and DAG 0:

| Condition | Assigned Cell Type |
|-----------|-------------------|
| `range` < 1,000m | Urban |
| `range` between 1,000m and 5,000m | Suburban |
| `range` > 5,000m | Rural |
| `range` is null or 0 | Default to Suburban |

This classification is a documented heuristic, not ground truth — acknowledged explicitly in Section 13 (Limitations).

**tower_master table schema (in PostgreSQL):**

```sql
CREATE TABLE tower_master (
    tower_id        VARCHAR PRIMARY KEY,   -- SHA256 hash of composite key, first 12 chars
    radio           VARCHAR NOT NULL,      -- GSM | UMTS | LTE | CDMA
    mcc             INTEGER NOT NULL,      -- 510 for Indonesia
    mnc             INTEGER NOT NULL,      -- operator MNC
    area            INTEGER NOT NULL,      -- LAC / TAC / NID
    cell            INTEGER NOT NULL,      -- Cell ID
    lon             DOUBLE PRECISION NOT NULL,
    lat             DOUBLE PRECISION NOT NULL,
    range_m         INTEGER,               -- estimated coverage radius in metres
    samples         INTEGER,               -- measurement count from OpenCelliD
    changeable      INTEGER,               -- 0 = exact position, 1 = averaged
    cell_type       VARCHAR NOT NULL,      -- urban | suburban | rural (derived from range_m)
    province_name   VARCHAR,               -- assigned via point-in-polygon against province GeoJSON
    island_group    VARCHAR,               -- Jawa | Sumatera | Kalimantan | Sulawesi | etc (derived)
    last_updated    TIMESTAMP,             -- from OpenCelliD `updated` unix timestamp
    seeded_at       TIMESTAMP DEFAULT NOW()
);
```

**Data handling discipline:**
- Raw OpenCelliD CSV files are **never committed to the repository**
- A `/data/` directory at the repo root is gitignored — all locally downloaded data lives here
- The repository contains only code and a clear README instruction for first-time setup

**Local dev vs cloud seeding:**

| Stage | How tower data is loaded |
|-------|--------------------------|
| Local (Stage 1) | Developer downloads Indonesia slice manually from opencellid.org (free with account registration), places in `/data/opencellid/`. Script `scripts/seed_opencellid_local.py` reads from this path, applies filtering, sampling, and classification, loads into local PostgreSQL `tower_master` table. |
| Cloud (Stage 2) | DAG 0 (`netpulse_seed_towers`) fetches latest Indonesia slice from OpenCelliD download API (API key from SSM), lands raw CSV in S3, applies same filtering/sampling/classification logic, upserts into RDS `tower_master`. Serves as the periodic 18-month refresh mechanism. |

### 5.3 Indonesia Province Boundary Data

Province boundary data is sourced from `chmdznr/indonesia-geojson` on GitHub — the most current openly available GeoJSON for Indonesian administrative boundaries, covering all 38 provinces as of the 2022/2023 administrative reorganisation (which added 4 new provinces from West Papua splits, bringing the total from 34 to 38).

**Source:** `https://github.com/chmdznr/indonesia-geojson`
**License:** Open (verify in repo before use)
**Format:** GeoJSON, WGS84 projection (EPSG:4326) — compatible with pydeck and shapely out of the box

**Two variants available:**
- Full geometry — complete polygon detail, larger file size
- Simplified geometry — reduced vertex count, smaller file size, recommended for pydeck rendering

**Use in netpulse:** the **simplified variant** is used everywhere to avoid rendering lag on the dashboard map.

**How it is used:**

| Usage | Where | Detail |
|-------|-------|--------|
| Point-in-polygon province assignment | `scripts/seed_opencellid_local.py` and DAG 0 | During tower seeding, `shapely` checks each tower's lat/long against province polygons to assign `province_name` to `tower_master`. This is a one-time operation at seed time — not repeated per pipeline run. |
| Province-level mart aggregation | `mart_province_summary` (dbt) | Joins `tower_master.province_name` into mart aggregations to produce province-level congestion summaries |
| pydeck GeoJsonLayer overlay | Streamlit dashboard (Page 1) | GeoJSON file loaded at dashboard runtime directly into pydeck — no database storage of geometry needed. Province polygons render as a boundary layer beneath the tower ScatterplotLayer, colour-filled by province congestion severity. |

**Data handling:**
- The GeoJSON file is **not committed to the repository** — stored in `/data/boundaries/`, which is gitignored
- Downloaded once during local setup; no refresh needed (administrative boundaries change rarely)
- In the cloud deployment, the file is downloaded at EC2 setup time and placed on the Airflow host filesystem for use by both the seed DAG and Streamlit

**`province_master` reference table (in PostgreSQL):**

```sql
CREATE TABLE province_master (
    province_id     SERIAL PRIMARY KEY,
    province_name   VARCHAR NOT NULL UNIQUE,  -- e.g. "DKI Jakarta", "Jawa Barat"
    island_group    VARCHAR,                  -- e.g. "Jawa", "Sumatera", "Kalimantan"
    added_at        TIMESTAMP DEFAULT NOW()
);
```

`province_name` is the join key between `tower_master` and `province_master`. `island_group` is derived manually (a simple lookup) to support island-level aggregation in the province summary mart.

### 5.5 Key Telco Metric: PRB Utilization

PRB (Physical Resource Block) utilization is the standard telco measure of how much of a tower's radio capacity is in use — analogous to CPU utilization for a server. Thresholds by cell type, stored in the `tower_thresholds` dbt seed table and joined at mart build time:

| Cell Type | Warn Threshold | Critical Threshold |
|-----------|---------------|-------------------|
| Urban | 70% | 85% |
| Suburban | 65% | 80% |
| Rural | 60% | 75% |

### 5.6 Data Lake Zones (S3 / MinIO)

```
netpulse-lake/
├── raw/
│   ├── opencellid/YYYY/MM/DD/          # Indonesia tower slice (cloud only)
│   ├── tower_telemetry/YYYY/MM/DD/     # Synthetic hourly telemetry
│   └── subscriber_sessions/YYYY/MM/DD/ # Synthetic session records
├── staging/
│   ├── tower_telemetry_cleaned/YYYY/MM/DD/
│   └── subscriber_sessions_cleaned/YYYY/MM/DD/
└── curated/
    └── (managed by dbt; loaded into PostgreSQL)
```

**Zone semantics:**
- **Raw:** Immutable. Exactly as generated or ingested. Partitioned by date. Never overwritten or deleted by pipeline runs.
- **Staging:** Cleaned and validated. Nulls handled, types cast, anomalous readings flagged (e.g. PRB > 100% indicating sensor fault), duplicates removed. Partitioned by date.
- **Curated:** Aggregated, business-ready. Managed entirely by dbt. Loaded into PostgreSQL for dashboard and alert consumption.

---

## 6. Pipeline Architecture

### 6.1 High-Level Flow

```
[OpenCelliD Indonesia Slice]
          │
          ▼ (one-time / periodic refresh)
[DAG 0: netpulse_seed_towers]          ← cloud only; local uses seed script
   Fetch OpenCelliD → S3 raw → sample 100 towers → load tower_master into RDS
          │
          ▼ (daily)
[DAG 1: netpulse_acquisition]
   Generate synthetic telemetry + sessions → land in S3/MinIO raw zone
          │
          ▼
[DAG 2: netpulse_staging]
   Read S3 raw → clean & validate → write S3/MinIO staging zone
          │
          ▼
[DAG 3: netpulse_dbt]
   dbt seed → dbt staging models → dbt mart models → dbt test
          │
          ▼
[DAG 4: netpulse_alerts]
   Query hotspot marts → evaluate alert rules → insert into PostgreSQL alerts table
          │
          ▼
[Streamlit Dashboard]
   Query PostgreSQL → render tower map, leaderboard, drilldown, alerts panel
```

### 6.2 Airflow DAGs

#### DAG 0: `netpulse_seed_towers` *(cloud deployment only)*
**Schedule:** Manual trigger (initial seed) + `@monthly` (refresh)
**Purpose:** Fetch latest OpenCelliD Indonesia slice, land in S3, sample and load tower master into RDS

Tasks:
- `fetch_opencellid_indonesia` — calls OpenCelliD download API with API key from SSM Parameter Store, writes raw CSV to `s3://netpulse-lake/raw/opencellid/YYYY/MM/DD/`
- `sample_towers` — reads raw CSV, filters to MCC 510, samples 100 towers across operator MNCs and radio types, applies cell type classification heuristic
- `load_tower_master` — upserts sampled towers into `tower_master` table in RDS
- `validate_tower_master` — asserts row count = 100, all lat/long non-null, all cell types assigned

Operator: `PythonOperator` using `boto3` and `psycopg2`.

Local equivalent: `scripts/seed_opencellid_local.py` — reads from `/data/opencellid/`, performs same sampling and classification logic, loads into local PostgreSQL and MinIO.

---

#### DAG 1: `netpulse_acquisition`
**Schedule:** Daily at 01:00 UTC
**Purpose:** Generate synthetic daily telemetry and session data anchored to real tower IDs, land in S3 raw zone

Tasks:
- `start` — DummyOperator
- `generate_tower_telemetry` — reads tower master from PostgreSQL, generates hourly PRB/latency/throughput/dropped-call/handover metrics per tower with realistic distributions (urban towers higher baseline utilization, rush hour peaks 08:00–09:00 and 18:00–20:00 WIB), writes Parquet to `raw/tower_telemetry/YYYY/MM/DD/`
- `generate_subscriber_sessions` — generates session records distributed across towers weighted by tower capacity and time of day, writes Parquet to `raw/subscriber_sessions/YYYY/MM/DD/`
- `validate_raw_landing` — asserts both files landed, row counts within expected range; raises on failure
- `end` — DummyOperator

`generate_tower_telemetry` and `generate_subscriber_sessions` run in parallel after `start`.

Operator: `PythonOperator`.

---

#### DAG 2: `netpulse_staging`
**Schedule:** Daily at 02:00 UTC
**Depends on:** DAG 1 success (ExternalTaskSensor)
**Purpose:** Clean and validate raw data, write to staging zone

Tasks (two parallel branches, one per source):

*Branch A — Tower Telemetry:*
- `read_raw_tower_telemetry` → `clean_tower_telemetry` → `write_staging_tower_telemetry`

*Branch B — Subscriber Sessions:*
- `read_raw_subscriber_sessions` → `clean_subscriber_sessions` → `write_staging_subscriber_sessions`

Cleaning operations:
- **Tower telemetry:** null imputation for minor fields, flag and quarantine rows where PRB > 100% (sensor fault indicator), cast types, validate tower ID exists in tower master, add `is_sensor_fault` boolean column
- **Subscriber sessions:** deduplication on `(subscriber_id, tower_id, session_start)`, null handling on required fields, validate subscriber ID exists in subscriber master, validate tower ID exists in tower master

Operator: `PythonOperator` using `boto3` for S3 I/O and `pandas` for transform logic.

---

#### DAG 3: `netpulse_dbt`
**Schedule:** Daily at 03:00 UTC
**Depends on:** DAG 2 success (ExternalTaskSensor)
**Purpose:** Build all dbt models and run data quality tests

Tasks:
- `dbt_seed` — loads `tower_thresholds` seed into PostgreSQL (`dbt seed`)
- `dbt_staging` — runs staging layer (`dbt run --select staging.*`)
- `dbt_marts` — runs mart layer (`dbt run --select marts.*`)
- `dbt_test` — runs all data quality tests (`dbt test`)

`dbt_staging` depends on `dbt_seed`. `dbt_marts` depends on `dbt_staging`. `dbt_test` depends on `dbt_marts`.

Operator: `BashOperator` invoking dbt CLI.

---

#### DAG 4: `netpulse_alerts`
**Schedule:** Daily at 04:30 UTC
**Depends on:** DAG 3 success (ExternalTaskSensor)
**Purpose:** Evaluate alert rules against mart outputs, write actionable alerts to PostgreSQL

Tasks:
- `evaluate_hotspot_alerts` — queries `mart_hotspot_summary` for towers where 7-day congestion frequency exceeds thresholds; inserts CRITICAL or WARN alert records
- `evaluate_peak_hour_alerts` — queries `mart_peak_hour_patterns` for towers with consistent peak congestion (>=5 of last 7 days at the same hour); inserts PATTERN alert records
- `evaluate_neighbour_alerts` — queries `mart_neighbour_impact` for towers where handover spikes correlate with upstream congestion; inserts SPILLOVER alert records
- `expire_resolved_alerts` — marks ACTIVE alerts as RESOLVED where the triggering tower has not congested in the past 3 consecutive days

All tasks run sequentially. Operator: `PythonOperator` using `psycopg2`.

**Alerts table schema:**
```sql
CREATE TABLE alerts (
    alert_id        SERIAL PRIMARY KEY,
    tower_id        VARCHAR NOT NULL,
    alert_type      VARCHAR NOT NULL,  -- CRITICAL | WARN | PATTERN | SPILLOVER
    alert_category  VARCHAR NOT NULL,  -- HOTSPOT | PEAK_HOUR | NEIGHBOUR
    severity        INTEGER NOT NULL,  -- 1 (low) to 3 (high)
    message         TEXT,
    triggered_at    TIMESTAMP NOT NULL,
    resolved_at     TIMESTAMP,
    status          VARCHAR NOT NULL   -- ACTIVE | RESOLVED
);
```

### 6.3 Scale-Up Path (Spark / EMR)

> **Architecture note (not implemented):** At production scale, DAG 2's staging transform layer would be replaced by PySpark jobs submitted to an ephemeral AWS EMR cluster. Production telco networks generate tower telemetry every few seconds across thousands of towers — hundreds of millions of rows daily — which makes pandas-based transforms unsuitable. The EMR cluster would be provisioned per DAG run using Airflow's `EmrCreateJobFlowOperator`, jobs submitted via `EmrAddStepsOperator`, and the cluster terminated on completion with `EmrTerminateJobFlowOperator`. The S3 data lake structure, dbt layer, and downstream marts remain unchanged — only the compute layer scales. This is deferred to production deployment where infrastructure costs are justified by data volume.

---

## 7. dbt Models

### 7.1 Staging Models (thin, 1:1 with sources)

- `stg_tower_telemetry` — typed, validated hourly tower metrics with `is_sensor_fault` flag; sensor fault rows retained but excluded from downstream mart aggregations
- `stg_subscriber_sessions` — deduplicated session records with tower and subscriber reference joins

### 7.2 Seeds

- `tower_thresholds` — configurable PRB warn/critical thresholds and latency warn thresholds per cell type (urban/suburban/rural)

### 7.3 Marts

| Mart | Description | Primary Consumer |
|------|-------------|-----------------|
| `mart_congestion_events` | Each tower-hour where PRB exceeded warn or critical threshold, joined to `tower_thresholds` seed. Columns: tower_id, event_hour, prb_utilization, threshold_warn, threshold_critical, severity (WARN/CRITICAL), is_sensor_fault (excluded). | Base for all downstream marts |
| `mart_hotspot_summary` | Per-tower rolling 7-day and 30-day congestion frequency (%), average PRB utilization, peak congestion hour, total affected subscriber-hours. Ranked by congestion frequency. | Hotspot leaderboard, alert DAG |
| `mart_peak_hour_patterns` | Per-tower, per-hour-of-day: average PRB across last 30 days, congestion occurrence rate (%). Identifies structurally congested time slots vs one-off spikes. | Tower drilldown, alert DAG |
| `mart_neighbour_impact` | For each congestion event, identifies neighbouring towers by haversine proximity and correlates with handover count spikes. Flags SPILLOVER cases where a congested tower is measurably offloading to neighbours. | Neighbour impact section, alert DAG |
| `mart_subscriber_impact` | Joins congestion windows to session records. Per congestion event: subscriber count affected, estimated degraded session minutes, service type breakdown (voice/data/SMS). | Tower drilldown subscriber impact section |
| `mart_network_health_snapshot` | Latest daily composite health score per tower (0–100): weighted combination of PRB utilization vs threshold, dropped call rate, and latency. Drives dashboard map colour coding. | pydeck tower map |
| `mart_province_summary` | Province-level aggregation joined from `tower_master.province_name`. Columns: province_name, island_group, tower_count, congested_tower_count, congestion_rate (%), avg_health_score, total_affected_subscriber_hours (rolling 7d and 30d). Ranked by congestion rate. | Province choropleth on pydeck map, province leaderboard tab |

### 7.4 dbt Tests

- `not_null` + `unique` on all primary keys across staging and mart models
- `accepted_values` on `severity` (WARN, CRITICAL), `cell_type` (urban, suburban, rural), `service_type` (voice, data, SMS), `status` (ACTIVE, RESOLVED)
- `relationships` test: every `tower_id` in telemetry and sessions exists in `tower_master`
- `relationships` test: every `cell_type` in `tower_master` exists in `tower_thresholds`
- Custom test `prb_range_valid`: PRB utilization between 0 and 100 in staging (sensor fault rows flagged separately, not dropped)
- Custom test `congestion_threshold_defined`: every tower in `mart_congestion_events` has a matching threshold record via cell type join

---

## 8. AWS Infrastructure (Terraform)

### 8.1 Network Architecture

```
                        Internet
                            │
                    [Internet Gateway]
                            │
              ┌─────────────┴─────────────┐
              │        Public Subnet       │
              │     (NAT Gateway only)     │
              └─────────────┬─────────────┘
                            │ (outbound only)
              ┌─────────────┴──────────────┐
              │        Private Subnet       │
              │   EC2 (Airflow)  RDS (PG)  │
              └────────────────────────────┘
                            │
                     [S3 via VPC
                    Gateway Endpoint]
```

**Key design decisions:**
- EC2 (Airflow host) sits in the private subnet — not directly reachable from the internet. Access via AWS Systems Manager Session Manager (no bastion host, no port 22 exposed)
- RDS sits in the private subnet — reachable only from within the VPC via the Airflow EC2 security group as source
- S3 accessed via **VPC Gateway Endpoint** — traffic stays on the AWS backbone, bypassing the NAT Gateway entirely. Avoids NAT data processing charges on S3 reads/writes
- NAT Gateway handles all other outbound internet traffic (pip installs, dbt package downloads, OpenCelliD API calls, AWS API calls to non-S3 services)
- OpenCelliD API key stored in SSM Parameter Store — fetched at runtime by DAG 0, never stored in code or environment files

### 8.2 Resources Provisioned

```hcl
# VPC & Networking
aws_vpc.netpulse                            # CIDR: 10.0.0.0/16
aws_subnet.public                           # 10.0.1.0/24 — NAT Gateway only
aws_subnet.private_a                        # 10.0.2.0/24 — EC2, RDS
aws_subnet.private_b                        # 10.0.3.0/24 — RDS (subnet group requires 2 AZs)
aws_internet_gateway.igw
aws_eip.nat                                 # Elastic IP for NAT Gateway
aws_nat_gateway.nat                         # In public subnet
aws_route_table.public_rt                   # Default route → IGW
aws_route_table.private_rt                  # Default route → NAT Gateway
aws_route_table_association.public
aws_route_table_association.private_a
aws_route_table_association.private_b
aws_vpc_endpoint.s3                         # Gateway endpoint — S3 traffic bypasses NAT

# Security Groups
aws_security_group.airflow_sg               # EC2: all outbound; no inbound from internet
aws_security_group.rds_sg                   # RDS: port 5432 inbound from airflow_sg only

# S3
aws_s3_bucket.netpulse_lake
aws_s3_bucket_versioning
aws_s3_bucket_lifecycle_configuration       # 90-day transition to S3-IA for raw/staging zones
aws_s3_bucket_policy                        # Restrict access to VPC endpoint only

# RDS
aws_db_instance.netpulse_postgres           # PostgreSQL 15, db.t3.micro, 20GB gp2
aws_db_subnet_group.netpulse                # Spans private_a + private_b

# EC2
aws_instance.airflow_host                   # t3.small, Amazon Linux 2, private_a
aws_iam_instance_profile.airflow_profile

# SSM Parameter Store
aws_ssm_parameter.db_password               # RDS password — never in plaintext
aws_ssm_parameter.opencellid_api_key        # OpenCelliD API key — fetched by DAG 0 at runtime

# IAM
aws_iam_role.airflow_role
aws_iam_policy.s3_readwrite                 # Scoped to netpulse-lake bucket only
aws_iam_policy.rds_connect
aws_iam_policy.ssm_session_manager          # Enables SSM-based EC2 access (replaces SSH)
aws_iam_policy.ssm_parameter_read           # Read DB password + OpenCelliD key from SSM
aws_iam_role_policy_attachment              # All policies attached to airflow_role
```

### 8.3 Terraform File Layout

```
terraform/
├── main.tf               # Provider config, terraform backend (S3 remote state)
├── variables.tf          # Region, CIDRs, instance types, DB config
├── outputs.tf            # RDS endpoint, S3 bucket name, VPC ID, EC2 instance ID
├── vpc.tf                # VPC, subnets, IGW, NAT GW, route tables, S3 VPC endpoint
├── security_groups.tf
├── s3.tf                 # Bucket, versioning, lifecycle, bucket policy
├── rds.tf                # DB instance, subnet group
├── ec2.tf                # EC2 instance, instance profile
└── iam.tf                # Role, policies, attachments
```

### 8.4 Cost Profile & Destroy Strategy

| Resource | Approx cost when running |
|----------|--------------------------|
| NAT Gateway | ~$0.045/hr + $0.045/GB (S3 traffic free via endpoint) |
| EC2 t3.small | ~$0.023/hr |
| RDS db.t3.micro | ~$0.017/hr |
| S3 | ~$0.023/GB/month (negligible at synthetic data volume) |

**Workflow:** `terraform apply` → run full pipeline including DAG 0 tower seed + 35-day backfill → validate dashboard and alerts → `terraform destroy`. Full session estimated under 3 hours; total cost well under $1.

**Note:** S3 bucket excluded from `terraform destroy` via `lifecycle { prevent_destroy = true }`. Raw and staging data persists across sessions; only compute resources are torn down.

---

## 9. Dashboard (Streamlit + pydeck)

Read-only. Queries PostgreSQL (RDS in cloud, local container in dev). Connection string injected via environment variable.

### Page 1: Network Health Map
- **pydeck GeoJsonLayer** rendering simplified Indonesia province boundaries (`chmdznr/indonesia-geojson`), colour-filled by province-level average health score from `mart_province_summary`: green (healthy) → amber (warn) → red (critical). GeoJSON loaded at dashboard runtime from local filesystem — geometry is not stored in PostgreSQL.
- **pydeck ScatterplotLayer** rendered on top of the province layer — all 100 towers at their real OpenCelliD lat/long coordinates, colour-coded by individual tower health score from `mart_network_health_snapshot`
- Tower size scaled by connected subscriber count in selected time window
- Click a tower → sidebar shows tower ID, radio type, operator MNC, cell type, province, current PRB utilization, health score
- Click a province polygon → sidebar shows province name, tower count, congested tower count, province congestion rate, avg health score
- Time window selector (last 24h / 7d / 30d) controls which snapshot drives colouring for both layers

### Page 2: Hotspot Leaderboard
Two tabs on this page:

**Tab A — Tower Leaderboard:**
- Ranked table of top 20 most congested towers over selected rolling window (7d or 30d)
- Columns: rank, tower ID, province, cell type, radio type, congestion frequency (%), avg PRB utilization, peak congestion hour, total affected subscriber-hours
- Clicking a row navigates to Page 3 drilldown for that tower

**Tab B — Province Leaderboard:**
- Ranked table of all provinces with at least one congested tower, sourced from `mart_province_summary`
- Columns: rank, province name, island group, tower count, congested towers, congestion rate (%), avg health score, total affected subscriber-hours
- Gives network planning teams a geographic view of where to prioritise capacity investment

### Page 3: Tower Drilldown
- Tower metadata header: real coordinates, radio type, operator MNC, cell type, province, warn/critical thresholds
- Hourly PRB utilization line chart over past 7 days with warn and critical threshold lines overlaid
- Congestion event history table: date, hour, severity, subscriber count affected, degraded session minutes
- Peak hour heatmap: hour of day × day of week, PRB utilization as colour intensity
- Neighbour impact section: neighbouring towers ranked by handover spike correlation score
- Subscriber impact summary: total affected sessions, degraded session minutes by service type (voice/data/SMS)

### Page 4: Active Alerts
- Summary metrics row: total active alerts, critical count, towers affected, provinces affected, oldest active alert age
- Filterable alerts table by alert type (CRITICAL / WARN / PATTERN / SPILLOVER), province, and island group
- Columns: tower ID, province, alert type, severity, message, triggered at, days active
- Alerts sourced directly from the `alerts` PostgreSQL table (status = ACTIVE)

---

## 10. Repository Structure

```
netpulse/
├── .gitignore                          # Includes /data/, .env, __pycache__
├── data/                               # GITIGNORED — local dev data only
│   ├── opencellid/                     # Manually downloaded Indonesia slice goes here
│   └── boundaries/                     # Manually downloaded province GeoJSON goes here
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── vpc.tf
│   ├── security_groups.tf
│   ├── s3.tf
│   ├── rds.tf
│   ├── ec2.tf
│   └── iam.tf
├── scripts/
│   └── seed_opencellid_local.py        # Local-only: reads /data/opencellid/, loads into MinIO + local PG
├── generators/
│   ├── generate_tower_telemetry.py     # Generates hourly telemetry anchored to real tower IDs
│   ├── generate_subscriber_sessions.py
│   └── seed_subscriber_master.py
├── dags/
│   ├── netpulse_seed_towers.py         # DAG 0 — cloud only: OpenCelliD → S3 → RDS
│   ├── netpulse_acquisition.py         # DAG 1
│   ├── netpulse_staging.py             # DAG 2
│   ├── netpulse_dbt.py                 # DAG 3
│   └── netpulse_alerts.py              # DAG 4
├── transforms/
│   ├── clean_tower_telemetry.py
│   └── clean_subscriber_sessions.py
├── dbt/
│   ├── models/
│   │   ├── staging/
│   │   │   ├── stg_tower_telemetry.sql
│   │   │   └── stg_subscriber_sessions.sql
│   │   └── marts/
│   │       ├── mart_congestion_events.sql
│   │       ├── mart_hotspot_summary.sql
│   │       ├── mart_peak_hour_patterns.sql
│   │       ├── mart_neighbour_impact.sql
│   │       ├── mart_subscriber_impact.sql
│   │       ├── mart_network_health_snapshot.sql
│   │       └── mart_province_summary.sql
│   ├── seeds/
│   │   └── tower_thresholds.csv        # Configurable per cell type — committed to repo
│   ├── tests/
│   │   ├── prb_range_valid.sql
│   │   └── congestion_threshold_defined.sql
│   └── dbt_project.yml
├── dashboard/
│   └── app.py
├── docker-compose.yml                  # Airflow, PostgreSQL, MinIO for local dev
├── .env.example                        # All required env vars documented, no secrets
└── README.md
```

**What lives in the repo vs not:**

| Item | In repo | Reason |
|------|---------|--------|
| All Python code, DAGs, transforms | Yes | Source code |
| dbt models, tests, `dbt_project.yml` | Yes | Source code |
| `tower_thresholds.csv` (dbt seed) | Yes | Config, not data — 3 rows |
| `.env.example` | Yes | Documents required vars without secrets |
| `docker-compose.yml` | Yes | Dev environment definition |
| Terraform HCL | Yes | Infrastructure as code |
| OpenCelliD CSV | No | Raw data, gitignored |
| Province boundary GeoJSON | No | Raw data, gitignored |
| `.env` | No | Contains secrets |
| `/data/` directory | No | Local dev data, gitignored |

---

## 11. Development Stages

### Stage 1: Local Development

**Goal:** Full pipeline working end-to-end on local machine. Zero AWS costs.

**Local stack (Docker Compose):**
- Airflow (official `apache/airflow` image)
- PostgreSQL (local container — schema mirrors RDS exactly)
- MinIO (S3-compatible local object store — pipeline code is identical; only endpoint URL differs)
- dbt (runs against local PostgreSQL via CLI)
- Streamlit (runs locally against local PostgreSQL)

**Tower and boundary seeding (local):**
1. Register at opencellid.org (free), download Indonesia slice CSV
2. Place in `/data/opencellid/`
3. Download simplified province GeoJSON from `chmdznr/indonesia-geojson` GitHub repo
4. Place in `/data/boundaries/`
5. Run `scripts/seed_opencellid_local.py` — samples 100 towers, runs point-in-polygon province assignment using `shapely`, loads into local PostgreSQL `tower_master` and `province_master` tables
6. Run `scripts/seed_subscriber_master.py` — generates 50,000 synthetic subscribers

**Environment-agnostic discipline:** All connection strings, S3/MinIO endpoints, bucket names, and credentials injected via `.env`. No hardcoded values anywhere in pipeline code. Local → cloud transition is a `.env` swap only.

**Stage 1 deliverables:**
- Tower master loaded from real OpenCelliD data in local PostgreSQL
- All five DAGs (DAG 0 skipped locally; replaced by seed script) running successfully in local Airflow
- 35-day backfill completed via Airflow backfill command
- All dbt models building and tests passing against local PostgreSQL
- All four Streamlit pages rendering correctly with local data including real tower coordinates on pydeck map
- Alert DAG inserting correctly into local alerts table; Page 4 showing active alerts

### Stage 2: Cloud Deployment

**Goal:** Validate full pipeline on real AWS infrastructure.

**Steps:**
1. `terraform apply` — provision all resources
2. Store OpenCelliD API key and DB password in SSM Parameter Store
3. Trigger `netpulse_seed_towers` (DAG 0) — fetches latest Indonesia slice, loads tower master into RDS
4. Swap `.env` to point at real S3, RDS, and AWS credentials
5. Run Airflow backfill for 35 days of historical telemetry and sessions on AWS
6. Validate all six marts and alerts table populated correctly in RDS
7. Point Streamlit at RDS, validate all four dashboard pages
8. Screenshot pipeline run, DAG graph, and dashboard for README
9. `terraform destroy`

**Stage 2 deliverables:**
- Architecture diagram (AWS resource layout with VPC, subnets, NAT GW, S3 endpoint)
- README deployment section: step-by-step Terraform + Airflow + DAG 0 setup
- Screenshot evidence of live pipeline run on real AWS
- Documented Spark/EMR scale-up path in README

---

## 12. Build Plan (2 Weeks)

### Week 1 — Local Development (Stage 1)

| Day | Task |
|-----|------|
| 1 | Docker Compose setup (Airflow, PostgreSQL, MinIO). Download OpenCelliD Indonesia slice. Run `seed_opencellid_local.py`. Verify tower master loaded with real coordinates. |
| 2 | Telemetry + session generators (anchored to real tower IDs). Subscriber master seed. 35-day backfill script. Validate output schemas and distributions. |
| 3 | DAG 1 (`netpulse_acquisition`) + DAG 2 (`netpulse_staging`). Cleaning transforms for both sources. End-to-end raw → staging working in local Airflow. |
| 4 | dbt project setup. Staging models + `tower_thresholds` seed. All staging dbt tests passing. |
| 5 | dbt mart models: `mart_congestion_events`, `mart_hotspot_summary`, `mart_peak_hour_patterns`. |
| 6 | dbt mart models: `mart_neighbour_impact`, `mart_subscriber_impact`, `mart_network_health_snapshot`. All dbt tests passing. |
| 7 | DAG 3 (`netpulse_dbt`) + DAG 4 (`netpulse_alerts`). Alerts table schema. Alert evaluation logic. Full local pipeline end-to-end validated. |

### Week 2 — Dashboard + Cloud Deployment (Stage 2)

| Day | Task |
|-----|------|
| 8 | Streamlit Page 1 (pydeck network health map with real coordinates) + Page 4 (active alerts). |
| 9 | Streamlit Page 2 (hotspot leaderboard) + Page 3 (tower drilldown with all charts). |
| 10 | Terraform: write all HCL files. `terraform apply`. Validate all AWS resources provisioned correctly. |
| 11 | Cloud deployment: DAG 0 tower seed on AWS, `.env` swap, 35-day backfill, validate RDS marts and alerts. |
| 12 | README: architecture diagram, deployment guide, OpenCelliD setup instructions, Spark/EMR scale-up section, limitations. `terraform destroy`. |

---

## 13. Limitations (Honest Scope)

- **Telemetry is synthetic.** OpenCelliD provides real tower locations and metadata, but hourly PRB utilization, latency, throughput, and session data are synthetically generated. Distributions are designed to be realistic but do not reflect actual network conditions.
- **Proximity-based neighbour detection.** Neighbour towers are identified by haversine distance, not actual RAN (Radio Access Network) neighbour relation tables. Production systems maintain explicit neighbour lists configured by network engineers.
- **Cell type classification is heuristic.** Urban/suburban/rural classification is inferred from radio type and MNC cluster density, not from official operator network planning data.
- **Single-node compute.** Pandas-based staging transforms are not production-scalable. Spark on EMR is the documented production path (Section 6.3).
- **No real-time component.** Streaming congestion alerting (sub-minute SLA breach detection) is out of scope. Intentional batch-first architectural decision.
- **Single Terraform environment.** Production would use separate workspaces for dev/staging/prod. Omitted for cost reasons.
- **No dashboard authentication.** Acceptable for a portfolio prototype.

---

## 14. Resume Narrative

`netpulse` adds four things to the existing portfolio narrative that no existing project covers:

1. **Real external data ingestion managed by Airflow** — DAG 0 fetches from OpenCelliD, a live external API. Most DE portfolios use only internal or fully synthetic data sources.
2. **Airflow owning the full pipeline lifecycle** — five DAGs covering seeding, acquisition, staging, dbt orchestration, and alerting. Airflow is not just a scheduler here; it owns the complete operational rhythm.
3. **Operational domain depth** — congestion hotspot identification is a practitioner-validated telco use case, not a generic analytics exercise. The project was scoped with direct input from an AVP of Data Engineering at a telco company.
4. **Infrastructure discipline** — custom VPC, private subnets, NAT Gateway, S3 VPC Gateway Endpoint, and SSM-based credential management show AWS networking and security awareness beyond basic resource provisioning.

**Draft resume bullet:**
> *"Architected a batch telco network congestion intelligence pipeline on AWS — five Airflow DAGs orchestrating real external data ingestion from OpenCelliD (Indonesian cell towers, MCC 510) and province boundary data (38 Indonesian provinces), synthetic telemetry generation, ELT staging, and automated alerting, with a three-zone S3 data lake, seven dbt analytics marts covering hotspot identification, province-level congestion aggregation, peak hour patterns, and subscriber impact, and infrastructure provisioned via Terraform with a custom VPC and private subnet architecture — processing ~152,000 events daily across 100 real towers and 50,000 subscribers."*
