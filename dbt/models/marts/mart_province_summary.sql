with towers as (
    select
        province_name,
        island_group,
        tower_id
    from {{ source('netpulse', 'tower_master') }}
    where province_name is not null
),
hotspots as (
    select tower_id, congestion_frequency_7d, congestion_frequency_30d, total_affected_subscriber_hours
    from {{ ref('mart_hotspot_summary') }}
),
health as (
    select tower_id, health_score
    from {{ ref('mart_network_health_snapshot') }}
)
select
    t.province_name,
    max(t.island_group) as island_group,
    count(distinct t.tower_id) as tower_count,
    count(distinct case when h.congestion_frequency_7d >= 30 then t.tower_id end) as congested_tower_count,
    round(
        count(distinct case when h.congestion_frequency_7d >= 30 then t.tower_id end)::numeric
        / nullif(count(distinct t.tower_id), 0) * 100,
        1
    ) as congestion_rate,
    round(avg(hl.health_score)::numeric, 1) as avg_health_score,
    coalesce(sum(h.total_affected_subscriber_hours), 0) as total_affected_subscriber_hours_7d
from towers t
left join hotspots h on t.tower_id = h.tower_id
left join health hl on t.tower_id = hl.tower_id
group by t.province_name
order by congestion_rate desc nulls last
