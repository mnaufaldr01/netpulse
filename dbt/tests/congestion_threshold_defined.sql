select e.tower_id
from {{ ref('mart_congestion_events') }} e
left join {{ source('netpulse', 'tower_master') }} tm on e.tower_id = tm.tower_id
left join {{ ref('tower_thresholds') }} th on tm.cell_type = th.cell_type
where th.cell_type is null
