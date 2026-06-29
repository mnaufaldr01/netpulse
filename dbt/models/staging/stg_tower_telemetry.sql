select
    t.tower_id,
    t.event_hour,
    t.prb_utilization,
    t.throughput_mbps,
    t.latency_ms,
    t.dropped_call_rate,
    t.handover_count,
    t.connected_subscribers,
    t.is_sensor_fault,
    t.partition_date
from {{ source('staging_raw', 'tower_telemetry_cleaned') }} as t
