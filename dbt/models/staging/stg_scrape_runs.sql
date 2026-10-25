select
    source,
    started_at,
    cast(started_at as date) as run_date,
    pages,
    rows,
    parse_failures,
    null_prices,
    duration_s
from {{ source('raw', 'scrape_runs') }}
