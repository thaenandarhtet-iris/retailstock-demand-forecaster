# RetailStock 2.0: Price & Promo Intelligence

This is the design for the second version of RetailStock. It lives on the `v2-price-promo` branch until it's ready to merge.

## The problem

RetailStock 1.0 forecasts demand for 500 SKUs and turns those forecasts into safety stock and reorder points. It works well on the Kaggle data, but it has a blind spot: it knows nothing about price or promotions. In real retail, those are the two biggest levers a business pulls, and they move demand more than anything else.

So 2.0 asks four questions:

1. **Which promotions actually made money?** Not just "did sales go up", but whether the extra sales covered the cost of the discount once you account for shoppers buying less afterwards.
2. **How sensitive is each product to price?** If the price goes up 10%, how much does demand fall?
3. **Does knowing price and promo make the forecast better?** And if it does, how much should stock levels change ahead of a planned promotion?
4. **How do real stores compare on price?** Using the same products, identified by barcode, across competing US grocery stores.

Everything 1.0 does keeps working exactly as before. 2.0 adds to it rather than replacing it.

## Where the data comes from

The tricky part of this project is that no single source has everything. Retail websites show prices and promotions, but never how many units they sold. Sales datasets have units, but usually no prices. So 2.0 uses three sources, each for what it's good at:

| Source | What it has | How it's collected | What it's used for |
|---|---|---|---|
| **M5 (Walmart, Kaggle)** | Daily unit sales and weekly prices, 2011 to 2016 | Downloaded manually into `data/raw/m5/`, not committed (same as the 1.0 data) | Promo lift, promo profit, price elasticity, and the price and promo inputs for the forecast |
| **Open Prices API (Open Food Facts)** | Real shelf prices from US stores, with a flag for discounted prices and the original price | Pulled daily from the API, slowly and politely | The competitor price index, and how often and how deeply each store discounts |
| **webscraper.io test store** | Product listings that load with JavaScript | Scraped daily with Selenium in headless Chrome | Shows the scraping pipeline working end to end. The site is built for practising scraping |

**Why not Target?** Target was the first choice, but its Terms & Conditions explicitly ban scraping and data extraction, and its robots.txt blocks the `/deals/` pages. This project only uses sources that allow it.

**Which M5 products.** M5 covers thousands of products, so 2.0 uses one store (`CA_1`) and one department (`FOODS_3`). Within that, it keeps the 200 items whose price changed the most often, because you can't measure price sensitivity on a product whose price never moves.

**Which Open Prices data.** Open Prices is crowdsourced from shoppers' receipts and covers many countries. 2.0 keeps only US stores, and only products seen in at least two stores, so every price has something to be compared against. The API ignores its own country filter, so this filtering happens in the code after the data comes back. The US data is mostly from Bay Area stores such as Safeway, Whole Foods, Trader Joe's and Costco.

## How it fits together

```
            ┌────────────────┐   ┌────────────────┐
 Selenium → │ webscraper.io  │   │ Open Prices API│ ← requests
            └───────┬────────┘   └───────┬────────┘
                    ▼                    ▼
   landing/raw/source=<src>/date=YYYY-MM-DD/part-0.jsonl     (laid out like a GCS bucket)
   landing/raw/m5/  (Kaggle CSVs, local only)
                    │
                    ▼  warehouse/load.py
          DuckDB  warehouse/retailstock.duckdb
                    │
                    ▼  dbt
   staging → snapshots (price history) → marts
                    │
          ┌─────────┴───────────┐
          ▼                     ▼
  src/pricing/              src/forecast.py, src/inventory.py
  lift, profit, elasticity  backtest, promo what-if
          │                     │
          └──────────┬──────────┘
                     ▼
        data/processed/looker/*.csv  → Looker Studio
```

