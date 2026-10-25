import pandas as pd

from src.forecast import score, seasonal_naive


def test_seasonal_naive_repeats_last_week_by_weekday():
    history = pd.Series(range(14), index=pd.date_range("2017-01-02", periods=14), dtype=float)
    horizon = pd.date_range("2017-01-16", periods=10)
    forecast = seasonal_naive(history, horizon)
    assert list(forecast.iloc[:7]) == [7, 8, 9, 10, 11, 12, 13]
    assert list(forecast.iloc[7:]) == [7, 8, 9]


def test_score_one_row_per_sku():
    results = pd.DataFrame({
        "store": [1, 1, 2, 2], "item": [1, 1, 1, 1],
        "actual": [10, 10, 5, 5], "prophet": [10, 10, 6, 4], "baseline": [8, 12, 5, 5],
    })
    metrics = score(results).set_index("store")
    assert len(metrics) == 2
    assert metrics.loc[1, "wape"] == 0
    assert metrics.loc[1, "baseline_wape"] == 20
    assert metrics.loc[2, "baseline_wape"] == 0


def _synthetic_sku(days=400):
    import numpy as np
    dates = pd.date_range("2015-01-01", periods=days)
    rng = np.random.default_rng(1)
    price = np.where((np.arange(days) // 7) % 6 == 0, 4.0, 5.0)
    sales = 20 + 3 * (dates.dayofweek >= 5) + 6 * (price == 4.0) + rng.normal(0, 1, days)
    return pd.DataFrame({"date": dates, "sales": sales, "sell_price": price, "is_promo": price == 4.0})


def test_default_forecast_unchanged():
    from src.forecast import forecast_sku
    sku = _synthetic_sku()
    default = forecast_sku(1, 1, sku[["date", "sales"]], holdout_days=28)
    explicit = forecast_sku(1, 1, sku[["date", "sales"]], holdout_days=28, regressors=())
    assert list(default.columns) == ["store", "item", "date", "actual", "prophet", "baseline"]
    pd.testing.assert_frame_equal(default, explicit)


def test_regressor_forecast_runs():
    from src.forecast import forecast_sku
    result = forecast_sku(1, 1, _synthetic_sku(), holdout_days=28, regressors=("sell_price", "is_promo"))
    assert len(result) == 28
    assert result.prophet.notna().all()
