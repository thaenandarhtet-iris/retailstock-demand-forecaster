# RetailStock 2.0 Implementation Plan

**Goal:** Add price and promo intelligence to RetailStock: scrapers and a daily job, a DuckDB + dbt warehouse, promo lift/profit and elasticity on M5, a price/promo-aware forecast with a rolling backtest, and Looker Studio exports.

**Architecture:** Scrapers write JSONL partitions into a GCS-shaped `landing/` folder. `warehouse/load.py` loads them and the M5 CSVs into DuckDB, and dbt builds staging, snapshot and mart tables. Python modules in `src/pricing/` and `src/backtest.py` read the marts and write CSVs to `data/processed/looker/`.

**Tech stack:** Python 3.11, pandas, numpy, statsmodels, prophet (existing), selenium 4 (Selenium Manager handles the driver), requests, duckdb, dbt-duckdb, dbt_utils, pytest.

**Spec:** `docs/design/2026-09-30-retailstock-2.0-design.md`

**Deadline:** two days, 2026-10-27. Day 1 is Tasks 1–5, Day 2 is Tasks 6–10.

## Global constraints

- Nothing in 1.0 changes behaviour. The existing 11 tests stay green, and `forecast_sku(...)` with no `regressors` returns exactly what it does today.
- M5 subset: store `CA_1`, department `FOODS_3`, the 200 items with the most distinct weekly prices.
- Promo rule (M5): `sell_price <= 0.90 * regular_price`, where regular price is the max price over the previous 8 non-promo weeks.
- Promo windows: 4 non-promo weeks before, 2 weeks after.
- `GROSS_MARGIN = 0.30` in `src/config.py`; exports also report 0.25 and 0.35.
- Elasticity: SKUs with fewer than 4 distinct prices get the department value and `pooled = True`.
- Backtest: 4 origins, 28-day horizon, origins 28 days apart, ending at the last M5 day.
- Open Prices: keep `location.osm_address_country_code == "US"` client-side; the price index needs ≥2 stores within 30 days.
- Scrapers send the user agent `RetailStock/2.0 (+https://github.com/thaenandarhtet-iris/retailstock-demand-forecaster)`, wait ≥1 s between requests, and only fetch listing pages.
- CI never makes network calls; parsers are tested on fixtures in `tests/fixtures/`.
- `landing/raw/m5/` and `warehouse/*.duckdb` are git-ignored. The scraped partitions are committed.
- Code and docs follow the 1.0 style: short docstrings that say why, no narrating comments.
- Writing in the README is in the voice of the 1.0 README.

## Review focus

1. **An empty or failed scrape day:** the run log still gets written with `rows = 0` and the failure count, and the loader doesn't crash on a day with no partition. Test in Task 2.
2. **Open Prices rows with a null price, a null location or a non-USD currency:** dropped by the parser, and counted in `null_prices`. Test in Task 2.
3. **An M5 item whose price never changes:** no promo events, `pooled = True` elasticity, and no division by zero in lift. Tests in Tasks 6 and 7.
4. **A promo at the very start or end of the data, without a full 4-week pre-window or 2-week post-window:** the event is skipped rather than computed on partial windows. Test in Task 6.
5. **Pre-period sales of zero:** lift % is NaN, not inf, and is excluded from department averages. Test in Task 6.

---

### Task 1: Dependencies, config and folders

**Files:**
- Modify: `requirements.txt`, `.gitignore`, `src/config.py`
- Create: `landing/.gitkeep`, `warehouse/__init__.py`, `scrape/__init__.py`, `src/pricing/__init__.py`, `tests/fixtures/.gitkeep`

- [ ] Add to `requirements.txt`: `statsmodels>=0.14`, `selenium>=4.25`, `requests>=2.32`, `duckdb>=1.1`, `dbt-duckdb>=1.9`.
- [ ] Add to `.gitignore`: `landing/raw/m5/`, `warehouse/*.duckdb`, `dbt/target/`, `dbt/logs/`, `dbt/dbt_packages/`.
- [ ] Add to `src/config.py`: `LANDING = ROOT / "landing" / "raw"`, `M5_DIR = ROOT / "data" / "raw" / "m5"`, `WAREHOUSE = ROOT / "warehouse" / "retailstock.duckdb"`, `LOOKER = PROCESSED / "looker"`, `M5_STORE = "CA_1"`, `M5_DEPT = "FOODS_3"`, `M5_SKUS = 200`, `PROMO_THRESHOLD = 0.10`, `REGULAR_WINDOW_WEEKS = 8`, `PRE_WEEKS = 4`, `POST_WEEKS = 2`, `GROSS_MARGIN = 0.30`, `USER_AGENT` (value as in Global constraints).
- [ ] Run `pip install -r requirements.txt && pytest -q`. Expected: 11 passed.
- [ ] Commit: `Add 2.0 dependencies, config and folders`

