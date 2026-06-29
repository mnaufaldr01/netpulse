with congestion as (
    select tower_id, event_hour, severity
    from {{ ref('mart_congestion_events') }}
),
sessions as (
    select *
    from {{ ref('stg_subscriber_sessions') }}
)
select
    c.tower_id,
    c.event_hour,
    c.severity,
    count(distinct s.subscriber_id) as subscriber_count_affected,
    sum(s.session_duration_min) as degraded_session_minutes,
    count(distinct case when s.service_type = 'voice' then s.subscriber_id end) as voice_sessions,
    count(distinct case when s.service_type = 'data' then s.subscriber_id end) as data_sessions,
    count(distinct case when s.service_type = 'SMS' then s.subscriber_id end) as sms_sessions
from congestion c
left join sessions s
    on c.tower_id = s.tower_id
    and s.session_start <= c.event_hour + interval '1 hour'
    and s.session_end >= c.event_hour
group by c.tower_id, c.event_hour, c.severity
