"""
Rolling-origin backtest on M5: does knowing price and promo make the forecast better?

1.0 was scored on one 90-day period. Here each model is scored on four 28-day periods, so one unusual
month can't decide the result.

Usage:
    python -m src.backtest
"""
import duckdb
import pandas as pd
from joblib import Parallel, delayed

from src.config import PROCESSED, WAREHOUSE
from src.forecast import forecast_sku
from src.metrics import wape
from src.pricing.promo import flag_promos, load_weekly

HORIZON = 28
ORIGINS = 4
MODELS = {"prophet": (), "prophet_price_promo": ("sell_price", "is_promo")}


def backtest_origins(last_day: pd.Timestamp, n: int = ORIGINS, horizon: int = HORIZON) -> list[pd.Timestamp]:
    """Last training day of each period; the latest one's test window ends on `last_day`."""
    return [last_day - pd.Timedelta(days=horizon * k) for k in range(n, 0, -1)]


def window(sku: pd.DataFrame, origin: pd.Timestamp, horizon: int = HORIZON) -> pd.DataFrame:
    """Everything up to the origin for training, then `horizon` days to test on."""
    return sku[sku.date <= origin + pd.Timedelta(days=horizon)]


def load_daily(db=WAREHOUSE) -> pd.DataFrame:
    with duckdb.connect(str(db), read_only=True) as con:
        daily = con.sql("select item_id, date, wm_yr_wk, units as sales, sell_price from main.fct_daily_sku").df()
    flags = flag_promos(load_weekly(db)[["item_id", "wm_yr_wk", "sell_price"]])
    return daily.merge(flags[["item_id", "wm_yr_wk", "is_promo"]], on=["item_id", "wm_yr_wk"])


def score_item(item_id: str, sku: pd.DataFrame, origin: pd.Timestamp) -> list[dict]:
    sliced = window(sku, origin)
    rows = []
    for model, regressors in MODELS.items():
        result = forecast_sku(0, item_id, sliced, holdout_days=HORIZON, regressors=regressors)
        if model == "prophet":
            rows.append(_row(origin, item_id, "baseline", result.actual, result.baseline))
        rows.append(_row(origin, item_id, model, result.actual, result.prophet))
    return rows


def _row(origin, item_id, model, actual, forecast) -> dict:
    """Per-SKU WAPE is undefined when a slow seller sold nothing, so totals are kept for the overall WAPE."""
    actual_total = float(actual.sum())
    return {"origin": origin.date(), "item_id": item_id, "model": model,
            "wape": wape(actual, forecast) if actual_total > 0 else float("nan"),
            "abs_error": float((actual - forecast).abs().sum()), "actual": actual_total,
            "error_std": float((actual - forecast).std())}


def run(daily: pd.DataFrame | None = None, n_jobs: int = -1) -> pd.DataFrame:
    daily = load_daily() if daily is None else daily
    daily["date"] = pd.to_datetime(daily.date)
    origins = backtest_origins(daily.date.max())
    jobs = (delayed(score_item)(item, sku.sort_values("date"), origin)
            for item, sku in daily.groupby("item_id") for origin in origins)
    return pd.DataFrame([row for rows in Parallel(n_jobs=n_jobs)(jobs) for row in rows])


def main():
    results = run()
    results.to_csv(PROCESSED / "backtest.csv", index=False)
    totals = results.groupby(["origin", "model"])[["abs_error", "actual"]].sum()
    by_origin = (totals.abs_error / totals.actual * 100).unstack("model").round(1)
    print(f"Overall WAPE over {ORIGINS} periods of {HORIZON} days")
    print(by_origin.to_string())
    print("Average", by_origin.mean().round(1).to_dict())


if __name__ == "__main__":
    main()
