import math

import pandas as pd
import pytest

from src.pricing.promo import did, flag_promos, promo_events, promo_profit


def _weekly_prices(prices, item="FOODS_3_001"):
    return pd.DataFrame({"item_id": item, "wm_yr_wk": range(11101, 11101 + len(prices)), "sell_price": prices})


def _panel(treated_effect, post_effect, controls=5, weeks=12, promo_weeks=(6, 7), shock=2.0):
    """10 units/day for every item; a department-wide shock in the promo weeks; the treated item gets extra on promo."""
    rows, prices = [], []
    for i in range(controls + 1):
        item = f"FOODS_3_{i:03d}"
        for w in range(weeks):
            daily = 10.0
            if w in promo_weeks:
                daily += shock + (treated_effect if i == 0 else 0)
            if i == 0 and w in (promo_weeks[-1] + 1, promo_weeks[-1] + 2):
                daily += post_effect
            rows.append({"item_id": item, "wm_yr_wk": 11101 + w, "units": daily * 7, "days": 7})
            prices.append({"item_id": item, "wm_yr_wk": 11101 + w,
                           "sell_price": 4.0 if (i == 0 and w in promo_weeks) else 5.0})
    return pd.DataFrame(rows), flag_promos(pd.DataFrame(prices))


def test_flag_promos_10pct_rule():
    flagged = flag_promos(_weekly_prices([5, 5, 5, 5, 4.5, 5]))
    assert list(flagged.is_promo) == [False, False, False, False, True, False]
    assert flagged.depth.iloc[4] == pytest.approx(0.10)
    assert not flag_promos(_weekly_prices([5, 5, 5, 5, 4.6, 5])).is_promo.any()


def test_permanent_price_cut_stops_being_a_promo():
    flagged = flag_promos(_weekly_prices([5] * 4 + [4] * 12))
    assert flagged.is_promo.iloc[4]
    assert not flagged.is_promo.iloc[-1]


def test_constant_price_has_no_events():
    assert promo_events(flag_promos(_weekly_prices([5.0] * 20))).empty


def test_promo_events_groups_consecutive_weeks():
    events = promo_events(flag_promos(_weekly_prices([5, 5, 5, 5, 4, 4, 5, 5, 4, 5])))
    assert list(zip(events.start_wk, events.end_wk)) == [(11105, 11106), (11109, 11109)]
    assert events.regular_price.iloc[0] == 5 and events.promo_price.iloc[0] == 4


def test_did_recovers_known_lift_and_dip():
    weekly, flagged = _panel(treated_effect=4.0, post_effect=-1.0)
    event = promo_events(flagged).iloc[0]
    result = did(weekly, flagged, event)
    assert result["incremental_per_day"] == pytest.approx(4.0)
    assert result["lift_pct"] == pytest.approx(40.0)
    assert result["dip_per_day"] == pytest.approx(-1.0)
    assert result["promo_units"] == pytest.approx(16 * 14)
    assert result["baseline_units"] == pytest.approx(12 * 14)
    assert result["dip_units"] == pytest.approx(-14)


def test_did_skips_incomplete_windows():
    weekly, flagged = _panel(treated_effect=4.0, post_effect=0.0, promo_weeks=(1, 2))
    assert did(weekly, flagged, promo_events(flagged).iloc[0]) is None


def test_zero_pre_sales_gives_nan_lift():
    weekly, flagged = _panel(treated_effect=4.0, post_effect=0.0)
    weekly.loc[(weekly.item_id == "FOODS_3_000") & (weekly.wm_yr_wk < 11107), "units"] = 0
    result = did(weekly, flagged, promo_events(flagged).iloc[0])
    assert math.isnan(result["lift_pct"])


def test_promo_profit_by_hand():
    event = {"regular_price": 10.0, "promo_price": 8.0, "promo_units": 140, "baseline_units": 100, "dip_units": -10}
    assert promo_profit(event, margin=0.30) == pytest.approx(1 * 140 - 3 * 100 + 3 * -10)
