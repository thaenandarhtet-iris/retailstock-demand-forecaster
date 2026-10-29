-- Days before an item was first stocked have no price in M5; they aren't zero-demand days, so drop them.
select
    s.item_id,
    s.date,
    s.wm_yr_wk,
    s.units,
    p.sell_price,
    s.event_name
from {{ ref('stg_m5_sales') }} s
join {{ ref('stg_m5_prices') }} p using (item_id, wm_yr_wk)
