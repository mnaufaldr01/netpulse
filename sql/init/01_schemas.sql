-- netpulse PostgreSQL bootstrap schemas
-- Mirrors RDS schema for local/cloud parity

CREATE TABLE IF NOT EXISTS tower_master (
    tower_id        VARCHAR PRIMARY KEY,
    radio           VARCHAR NOT NULL,
    mcc             INTEGER NOT NULL,
    mnc             INTEGER NOT NULL,
    area            INTEGER NOT NULL,
    cell            INTEGER NOT NULL,
    lon             DOUBLE PRECISION NOT NULL,
    lat             DOUBLE PRECISION NOT NULL,
    range_m         INTEGER,
    samples         INTEGER,
    changeable      INTEGER,
    cell_type       VARCHAR NOT NULL,
    province_name   VARCHAR,
    island_group    VARCHAR,
    last_updated    TIMESTAMP,
    seeded_at       TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS province_master (
    province_id     SERIAL PRIMARY KEY,
    province_name   VARCHAR NOT NULL UNIQUE,
    island_group    VARCHAR,
    added_at        TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS subscriber_master (
    subscriber_id   VARCHAR PRIMARY KEY,
    plan_tier       VARCHAR NOT NULL,
    home_region     VARCHAR NOT NULL,
    seeded_at       TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id        SERIAL PRIMARY KEY,
    tower_id        VARCHAR NOT NULL,
    alert_type      VARCHAR NOT NULL,
    alert_category  VARCHAR NOT NULL,
    severity        INTEGER NOT NULL,
    message         TEXT,
    triggered_at    TIMESTAMP NOT NULL,
    resolved_at     TIMESTAMP,
    status          VARCHAR NOT NULL
);

-- Staging tables populated by DAG 2 transforms (dbt sources)
CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.tower_telemetry_cleaned (
    tower_id            VARCHAR NOT NULL,
    event_hour          TIMESTAMP NOT NULL,
    prb_utilization     DOUBLE PRECISION,
    throughput_mbps     DOUBLE PRECISION,
    latency_ms          DOUBLE PRECISION,
    dropped_call_rate   DOUBLE PRECISION,
    handover_count      INTEGER,
    connected_subscribers INTEGER,
    is_sensor_fault     BOOLEAN DEFAULT FALSE,
    partition_date      DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS staging.subscriber_sessions_cleaned (
    subscriber_id       VARCHAR NOT NULL,
    tower_id            VARCHAR NOT NULL,
    session_start       TIMESTAMP NOT NULL,
    session_end         TIMESTAMP,
    session_duration_min DOUBLE PRECISION,
    service_type        VARCHAR NOT NULL,
    bytes_transferred   BIGINT,
    partition_date      DATE NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_staging_telemetry_date ON staging.tower_telemetry_cleaned (partition_date);
CREATE INDEX IF NOT EXISTS idx_staging_sessions_date ON staging.subscriber_sessions_cleaned (partition_date);
