select
    s.subscriber_id,
    s.tower_id,
    s.session_start,
    s.session_end,
    s.session_duration_min,
    s.service_type,
    s.bytes_transferred,
    s.partition_date
from {{ source('staging_raw', 'subscriber_sessions_cleaned') }} as s
