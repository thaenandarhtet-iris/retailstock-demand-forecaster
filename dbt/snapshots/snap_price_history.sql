{% snapshot snap_price_history %}
{{ config(
    target_schema='snapshots',
    unique_key="source || '|' || store || '|' || sku",
    strategy='check',
    check_cols=['price', 'is_promo'],
) }}
-- The latest observation per product and store; each price change becomes a new dated row.
select *
from {{ ref('stg_scraped_prices') }}
qualify row_number() over (partition by source, store, sku order by observed_on desc, scraped_at desc) = 1
{% endsnapshot %}
