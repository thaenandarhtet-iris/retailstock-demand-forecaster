import pytest

from src.metrics import bias, mape, wape


def test_perfect_forecast_scores_zero():
    assert wape([10, 20], [10, 20]) == 0
    assert mape([10, 20], [10, 20]) == 0
    assert bias([10, 20], [10, 20]) == 0


def test_wape_weights_by_volume():
    assert wape([100, 10], [90, 20]) == pytest.approx(20 / 110 * 100)


def test_mape_skips_zero_demand_days():
    assert mape([0, 10], [5, 12]) == pytest.approx(20.0)


def test_bias_sign_means_over_forecast():
    assert bias([10, 10], [12, 12]) == 2
    assert bias([10, 10], [8, 8]) == -2
