with telemetry as (
    select
        tower_id,
        extract(hour from event_hour) as hour_of_day,
        prb_utilization,
        event_hour::date as event_date
    from {{ ref('stg_tower_telemetry') }}
    where is_sensor_fault = false
      and event_hour >= current_date - interval '30 days'
),
thresholds as (
    select tm.tower_id, th.prb_warn_pct
    from {{ source('netpulse', 'tower_master') }} tm
    inner join {{ ref('tower_thresholds') }} th on tm.cell_type = th.cell_type
),
enriched as (
    select
        t.tower_id,
        t.hour_of_day,
        t.event_date,
        t.prb_utilization,
        case when t.prb_utilization >= th.prb_warn_pct then 1 else 0 end as is_congested
    from telemetry t
    inner join thresholds th on t.tower_id = th.tower_id
)
select
    tower_id,
    hour_of_day,
    avg(prb_utilization) as avg_prb_utilization,
    avg(is_congested::float) * 100 as congestion_occurrence_rate,
    sum(is_congested) as days_congested
from enriched
group by tower_id, hour_of_day
