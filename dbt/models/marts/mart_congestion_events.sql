with telemetry as (
    select * from {{ ref('stg_tower_telemetry') }}
    where is_sensor_fault = false
),
thresholds as (
    select * from {{ ref('tower_thresholds') }}
),
joined as (
    select
        t.tower_id,
        t.event_hour,
        t.prb_utilization,
        th.prb_warn_pct as threshold_warn,
        th.prb_critical_pct as threshold_critical,
        case
            when t.prb_utilization >= th.prb_critical_pct then 'CRITICAL'
            when t.prb_utilization >= th.prb_warn_pct then 'WARN'
        end as severity,
        t.is_sensor_fault
    from telemetry t
    inner join {{ source('netpulse', 'tower_master') }} tm on t.tower_id = tm.tower_id
    inner join thresholds th on tm.cell_type = th.cell_type
)
select *
from joined
where severity is not null
