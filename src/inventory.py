"""
Turn forecasts into safety stock and reorder points, and check them against actual demand.

Usage:
    python -m src.inventory
"""
import numpy as np
import pandas as pd
from scipy.stats import norm

from src.config import LEAD_TIME_DAYS, PROCESSED, SERVICE_LEVEL
from src.data import load_sales


def safety_stock(daily_std: float, lead_time_days: int = LEAD_TIME_DAYS, service_level: float = SERVICE_LEVEL) -> float:
    """z * daily standard deviation * sqrt(lead time)."""
    return float(norm.ppf(service_level) * daily_std * np.sqrt(lead_time_days))


def promo_reorder_point(base_lead_demand: float, beta: float, promo_coef: float, depth: float, error_std: float) -> float:
    """
    Reorder point ahead of a planned promotion: lead-time demand scaled by the price effect (elasticity) and the
    extra lift from the promo itself, plus safety stock from the price-aware forecast's errors.
    """
    multiplier = (1 - depth) ** beta * np.exp(promo_coef)
    return float(base_lead_demand * multiplier + safety_stock(error_std))


def lead_time_windows(values: np.ndarray, lead_time_days: int = LEAD_TIME_DAYS) -> np.ndarray:
    """Sum of every consecutive `lead_time_days` window."""
    return np.convolve(values, np.ones(lead_time_days), mode="valid")


def plan_sku(sku: pd.DataFrame, history_mean: float, history_std: float) -> dict:
    """
    Size the buffer on the first half of the holdout and test it on the second half.

    forecast-based:  SS from the std of daily forecast errors, ROP = forecast lead-time demand + SS
    historical:      SS from the std of all past daily sales, ROP = average lead-time demand + SS
    """
    sku = sku.sort_values("date")
    half = len(sku) // 2
    calibrate, test = sku.iloc[:half], sku.iloc[half:]

    forecast_ss = safety_stock((calibrate.actual - calibrate.prophet).std())
    historical_ss = safety_stock(history_std)

    actual_lt = lead_time_windows(test.actual.to_numpy())
    forecast_rop = lead_time_windows(test.prophet.to_numpy()) + forecast_ss
    historical_rop = history_mean * LEAD_TIME_DAYS + historical_ss

    return {
        "safety_stock": round(forecast_ss, 1),
        "reorder_point": round(float(test.prophet.iloc[:LEAD_TIME_DAYS].sum()) + forecast_ss, 1),
        "historical_safety_stock": round(historical_ss, 1),
        "historical_reorder_point": round(historical_rop, 1),
        "service_level": float(np.mean(actual_lt <= forecast_rop)),
        "historical_service_level": float(np.mean(actual_lt <= historical_rop)),
    }


def run() -> pd.DataFrame:
    results = pd.read_csv(PROCESSED / "forecast_results.csv", parse_dates=["date"])
    history = load_sales()
    history = history[history.date < results.date.min()].groupby(["store", "item"]).sales.agg(["mean", "std"])

    rows = []
    for (store, item), sku in results.groupby(["store", "item"]):
        stats = history.loc[(store, item)]
        rows.append({"store": store, "item": item, **plan_sku(sku, stats["mean"], stats["std"])})
    return pd.DataFrame(rows)


def main():
    plan = run()
    plan.to_csv(PROCESSED / "replenishment_table.csv", index=False)
    target = f"{SERVICE_LEVEL:.0%}"
    print(f"{len(plan)} SKUs, {LEAD_TIME_DAYS}-day lead time, {target} target service level")
    print(f"Forecast-based:  service level {plan.service_level.mean():.1%}, total safety stock {plan.safety_stock.sum():,.0f} units")
    print(f"Historical std:  service level {plan.historical_service_level.mean():.1%}, total safety stock {plan.historical_safety_stock.sum():,.0f} units")


if __name__ == "__main__":
    main()
