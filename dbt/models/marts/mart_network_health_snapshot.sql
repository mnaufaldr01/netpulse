with latest as (
    select
        t.tower_id,
        t.prb_utilization,
        t.latency_ms,
        t.dropped_call_rate,
        t.connected_subscribers,
        t.partition_date,
        th.prb_warn_pct,
        th.prb_critical_pct
    from {{ ref('stg_tower_telemetry') }} t
    inner join {{ source('netpulse', 'tower_master') }} tm on t.tower_id = tm.tower_id
    inner join {{ ref('tower_thresholds') }} th on tm.cell_type = th.cell_type
    where t.is_sensor_fault = false
      and t.partition_date = (select max(partition_date) from {{ ref('stg_tower_telemetry') }})
),
scored as (
    select
        tower_id,
        connected_subscribers,
        greatest(0, least(100,
            100
            - greatest(0, (prb_utilization - prb_warn_pct) * 1.5)
            - (latency_ms / 10)
            - (dropped_call_rate * 10)
        )) as health_score
    from latest
)
select
    tower_id,
    round(avg(health_score)::numeric, 1) as health_score,
    max(connected_subscribers) as connected_subscribers
from scored
group by tower_id