### Task 2: Parsers and run log

**Files:**
- Create: `scrape/parsers.py`, `scrape/base.py`, `tests/test_parsers.py`, `tests/test_scrape_base.py`, `tests/fixtures/webscraper_ajax.html`, `tests/fixtures/open_prices_page.json`

**Interfaces:**
- Produces: `parse_webscraper_listing(html: str, scraped_at: str) -> list[dict]` and `parse_open_prices(payload: dict) -> tuple[list[dict], int]`, which returns records plus the number of rows dropped. Record keys: `source, sku, name, category, store, price, was_price, is_promo, observed_on, scraped_at`.
- Produces: `write_partition(source: str, records: list[dict], run: dict, day: date, root: Path = LANDING) -> Path`. It writes `root/source=<source>/date=<day>/part-0.jsonl` (skipping that file when there are no records) and always appends `run` to `root/source=_runs/date=<day>/<source>.jsonl`. Run keys: `source, started_at, pages, rows, parse_failures, null_prices, duration_s`.

- [ ] Save the fixtures: one real page of `https://webscraper.io/test-sites/e-commerce/ajax/computers/laptops` after JS render (`driver.page_source`), and one real `GET /api/v1/prices?location_id=3998&size=20` response, hand-edited so it has one null price, one non-US location and one `EUR` row.
- [ ] Write the failing tests:
  - `test_webscraper_parses_every_card`: the count equals the number of `.thumbnail` cards in the fixture, every price is > 0, and `is_promo` is all False.
  - `test_open_prices_keeps_only_us_usd_priced_rows`: the 3 bad rows are dropped, `dropped == 3`, and a discounted row has `is_promo is True` with `was_price == price_without_discount`.
  - `test_write_partition_always_logs_run`: given `records=[]`, no part file exists but the run log has one line with `rows == 0`.
- [ ] Run `pytest tests/test_parsers.py tests/test_scrape_base.py -v`. Expected: FAIL (import error).
- [ ] Implement with `html.parser` from the stdlib (no BeautifulSoup) and `json`.
- [ ] Run the same tests. Expected: PASS.
- [ ] Commit: `Add scraper parsers and run log`

### Task 3: Scrapers and the daily GitHub Action

**Files:**
- Create: `scrape/webscraper_io.py`, `scrape/open_prices.py`, `.github/workflows/scrape.yml`

**Interfaces:**
- Consumes: the Task 2 parsers and `write_partition`.
- Produces: `python -m scrape.webscraper_io` and `python -m scrape.open_prices`, each writing today's partition.

- [ ] `webscraper_io.py`: headless Chrome with `USER_AGENT`. It visits the laptops, tablets and phones listings and clicks through pagination until the next button is disabled (cap 20 pages), sleeping 1 s between pages and waiting for `.thumbnail` with `WebDriverWait`. A page that times out counts as a parse failure and the run continues.
- [ ] `open_prices.py`: fetch the US location ids from `/api/v1/locations?size=100&order_by=-price_count`, filtered client-side. For each one, page through `/api/v1/prices?location_id=<id>&size=100&order_by=-date` back to 30 days ago, with a 1 s sleep between requests. Uses `requests` with a 30 s timeout.
- [ ] Run both locally. Expected: a part file and a run-log line under `landing/raw/` for each source, with Open Prices rows > 0.
- [ ] `scrape.yml`: `cron: "0 13 * * *"` plus `workflow_dispatch`, ubuntu-latest, Python 3.11, `pip install selenium requests`. It runs both scrapers, then `git add landing/raw && git commit -m "Daily scrape $(date -u +%F)" || true && git push`, with `permissions: contents: write`.
- [ ] Commit: `Add Selenium and Open Prices scrapers with daily job`

### Task 4: Load into DuckDB

**Files:**
- Create: `warehouse/load.py`, `warehouse/bq_load.py`, `tests/test_load.py`

**Interfaces:**
- Produces: `load_all(db: Path = WAREHOUSE, landing: Path = LANDING, m5_dir: Path = M5_DIR) -> dict[str, int]`, returning row counts per table. It creates `raw.scraped_prices`, `raw.scrape_runs`, `raw.m5_sales_long` (the 200-SKU subset melted to `item_id, date, units`), `raw.m5_prices` and `raw.m5_calendar`.
- Produces: `select_m5_items(prices: DataFrame, n: int = M5_SKUS) -> list[str]`.

