import numpy as np
import pandas as pd
import pytest

from src.inventory import lead_time_windows, plan_sku, safety_stock


def test_safety_stock_formula():
    assert safety_stock(10, lead_time_days=4, service_level=0.95) == pytest.approx(1.6449 * 10 * 2, rel=1e-3)


def test_no_variability_needs_no_safety_stock():
    assert safety_stock(0) == 0


def test_lead_time_windows_sum_consecutive_days():
    assert list(lead_time_windows(np.array([1, 2, 3, 4]), lead_time_days=2)) == [3, 5, 7]


def test_perfect_forecast_gives_full_service_with_no_buffer():
    sku = pd.DataFrame({"date": pd.date_range("2017-10-03", periods=90), "actual": 20.0, "prophet": 20.0})
    plan = plan_sku(sku, history_mean=20, history_std=5)
    assert plan["safety_stock"] == 0
    assert plan["reorder_point"] == 140
    assert plan["service_level"] == 1.0


def test_historical_method_misses_when_demand_has_grown():
    sku = pd.DataFrame({"date": pd.date_range("2017-10-03", periods=90), "actual": 30.0, "prophet": 30.0})
    plan = plan_sku(sku, history_mean=20, history_std=1)
    assert plan["historical_service_level"] == 0.0
    assert plan["service_level"] == 1.0


def test_promo_rop_no_promo_matches_base():
    from src.inventory import promo_reorder_point
    assert promo_reorder_point(100, beta=-1.5, promo_coef=0, depth=0, error_std=5) == pytest.approx(100 + safety_stock(5))


def test_promo_rop_elastic_raises():
    from src.inventory import promo_reorder_point
    expected = 100 * 0.8 ** -1.5 + safety_stock(5)
    assert promo_reorder_point(100, beta=-1.5, promo_coef=0, depth=0.2, error_std=5) == pytest.approx(expected)
