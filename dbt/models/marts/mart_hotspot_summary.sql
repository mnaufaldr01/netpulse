with events as (
    select * from {{ ref('mart_congestion_events') }}
),
telemetry as (
    select
        tower_id,
        event_hour::date as event_date,
        prb_utilization,
        extract(hour from event_hour) as hour_of_day
    from {{ ref('stg_tower_telemetry') }}
    where is_sensor_fault = false
),
agg as (
    select
        t.tower_id,
        count(distinct case when e.severity is not null and e.event_hour >= current_date - interval '7 days' then e.event_hour end)::float
            / nullif(count(distinct case when t.event_hour >= current_date - interval '7 days' then t.event_hour end), 0) * 100
            as congestion_frequency_7d,
        count(distinct case when e.severity is not null and e.event_hour >= current_date - interval '30 days' then e.event_hour end)::float
            / nullif(count(distinct case when t.event_hour >= current_date - interval '30 days' then t.event_hour end), 0) * 100
            as congestion_frequency_30d,
        avg(t.prb_utilization) as avg_prb_utilization,
        mode() within group (order by extract(hour from e.event_hour)) as peak_congestion_hour,
        count(distinct case when e.severity is not null then e.event_hour end) as total_congestion_hours
    from telemetry t
    left join events e on t.tower_id = e.tower_id and t.event_hour = e.event_hour
    group by t.tower_id
)
select
    tower_id,
    coalesce(congestion_frequency_7d, 0) as congestion_frequency_7d,
    coalesce(congestion_frequency_30d, 0) as congestion_frequency_30d,
    coalesce(avg_prb_utilization, 0) as avg_prb_utilization,
    peak_congestion_hour,
    coalesce(total_congestion_hours, 0) as total_affected_subscriber_hours
from agg
order by congestion_frequency_7d desc nulls last
