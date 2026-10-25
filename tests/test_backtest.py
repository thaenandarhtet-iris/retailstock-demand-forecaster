import pandas as pd

from src.backtest import backtest_origins, window


def test_origins_are_28_days_apart_and_end_at_last_day():
    origins = backtest_origins(pd.Timestamp("2016-05-22"))
    assert origins == [pd.Timestamp(d) for d in ["2016-01-31", "2016-02-28", "2016-03-27", "2016-04-24"]]
    assert origins[-1] + pd.Timedelta(days=28) == pd.Timestamp("2016-05-22")


def test_no_test_window_overlaps_its_training():
    sku = pd.DataFrame({"date": pd.date_range("2016-01-01", "2016-05-22"), "sales": 1.0})
    for origin in backtest_origins(pd.Timestamp("2016-05-22")):
        sliced = window(sku, origin)
        train, test = sliced.iloc[:-28], sliced.iloc[-28:]
        assert train.date.max() == origin
        assert test.date.min() == origin + pd.Timedelta(days=1)
        assert len(test) == 28