- [ ] Write the failing tests:
  - `test_select_m5_items_prefers_price_variation`: 3 items with 1, 5 and 3 distinct prices and `n=2` give the items with 5 and 3.
  - `test_load_all_tolerates_missing_day`: a tmp landing folder with one partition plus a run log for another day with no partition gives `raw.scraped_prices` the one partition's rows and `raw.scrape_runs` 2 rows.
  - `test_load_all_m5_subset` on tiny synthetic M5 CSVs in tmp: only CA_1 FOODS_3 rows are kept.
- [ ] Implement with DuckDB's `read_json_auto(..., hive_partitioning=true)` for the landing files. For M5, filter rows before melting `sales_train_evaluation.csv` with pandas. Use `CREATE OR REPLACE TABLE` so reloads are idempotent.
- [ ] `bq_load.py`: `load_all_bigquery(project: str, dataset: str, bucket: str)`, which uses `google-cloud-bigquery` load jobs from `gs://<bucket>/raw/...` with the same table names. Import it inside the function; it isn't run or tested in this version (spec §10).
- [ ] Run `pytest tests/test_load.py -v`. Expected: PASS. Then `python -m warehouse.load` prints the row counts, with `m5_sales_long` = 200 × 1941.
- [ ] Commit: `Load landing files and M5 subset into DuckDB`

### Task 5: dbt project

**Files:**
- Create: `dbt/dbt_project.yml`, `dbt/profiles.yml.example`, `dbt/packages.yml` (dbt_utils), `dbt/models/sources.yml`, `dbt/models/staging/stg_scraped_prices.sql`, `stg_open_prices.sql`, `stg_m5_sales.sql`, `stg_m5_prices.sql`, `stg_scrape_runs.sql`, `dbt/snapshots/snap_price_history.sql`, `dbt/models/marts/dim_sku.sql`, `fct_daily_sku.sql`, `mart_competitor_price_index.sql`, `mart_scrape_health.sql`, `dbt/models/marts/schema.yml`
- Modify: `.github/workflows/tests.yml`

**Interfaces:**
- Produces: `main.fct_daily_sku(item_id, date, wm_yr_wk, units, sell_price, event_name)` and `main.mart_competitor_price_index(store, category, n_products, price_index, promo_share, avg_depth)` in DuckDB. Promo flagging stays in Python (Task 6), because the rolling regular-price rule is clearer there.
- Profiles: `retailstock` with targets `dev` (duckdb, `path: ../warehouse/retailstock.duckdb`) and `bq` (bigquery, `method: oauth`, project and dataset from env vars).

- [ ] `sources.yml`: freshness on `raw.scraped_prices` with `loaded_at_field: scraped_at`, warning after 36 hours and erroring after 72.
- [ ] `snap_price_history`: `strategy='check'`, `check_cols=['price','is_promo']`, `unique_key="source||'|'||store||'|'||sku"`.
- [ ] `mart_competitor_price_index`: per barcode and 30-day window, `price / median(price) over (partition by sku)` among skus with `count(distinct store) >= 2`. Then `median(...) * 100` per store and category.
- [ ] `schema.yml` tests: `unique` + `not_null` on `dim_sku.item_id` and `(item_id, date)` in `fct_daily_sku` via `dbt_utils.unique_combination_of_columns`; `accepted_values` on `stg_scraped_prices.source`; `dbt_utils.expression_is_true` for `sell_price > 0`.
- [ ] Run `cd dbt && dbt deps && dbt build --profiles-dir . && dbt source freshness --profiles-dir .`. Expected: all models and tests pass, and freshness passes or warns.
- [ ] CI: add a `dbt` job that builds a fixture warehouse with `python -m warehouse.load` against the `tests/fixtures/` landing data and tiny M5 CSVs (put the Task 4 synthetic CSVs in `tests/fixtures/m5/`), then runs `dbt build`.
- [ ] Commit: `Add dbt staging, price-history snapshot and marts`

### Task 6: Promo detection, lift, dip and profit

**Files:**
- Create: `src/pricing/promo.py`, `tests/test_promo.py`

