import pandas as pd

from src.pricing import export

FILES = ["promo_events", "elasticity", "backtest", "promo_whatif", "price_index", "scrape_health"]


def test_export_writes_all_files(tmp_path, monkeypatch):
    frames = {
        "promo_events": pd.DataFrame({"event_id": [0], "item_id": ["FOODS_3_001"], "profit_30": [1.0]}),
        "elasticity": pd.DataFrame({"item_id": ["FOODS_3_001"], "beta_shrunk": [-1.5], "promo_coef": [0.2]}),
        "backtest": pd.DataFrame({"origin": ["2016-04-24"], "item_id": ["FOODS_3_001"],
                                  "model": ["prophet_price_promo"], "error_std": [3.0]}),
        "recent_demand": pd.DataFrame({"item_id": ["FOODS_3_001"], "daily_units": [10.0]}),
        "price_index": pd.DataFrame({"store": ["3998"], "price_index": [98.4]}),
        "scrape_health": pd.DataFrame({"run_date": ["2026-10-25"], "rows": [10]}),
    }
    monkeypatch.setattr(export, "load_inputs", lambda: frames)
    export.run(looker=tmp_path)
    for name in FILES:
        assert len(pd.read_csv(tmp_path / f"{name}.csv")) == 1
    whatif = pd.read_csv(tmp_path / "promo_whatif.csv")
    assert whatif.reorder_point_promo.iloc[0] > whatif.reorder_point_now.iloc[0]


def test_whatif_clips_implausible_elasticity():
    inputs = {
        "elasticity": pd.DataFrame({"item_id": ["up", "huge"], "beta_shrunk": [18.0, -16.0], "promo_coef": [0.0, 0.0]}),
        "backtest": pd.DataFrame({"origin": ["2016-04-24"] * 2, "item_id": ["up", "huge"],
                                  "model": ["prophet_price_promo"] * 2, "error_std": [0.0, 0.0]}),
        "recent_demand": pd.DataFrame({"item_id": ["up", "huge"], "daily_units": [10.0, 10.0]}),
    }
    whatif = export.promo_whatif(inputs, depth=0.2).set_index("item_id")
    assert list(whatif.beta_used) == [0.0, -4.0]
    assert whatif.beta_clipped.all()
    assert whatif.loc["up", "reorder_point_promo"] == whatif.loc["up", "reorder_point_now"]
