select count(*) as invalid_prb_count
from {{ ref('stg_tower_telemetry') }}
where prb_utilization < 0 or (prb_utilization > 100 and is_sensor_fault = false)
having count(*) > 0