**Interfaces:**
- Consumes: `fct_daily_sku` from DuckDB (read with `duckdb.connect(WAREHOUSE, read_only=True).sql(...).df()`).
- Produces:
  - `flag_promos(weekly: DataFrame) -> DataFrame`. Input columns are `item_id, wm_yr_wk, sell_price`; it adds `regular_price, is_promo, depth`.
  - `promo_events(flagged: DataFrame) -> DataFrame`, with one row per run of consecutive promo weeks: `event_id, item_id, start_wk, end_wk, depth, promo_price, regular_price`.
  - `did(daily: DataFrame, flagged: DataFrame, event: Series) -> dict` returning `{incremental_per_day, lift_pct, dip_per_day, promo_units, baseline_units, dip_units}`, or `None` when the windows are incomplete. Controls are department items with no promo in the pre, promo or post windows.
  - `promo_profit(event: dict, margin: float = GROSS_MARGIN) -> float`, with `unit_cost = regular_price * (1 - margin)`, computed as `(promo_price - cost) * promo_units - (regular_price - cost) * baseline_units + (regular_price - cost) * dip_units`. `dip_units` is negative when shoppers buy less afterwards.
  - `run() -> DataFrame`, the event table with profit at 0.25, 0.30 and 0.35.

- [ ] Write the failing tests:
  - `test_flag_promos_10pct_rule`: prices `[5,5,5,5,4.5,5]` mark only week 5, with depth 0.10; `[5,5,5,5,4.6,5]` mark nothing.
  - `test_constant_price_has_no_events`.
  - `test_did_recovers_known_lift_and_dip`: a synthetic panel of 1 treated and 5 control items at 10 units/day, a department-wide +2 shock in the promo weeks, and the treated item +4 during the promo and −1 for the 2 weeks after. Expect `incremental_per_day == approx(4)`, `lift_pct == approx(40)` and `dip_per_day == approx(-1)`.
  - `test_did_skips_incomplete_windows`: a promo in week 2 returns `None`.
  - `test_zero_pre_sales_gives_nan_lift`.
  - `test_promo_profit_by_hand`: regular 10, promo 8, margin 0.30 (cost 7), promo units 140, baseline 100, dip −10 gives `1*140 - 3*100 + 3*(-10) = -190`.
- [ ] Run `pytest tests/test_promo.py -v`. Expected: FAIL.
- [ ] Implement.
- [ ] Run the tests. Expected: PASS. Then `python -m src.pricing.promo` prints the event count, the median lift and the share of profitable events at 30%.
- [ ] Commit: `Measure promo lift, post-promo dip and promo profit`

### Task 7: Elasticity

**Files:**
- Create: `src/pricing/elasticity.py`, `tests/test_elasticity.py`

**Interfaces:**
- Consumes: `flag_promos` from Task 6.
- Produces:
  - `fit_sku(weekly: DataFrame) -> dict`, with `{beta, se, ci_low, ci_high, n_prices}`. Weekly columns are `units, sell_price, is_promo, week_of_year`. It uses statsmodels OLS `np.log1p(units) ~ np.log(sell_price) + is_promo + C(week_of_year)` with `cov_type="HC1"`.
  - `shrink(fits: DataFrame) -> DataFrame`, which adds `beta_shrunk, weight, pooled`. `tau2 = max(var(beta) - mean(se**2), 1e-6)` over SKUs with `n_prices >= 4`, `weight = tau2 / (tau2 + se**2)`, and SKUs with `n_prices < 4` get `beta_shrunk = dept mean`, `weight = 0` and `pooled = True`.
  - `run() -> DataFrame`.

- [ ] Write the failing tests:
  - `test_recovers_known_elasticity`: 150 synthetic weeks, prices drawn from 6 levels, and `units = Poisson(exp(4 - 1.5*ln p))`. Expect `ci_low < -1.5 < ci_high`.
  - `test_shrink_weight_limits`: `se=0` gives weight 1, and very large `se` gives weight ≈ 0.
  - `test_few_prices_pooled`: `n_prices=3` gives `pooled is True` and `beta_shrunk == dept mean`.
- [ ] Run `pytest tests/test_elasticity.py -v`. Expected: FAIL.
- [ ] Implement, using week-of-year from `stg_m5_sales` dates.
- [ ] Run the tests. Expected: PASS. Then `python -m src.pricing.elasticity` prints the median `beta_shrunk` and the count pooled.
- [ ] Commit: `Estimate price elasticity with shrinkage`

### Task 8: Forecast regressors and rolling backtest

**Files:**
- Modify: `src/forecast.py` (`forecast_sku`)
- Create: `src/backtest.py`, `tests/test_backtest.py`
- Modify: `tests/test_forecast.py`