**Built to move to Google Cloud.** Everything runs locally for now, but it's set up so the move to Google Cloud is a configuration change rather than a rewrite. The `landing/` folder uses the same layout a Cloud Storage bucket would. `warehouse/bq_load.py` does the same job as `load.py` but loads into BigQuery. The dbt project has a BigQuery profile ready to go, and the SQL sticks to what both DuckDB and BigQuery understand. The BigQuery path is written but isn't run in this version.

**Scraping runs on its own.** A GitHub Actions workflow runs both scrapers every day at 13:00 UTC and commits that day's data to the repo. That way the price history keeps growing without depending on my laptop being on.

## What gets added to the repo

```
scrape/
  base.py            Saves each run's data and a log record of how the run went
  webscraper_io.py   Selenium scraper for the test store
  open_prices.py     Open Prices API client
  parsers.py         Turns raw HTML and JSON into clean records (tested on saved pages)
warehouse/
  load.py            Loads the landing files into DuckDB
  bq_load.py         The same, for Cloud Storage to BigQuery (not run yet)
dbt/
  models/staging/    One cleaned-up model per source
  snapshots/         A dated history of every price change
  models/marts/      Products, daily sales, promo events, competitor price index, scrape health
  models/sources.yml Warns if the scraped data stops arriving
src/pricing/
  promo.py           Finds promotions and measures lift, the dip afterwards, and profit
  elasticity.py      Measures price sensitivity
  export.py          Writes the files for Looker Studio
src/forecast.py      Gains optional price and promo inputs (off by default, so 1.0 is unchanged)
src/backtest.py      Tests the forecast over several time periods
.github/workflows/scrape.yml   The daily scraping job
tests/               New tests for each module, plus saved pages to test against
docs/design/         This file
```

## Methods

### Spotting a promotion

For the Open Prices data this is easy, because each price says whether it was discounted. M5 has no promo field, so 2.0 works it out from the price. A week counts as a promotion when the price is at least 10% below the product's highest regular price over the previous 8 weeks. The discount depth is how far below that regular price it sits.

### Measuring promo lift

The simple way to measure lift is to compare sales during a promotion with sales in the weeks before it. The problem is that this credits the promotion with anything else that happened that week. If a promo ran over Thanksgiving, the holiday bump gets counted as promo lift.

To avoid that, 2.0 also looks at similar products in the same department that weren't on promotion at the time (a method called difference-in-differences). If those products also went up 15% that week, then 15% of the bump had nothing to do with the promo. Lift is the extra growth beyond what the comparison products saw.

### Whether the promotion made money

A promotion can lift sales and still lose money. Two things eat into it. The first is the discount itself: every unit that would have sold anyway now sells for less. The second is that shoppers often stock up during a promo and then buy less for the next couple of weeks.

So for each promotion, 2.0 measures the dip in the two weeks afterwards, using the same comparison as above. Then it adds up the promo profit:

- **Plus** the margin earned on everything sold during the promo, at the discounted price.
- **Minus** the margin those sales would have earned at the regular price anyway.
- **Minus** the margin lost during the dip afterwards.

M5 has no cost data, so this assumes a 30% gross margin, set in `src/config.py`. Because that's an assumption, the dashboard also shows the results at 25% and 35%, so you can see whether the conclusions hold.

### Price sensitivity (elasticity)

For each product, 2.0 fits a regression of weekly units sold on price, using logs of both. That way the price coefficient reads directly as "a 1% price change moves demand by this many percent". It also controls for promotions and for the time of year, so seasonal patterns aren't mistaken for price effects.

Each estimate comes with a 95% confidence interval. Some products only changed price a few times, which makes their estimates noisy. For those, the estimate is pulled towards the department average, and the noisier the estimate, the further it's pulled. Products with fewer than four distinct prices just get the department average, and they're flagged as such.

### Forecasting with price and promo

The 1.0 Prophet model gets two new optional inputs: price and promo. Future prices are treated as known, which is realistic because retailers plan their promotions in advance.

