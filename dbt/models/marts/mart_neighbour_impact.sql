with towers as (
    select tower_id, lat, lon from {{ source('netpulse', 'tower_master') }}
),
congested as (
    select distinct tower_id, event_hour
    from {{ ref('mart_congestion_events') }}
),
telemetry as (
    select tower_id, event_hour, handover_count
    from {{ ref('stg_tower_telemetry') }}
    where is_sensor_fault = false
),
pairs as (
    select
        a.tower_id as source_tower_id,
        b.tower_id as neighbour_tower_id,
        t.event_hour,
        t.handover_count as source_handovers,
        t2.handover_count as neighbour_handovers
    from congested c
    inner join towers a on c.tower_id = a.tower_id
    inner join telemetry t on a.tower_id = t.tower_id and c.event_hour = t.event_hour
    inner join towers b on a.tower_id != b.tower_id
    inner join telemetry t2 on b.tower_id = t2.tower_id and c.event_hour = t2.event_hour
    where (
        6371000 * acos(
            least(1.0, greatest(-1.0,
                cos(radians(a.lat)) * cos(radians(b.lat))
                * cos(radians(b.lon) - radians(a.lon))
                + sin(radians(a.lat)) * sin(radians(b.lat))
            ))
        )
    ) < 3000
)
select
    source_tower_id,
    neighbour_tower_id,
    case when neighbour_handovers > source_handovers * 1.5 then true else false end as is_spillover
from pairs
group by source_tower_id, neighbour_tower_id, source_handovers, neighbour_handovers
having neighbour_handovers > source_handovers * 1.5
