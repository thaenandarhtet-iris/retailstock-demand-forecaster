select
    item_id,
    split_part(item_id, '_', 1) || '_' || split_part(item_id, '_', 2) as dept_id,
    min(date) as first_sold,
    max(date) as last_sold,
    count(distinct sell_price) as n_prices
from {{ ref('fct_daily_sku') }}
group by item_id