1.0 was tested on a single 90-day period. 2.0 tests on four separate 28-day periods instead, each one ending a month before the last. Three models are compared in each period: the simple same-weekday baseline, Prophet as in 1.0, and Prophet with price and promo. If adding price and promo doesn't help, the README will say so.

### Stock levels ahead of a promotion

This reuses the 1.0 safety stock and reorder point calculations. The new part answers a planner's question: "If we run a 20% promotion next week, how much should the reorder point go up?" It uses the price sensitivity and promo effect from above to estimate demand at the discounted price, then sizes the buffer from the new model's forecast errors.

### Competitor price index

For every product (by barcode) seen in at least two US stores within the same 30 days, 2.0 compares each store's price with the middle price across stores. An index of 100 means a store prices right in the middle, and 110 means it's 10% more expensive. These are rolled up by store and by category, alongside how often each store discounts and by how much.

## Keeping the data trustworthy

Scrapers break quietly. A website changes its layout and suddenly you're collecting empty prices without noticing. So every scrape run writes a log record: how many pages it visited, how many rows it got, how many pages failed to parse, how many prices were missing, and how long it took. These feed a scrape-health table, which shows up as a tile on the dashboard.

dbt adds its own checks on every build. Keys must be unique and not missing, prices must be positive, discounts must be between 0% and 90%, and a warning fires if the scraped data hasn't arrived in 36 hours (an error after 72).

## Dashboard

The Looker Studio report has four pages, built from the files in `data/processed/looker/`:

1. **Promo scorecard:** profit for each promotion and department, lift against the dip afterwards, and how the results change with the margin assumption.
2. **Price sensitivity:** each product's elasticity with its confidence interval, before and after shrinking towards the department average.
3. **Forecast and stock:** forecast accuracy for each model across the four test periods, and the promo what-if for reorder points.
4. **Market and pipeline:** the competitor price index by store, promo frequency, and the scrape-health tile.

The link and a screenshot will go in the README, like the Tableau link for 1.0.

## Testing

The tests check that the maths does what it should, without depending on live websites:

- **Parsers** run against saved copies of real pages, so the tests never hit a live site.
- **Promo lift** is tested on made-up data with a known 40% lift and 10% dip, to check the method recovers them. Promo profit is checked against a calculation done by hand.
- **Elasticity** is tested on made-up data with a known elasticity of −1.5, to check the estimate lands within its confidence interval.
- **The backtest** checks that no test period overlaps the data it was trained on.
- **The forecast** checks that calling it the 1.0 way still gives exactly the 1.0 result.
- **dbt** builds and runs its checks in CI on a small sample database.
- All the existing 1.0 tests have to keep passing.

## Build order

1. The scrapers, landing files, loader and the daily GitHub Action. These come first so the price history starts growing straight away.
2. The dbt models, price-history snapshot and data checks.
3. Promo lift, promo profit and price sensitivity.
4. The forecast with price and promo, the rolling backtest and the promo what-if.
5. The Looker Studio exports and dashboard, then the README for 2.0.

## Not in this version

- Running on real Cloud Storage and BigQuery. The code is written but not run yet.
- How one product's price affects another's sales (cross-price effects and cannibalisation).
- Matching M5 products to real ones. M5 hides product names, so any comparison with Open Prices data is by category only.
- Working out the best promo price.

## Limitations

- **Price sensitivity is measured, not tested.** Prices in M5 weren't set at random. Retailers tend to discount products that are already selling slowly, which probably makes demand look less price-sensitive than it really is. The elasticities describe what happened rather than proving cause and effect.
- **Promo profit depends on an assumed margin.** M5 has no costs, so profit uses a 30% gross margin. The dashboard shows 25% and 35% too.
- **Open Prices coverage is uneven.** It's crowdsourced, mostly from the Bay Area, so some stores and dates have far more data than others.
- **The test store's prices never change.** That source shows the pipeline works, but it adds nothing to the analysis.
