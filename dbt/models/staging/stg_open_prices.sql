select *
from {{ ref('stg_scraped_prices') }}
where source = 'open_prices'
