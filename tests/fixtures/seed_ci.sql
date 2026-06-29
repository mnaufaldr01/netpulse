-- CI / integration seed data for netpulse (run after sql/init/*.sql)
-- Idempotent: clears pipeline tables before insert.

TRUNCATE TABLE staging.tower_telemetry_cleaned;
TRUNCATE TABLE staging.subscriber_sessions_cleaned;
TRUNCATE TABLE alerts RESTART IDENTITY;
TRUNCATE TABLE subscriber_master;
TRUNCATE TABLE tower_master CASCADE;

INSERT INTO tower_master (
    tower_id, radio, mcc, mnc, area, cell, lon, lat, range_m,
    samples, changeable, cell_type, province_name, island_group
) VALUES
    ('twr000000001', 'LTE', 510, 1, 100, 1, 106.8456, -6.2088, 500, 10, 1, 'urban', 'DKI Jakarta', 'Jawa'),
    ('twr000000002', 'LTE', 510, 8, 100, 2, 106.8500, -6.2100, 2000, 10, 1, 'suburban', 'DKI Jakarta', 'Jawa'),
    ('twr000000003', 'LTE', 510, 11, 100, 3, 107.6191, -6.9175, 8000, 10, 1, 'rural', 'Jawa Barat', 'Jawa');

INSERT INTO subscriber_master (subscriber_id, plan_tier, home_region) VALUES
    ('sub000001', 'premium', 'Jawa'),
    ('sub000002', 'standard', 'Jawa');

-- 8 days of hourly telemetry (2025-06-21 .. 2025-06-28) for all towers
INSERT INTO staging.tower_telemetry_cleaned (
    tower_id, event_hour, prb_utilization, throughput_mbps, latency_ms,
    dropped_call_rate, handover_count, connected_subscribers, is_sensor_fault, partition_date
)
SELECT
    tm.tower_id,
    gs.event_hour,
    CASE
        WHEN tm.tower_id = 'twr000000001' AND EXTRACT(hour FROM gs.event_hour) BETWEEN 8 AND 20 THEN 82.0
        WHEN tm.tower_id = 'twr000000002' AND EXTRACT(hour FROM gs.event_hour) = 12 THEN 115.0
        ELSE 42.0
    END AS prb_utilization,
    45.0 AS throughput_mbps,
    28.0 AS latency_ms,
    0.4 AS dropped_call_rate,
    CASE
        WHEN tm.tower_id = 'twr000000001' THEN 20
        WHEN tm.tower_id = 'twr000000002' THEN 8
        ELSE 5
    END AS handover_count,
    60 AS connected_subscribers,
    CASE
        WHEN tm.tower_id = 'twr000000002' AND EXTRACT(hour FROM gs.event_hour) = 12 THEN TRUE
        ELSE FALSE
    END AS is_sensor_fault,
    gs.event_hour::date AS partition_date
FROM tower_master tm
CROSS JOIN LATERAL (
    SELECT generate_series(
        '2025-06-21'::date,
        '2025-06-28'::date + interval '23 hours',
        interval '1 hour'
    ) AS event_hour
) gs;

-- Subscriber sessions overlapping congestion hours on urban tower
INSERT INTO staging.subscriber_sessions_cleaned (
    subscriber_id, tower_id, session_start, session_end,
    session_duration_min, service_type, bytes_transferred, partition_date
) VALUES
    (
        'sub000001', 'twr000000001',
        '2025-06-28 08:00:00', '2025-06-28 10:00:00',
        120.0, 'data', 5000000, '2025-06-28'
    ),
    (
        'sub000001', 'twr000000001',
        '2025-06-28 08:30:00', '2025-06-28 09:30:00',
        60.0, 'voice', 0, '2025-06-28'
    ),
    (
        'sub000002', 'twr000000002',
        '2025-06-28 11:00:00', '2025-06-28 12:30:00',
        90.0, 'data', 2000000, '2025-06-28'
    );
