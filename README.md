# RetailStock: Demand Forecasting & Safety-Stock Planner

[![tests](https://github.com/thaenandarhtet-iris/retailstock-demand-forecaster/actions/workflows/tests.yml/badge.svg)](https://github.com/thaenandarhtet-iris/retailstock-demand-forecaster/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Forecasts daily demand for 500 retail SKUs (10 stores × 50 items, five years of sales) and turns the forecasts into safety stock and reorder points. It then checks those inventory levels against what customers actually bought.

**Live dashboard:** [Tableau Public](https://public.tableau.com/views/RetailStockDemandandReplenishmentDashboard/RetailstockDemandReplenishmentDashboard)

![Dashboard](assets/dashboard.png)

## The problem

A retailer has to balance two costs: running out of stock and losing sales, or holding too much and tying up cash. The buffer you need, the safety stock, depends on how *uncertain* demand is. The question this project answers is how much of that uncertainty a good forecast can remove.

## Results

Measured on the last 90 days of data (October to December 2017), which no model saw during training.

**Forecasting.** One Prophet model per SKU, with weekly and yearly seasonality, compared with a simple baseline that repeats the last week of sales:

| | Prophet | Baseline |
|---|---|---|
| Overall WAPE | **11.6%** | 21.3% |
| SKUs where it's more accurate | **500 of 500** | |
| Median WAPE per SKU | 12.2% | 22.0% |

![WAPE per SKU](assets/wape_per_sku.png)

**Inventory.** A 7-day supplier lead time and a 95% target service level. The original version of this project sized safety stock from the spread of all past daily sales. The new version sizes it from the spread of *forecast errors*:

| Safety stock based on | Total safety stock | Service level achieved |
|---|---|---|
| Past sales variability (original) | 32,209 units | 88.0% |
| Forecast errors (new) | **16,795 units** (−48%) | **92.9%** |

![Service level per SKU](assets/service_level.png)

**Half the buffer and fewer stockouts.** The forecast already explains the weekly and yearly patterns, so the remaining uncertainty is much smaller. The original method had a second problem: it used the five-year average demand, which lags behind today's higher sales, so its reorder points were too low even with the bigger buffer.

**Why 92.9% and not 95%.** The test period includes the late-November surge, which the model under-forecasts slightly. Adding US holidays to Prophet made no real difference (93.4%), because this dataset has no genuine holiday effects. A production system would re-estimate the buffer weekly on recent errors, or raise it for peak season.

## How it works

1. **Forecast** (`src/forecast.py`): fits Prophet for each of the 500 SKUs in parallel on everything except the last 90 days, forecasts those 90 days, and scores Prophet against the baseline. WAPE (total error ÷ total sales) is the headline metric; MAPE and bias are also reported per SKU.
2. **Size inventory** (`src/inventory.py`): safety stock = z × σ × √(lead time), with z = 1.645 for 95%. The reorder point is the forecast demand over the next 7 days plus safety stock. To keep the test fair, σ is measured on the first 45 days of the holdout and the service level is checked on the other 45, so no day is used for both.
3. **Export** (`src/dashboard.py`): writes `data/processed/dashboard_data.xlsx` for Tableau. It has three sheets: forecast vs actual, accuracy per SKU, and reorder status.

The notebooks in `notebooks/` walk through the analysis with charts: EDA, forecast accuracy, safety stock, and the dashboard export.

## Run it

```bash
git clone https://github.com/thaenandarhtet-iris/retailstock-demand-forecaster.git
cd retailstock-demand-forecaster
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Download the data (see below) into `data/raw/train.csv`, then:

```bash
python -m src.pipeline    # forecast 500 SKUs, size inventory, export dashboard data (~30s on 10 cores)
pytest                    # unit tests for metrics, baseline and inventory maths
jupyter notebook notebooks/
```

## Data

The data comes from Kaggle's [Store Item Demand Forecasting Challenge](https://www.kaggle.com/competitions/demand-forecasting-kernels-only): 913,000 rows of daily sales from 2013 to 2017. The competition rules don't allow redistributing it, so it isn't included here. To get it:

1. Accept the competition rules on the Kaggle page.
2. Download `train.csv` from the Data tab, or use the Kaggle CLI:
   ```bash
   kaggle competitions download -c demand-forecasting-kernels-only -f train.csv -p data/raw
   ```

The model outputs in `data/processed/` are included, so the notebooks' results can be read without the raw data.

## Repository structure

```
src/
  config.py       Paths, lead time, service level, holdout length
  data.py         Load the Kaggle sales file
  forecast.py     Prophet per SKU, baseline, accuracy metrics
  metrics.py      WAPE, MAPE, bias
  inventory.py    Safety stock, reorder points, service-level check
  dashboard.py    Excel export for Tableau
  pipeline.py     Runs all three steps
notebooks/        01 EDA, 02 forecasting, 03 safety stock, 04 dashboard export
tests/            pytest suite
data/processed/   Forecasts, metrics, replenishment table, dashboard workbook
assets/           Dashboard screenshot and charts
```

## Limitations

- **Stock on hand is simulated.** There's no live inventory feed, so the dashboard's current stock is set at 60–130% of each reorder point to demonstrate the reorder alert. Safety stock and reorder points come from the real forecasts.
- **Fixed lead time.** The 7-day lead time is an assumption; real supplier lead times vary, which would need a larger buffer.
- **One test period.** Results come from a single 90-day holdout at the end of 2017. Rolling-origin backtesting over several periods would give more reliable estimates.
- **Clean competition data.** This dataset is known to be very regular, with no missing days or promotions. Real retail data would be noisier.

## License

[MIT](LICENSE)
