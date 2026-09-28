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