**Interfaces:**
- Changes: `forecast_sku(store, item, sku, holdout_days=HOLDOUT_DAYS, regressors: tuple[str, ...] = ())`. When `regressors` is set, `sku` must carry those columns, and each one is passed to `model.add_regressor` and supplied in the future frame.
- Produces: `backtest_origins(last_day: Timestamp, n: int = 4, horizon: int = 28) -> list[Timestamp]` and `run() -> DataFrame` with columns `origin, item_id, model, wape`, where `model` is one of `baseline`, `prophet` or `prophet_price_promo`. Regressors: daily `sell_price` from the week, and `is_promo` from Task 6.

- [ ] Write the failing tests:
  - `test_default_forecast_unchanged`: on 400 synthetic days, `forecast_sku(1, 1, df)` equals `forecast_sku(1, 1, df, regressors=())`, and its columns are exactly the 1.0 set.
  - `test_regressor_forecast_runs`: with `sell_price` and `is_promo` columns, `prophet` has no NaN.
  - `test_origins_are_28_days_apart_and_end_at_last_day`: `backtest_origins(pd.Timestamp("2016-05-22"))` gives `["2016-01-31", "2016-02-28", "2016-03-27", "2016-04-24"]`. The last origin plus 28 days is the last day.
  - `test_no_test_window_overlaps_its_training`.
- [ ] Run the tests. Expected: the new ones fail and the 11 old ones pass.
- [ ] Implement. `backtest.run` reuses `seasonal_naive`, `wape` and joblib `Parallel` from 1.0.
- [ ] Run `pytest -q`. Expected: all pass. Then `python -m src.backtest` prints the mean WAPE per model and the per-origin table.
- [ ] Commit: `Add price and promo regressors and a rolling backtest`

### Task 9: Promo what-if and Looker exports

**Files:**
- Modify: `src/inventory.py` (add a function)
- Create: `src/pricing/export.py`, `tests/test_export.py`
- Modify: `tests/test_inventory.py`

**Interfaces:**
- Produces: `promo_reorder_point(base_lead_demand: float, beta: float, promo_coef: float, depth: float, error_std: float) -> float`. Demand multiplier: `(1 - depth) ** beta * exp(promo_coef)`. Returns `base_lead_demand * multiplier + safety_stock(error_std)`.
- Produces: `export.run()`, which writes `data/processed/looker/promo_events.csv`, `elasticity.csv`, `backtest.csv`, `promo_whatif.csv` (each SKU at a 20% depth: `reorder_point_now`, `reorder_point_promo`), `price_index.csv` and `scrape_health.csv`.

- [ ] Write the failing tests:
  - `test_promo_rop_no_promo_matches_base`: `depth=0` and `promo_coef=0` return `base + safety_stock(std)`.
  - `test_promo_rop_elastic_raises`: `beta=-1.5`, `depth=0.2` and `promo_coef=0` give `base * 0.8 ** -1.5 + ss`.
  - `test_export_writes_all_files` (tmp `LOOKER`, with small frames monkeypatched into each `run`): 6 files exist with headers.
- [ ] Run the tests. Expected: FAIL.
- [ ] Implement.
- [ ] Run `pytest -q`. Expected: all pass. Then `python -m src.pricing.export` writes the 6 CSVs.
- [ ] Commit: `Add promo reorder what-if and Looker Studio exports`

### Task 10: Pipeline, dashboard and README 2.0

**Files:**
- Modify: `src/pipeline.py`, `README.md`
- Create: `assets/dashboard_v2.png` (from the user)

- [ ] `pipeline.py`: add a `--v2` flag that runs `warehouse.load.load_all`, `dbt build` (via `subprocess.run([... "dbt", "build", ...], check=True, cwd=ROOT / "dbt")`), the promo, elasticity, backtest and export steps. With no flag it runs the 1.0 steps exactly as now.
- [ ] Run `python -m src.pipeline --v2` end to end. Expected: no errors and 6 Looker CSVs.
- [ ] The user builds the Looker Studio report (4 pages per spec §7) from the CSVs and sends the link and screenshot.
- [ ] README: add a "2.0: Price & Promo Intelligence" section in the 1.0 voice. It covers the problem, the three sources and why not Target, the results tables with the real numbers from the runs, how it works, run instructions including the M5 download, and the spec's Limitations. Also update the repo structure, and add a scrape-workflow badge.
- [ ] Run `pytest -q` and `cd dbt && dbt build --profiles-dir .`. Expected: all green.
- [ ] Commit: `Add 2.0 pipeline and README`
- [ ] Ask the user before pushing and opening a PR into `main`.
