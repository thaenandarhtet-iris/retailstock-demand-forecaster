import numpy as np
import pandas as pd
import pytest

from src.pricing.elasticity import fit_sku, shrink


def test_recovers_known_elasticity():
    rng = np.random.default_rng(0)
    weeks = 150
    price = rng.choice([1.0, 1.25, 1.5, 1.75, 2.0, 2.5], size=weeks)
    weekly = pd.DataFrame({
        "units": rng.poisson(np.exp(6 - 1.5 * np.log(price))),
        "sell_price": price,
        "is_promo": False,
        "week_of_year": np.arange(weeks) % 52 + 1,
    })
    fit = fit_sku(weekly)
    assert fit["ci_low"] < -1.5 < fit["ci_high"]
    assert fit["n_prices"] == 6


def _fits():
    return pd.DataFrame({
        "item_id": ["a", "b", "c", "d"],
        "beta": [-1.0, -2.0, -1.5, -9.0],
        "se": [0.0, 1e6, 0.2, 0.1],
        "n_prices": [5, 5, 5, 3],
    })


def test_shrink_weight_limits():
    out = shrink(_fits()).set_index("item_id")
    assert out.loc["a", "weight"] == pytest.approx(1.0)
    assert out.loc["a", "beta_shrunk"] == pytest.approx(-1.0)
    assert out.loc["b", "weight"] == pytest.approx(0.0, abs=1e-6)


def test_few_prices_pooled():
    out = shrink(_fits()).set_index("item_id")
    dept_mean = np.mean([-1.0, -2.0, -1.5])
    assert out.loc["d", "pooled"]
    assert out.loc["d", "beta_shrunk"] == pytest.approx(dept_mean)
    assert not out.loc["a", "pooled"]
