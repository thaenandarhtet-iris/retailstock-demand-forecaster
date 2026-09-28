"""
Forecast daily demand for every store-item SKU and score it on a held-out window.

Usage:
    python -m src.forecast          # all 500 SKUs
    python -m src.forecast --limit 5
"""
import argparse
import logging

import pandas as pd
from joblib import Parallel, delayed
from prophet import Prophet

from src.config import HOLDOUT_DAYS, PROCESSED
from src.data import load_sales
from src.metrics import bias, mape, wape


def seasonal_naive(history: pd.Series, horizon: pd.DatetimeIndex) -> pd.Series:
    """Baseline: each day's forecast is actual sales on the same weekday of the last training week."""
    last_week = history.iloc[-7:]
    by_weekday = dict(zip(last_week.index.dayofweek, last_week.values))
    return pd.Series([by_weekday[d.dayofweek] for d in horizon], index=horizon, dtype=float)


def forecast_sku(store: int, item: int, sku: pd.DataFrame, holdout_days: int = HOLDOUT_DAYS) -> pd.DataFrame:
    """Fit Prophet on all but the last `holdout_days` and forecast them, alongside the baseline."""
    logging.getLogger("cmdstanpy").disabled = True
    series = sku.set_index("date")["sales"].sort_index()
    train, test = series.iloc[:-holdout_days], series.iloc[-holdout_days:]

    model = Prophet(yearly_seasonality=True, weekly_seasonality=True, daily_seasonality=False)
    model.fit(pd.DataFrame({"ds": train.index, "y": train.values}))
    prophet = model.predict(pd.DataFrame({"ds": test.index}))["yhat"].clip(lower=0).to_numpy()

    return pd.DataFrame({
        "store": store,
        "item": item,
        "date": test.index,
        "actual": test.values,
        "prophet": prophet,
        "baseline": seasonal_naive(train, test.index).to_numpy(),
    })


def score(results: pd.DataFrame) -> pd.DataFrame:
    """Per-SKU accuracy for Prophet and the baseline."""
    rows = []
    for (store, item), g in results.groupby(["store", "item"]):
        rows.append({
            "store": store,
            "item": item,
            "wape": wape(g.actual, g.prophet),
            "mape": mape(g.actual, g.prophet),
            "bias": bias(g.actual, g.prophet),
            "baseline_wape": wape(g.actual, g.baseline),
        })
    return pd.DataFrame(rows)


def run(limit: int | None = None, n_jobs: int = -1) -> tuple[pd.DataFrame, pd.DataFrame]:
    sales = load_sales()
    skus = list(sales.groupby(["store", "item"]))[:limit]
    parts = Parallel(n_jobs=n_jobs)(delayed(forecast_sku)(store, item, sku) for (store, item), sku in skus)
    results = pd.concat(parts, ignore_index=True)
    return results, score(results)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, help="only forecast the first N SKUs")
    args, _ = parser.parse_known_args()

    results, metrics = run(args.limit)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    results.to_csv(PROCESSED / "forecast_results.csv", index=False)
    metrics.to_csv(PROCESSED / "forecast_metrics.csv", index=False)

    total = {"prophet": wape(results.actual, results.prophet), "baseline": wape(results.actual, results.baseline)}
    print(f"{len(metrics)} SKUs, {HOLDOUT_DAYS}-day holdout")
    print(f"Overall WAPE  Prophet {total['prophet']:.1f}%  |  same-weekday-last-week baseline {total['baseline']:.1f}%")
    print(f"Prophet beats the baseline on {(metrics.wape < metrics.baseline_wape).sum()} of {len(metrics)} SKUs")


if __name__ == "__main__":
    main()
