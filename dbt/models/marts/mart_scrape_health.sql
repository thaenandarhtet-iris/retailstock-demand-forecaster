select
    run_date,
    source,
    sum(rows) as rows,
    sum(pages) as pages,
    sum(parse_failures) as parse_failures,
    sum(null_prices) as null_prices,
    sum(parse_failures) * 1.0 / nullif(sum(pages), 0) as failure_rate,
    sum(duration_s) as duration_s
from {{ ref('stg_scrape_runs') }}
group by run_date, source
