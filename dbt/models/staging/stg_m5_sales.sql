select
    s.item_id,
    cast(s.date as date) as date,
    c.wm_yr_wk,
    s.units,
    nullif(c.event_name_1, '') as event_name
from {{ source('raw', 'm5_sales_long') }} s
join {{ source('raw', 'm5_calendar') }} c on cast(c.date as date) = cast(s.date as date)
