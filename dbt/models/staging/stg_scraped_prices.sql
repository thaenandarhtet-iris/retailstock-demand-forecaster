-- One row per source, store, product and day. Open Prices is pulled with a 30-day lookback every day,
-- so the same observation arrives many times; keep the most recent copy.
select
    source,
    store,
    coalesce(store_name, store) as store_name,
    sku,
    name,
    category,
    price,
    was_price,
    is_promo,
    observed_on,
    scraped_at
from {{ source('raw', 'scraped_prices') }}
where price > 0
qualify row_number() over (
    partition by source, store, sku, observed_on, coalesce(price_id, '')
    order by scraped_at desc
) = 1
