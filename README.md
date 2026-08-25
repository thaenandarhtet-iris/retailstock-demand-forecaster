# RetailStock Demand Forecaster & Safety-Stock Planner

Forecasts SKU-level retail demand and translates that forecast into concrete inventory decisions — safety stock levels and reorder points — using a real 5-year, 10-store, 50-item daily sales dataset.

## Problem
Retailers need to balance two costs: running out of stock (lost sales) and holding too much stock (tied-up capital, storage costs). Getting this right requires knowing not just what demand looks like on average, but how uncertain that demand is — which drives how much safety buffer to hold. This project builds an end-to-end pipeline from raw sales data to a forecast, an uncertainty-aware inventory policy, and a dashboard an ops team could actually use.

## Approach
1. EDA — cleaned and explored 913K rows of daily sales across 10 stores x 50 items; extracted per-SKU demand statistics (mean, std dev)
2. Forecasting — trained Facebook Prophet models per SKU (capturing weekly + yearly seasonality), evaluated on a held-out 90-day test window using MAPE and bias
3. Inventory policy — computed safety stock (Z-score x demand std dev over lead time) and reorder points for all 500 SKUs, assuming a 7-day lead time and 95% service level
4. Dashboard — built an interactive Tableau dashboard showing forecast accuracy and which SKUs are below their reorder point

## Results
| SKU | MAPE | Bias |
|---|---|---|
| Store 1, Item 1 | ~23% | — |
| Store 5, Item 10 | ~12% | — |
| Store 10, Item 25 | ~11% | — |

(Replace with your actual numbers from forecast_metrics.csv)

## Dashboard
![Dashboard](assets/dashboard.png)


## Tech stack
Python (pandas, NumPy, SciPy, Prophet, statsmodels, scikit-learn), Jupyter, Tableau Public

## Repo structure
- 01_eda.ipynb — data exploration + demand statistics
- 02_forecasting.ipynb — Prophet models + MAPE/bias evaluation
- 03_safety_stock.ipynb — safety stock & reorder point calculations
- 04_dashboard_export.ipynb — prepares data for Tableau
- data/raw/ — source Kaggle dataset
- data/processed/ — model outputs, dashboard-ready files
- assets/ — dashboard screenshot
- requirements.txt

## How to run
git clone https://github.com/thaenandarhtet-iris/retailstock-demand-forecaster.git
cd retailstock-demand-forecaster
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
jupyter notebook

Run notebooks in order: 01_eda.ipynb → 02_forecasting.ipynb →
