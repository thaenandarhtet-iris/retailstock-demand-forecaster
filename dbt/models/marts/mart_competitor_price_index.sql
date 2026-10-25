-- Compare stores on identical products (same barcode) seen in at least two stores in the last 30 days.
-- 100 means a store prices at the middle of the market; 110 means 10% above it.
with recent as (
    select *
    from {{ ref('stg_open_prices') }}
    where observed_on > (select max(observed_on) from {{ ref('stg_open_prices') }}) - interval 30 day
),

store_prices as (
    select store, store_name, sku, any_value(category) as category,
        {{ median('price') }} as price,
        avg(case when is_promo then 1.0 else 0.0 end) as promo_share,
        avg(case when is_promo and was_price > 0 then 1 - price / was_price end) as depth
    from recent
    group by store, store_name, sku
),

market as (
    select sku, {{ median('price') }} as market_price
    from store_prices
    group by sku
    having count(distinct store) >= 2
)

select
    s.store,
    s.store_name,
    coalesce(s.category, 'unknown') as category,
    count(*) as n_products,
    round({{ median('s.price / m.market_price') }} * 100, 1) as price_index,
    avg(s.promo_share) as promo_share,
    avg(s.depth) as avg_depth
from store_prices s
join market m using (sku)
group by s.store, s.store_name, coalesce(s.category, 'unknown')
