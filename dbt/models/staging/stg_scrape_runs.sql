-- A day can be scraped twice (the schedule plus a manual run). The second run replaces that day's data file,
-- so only the latest run per source and day describes what's in the warehouse.
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
where started_at is not null
qualify row_number() over (partition by source, cast(started_at as date) order by started_at desc) = 1
