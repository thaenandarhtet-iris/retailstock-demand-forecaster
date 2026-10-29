"""
Find promotions in the M5 price history and measure whether they paid off.

Lift is measured with difference-in-differences: the promoted item's change in sales is compared with the change
for department items that weren't on promotion at the time, so a holiday week isn't credited to the promo.

Usage:
    python -m src.pricing.promo
"""
import duckdb
import numpy as np
import pandas as pd

from src.config import GROSS_MARGIN, POST_WEEKS, PRE_WEEKS, PROCESSED, PROMO_THRESHOLD, REGULAR_WINDOW_WEEKS, WAREHOUSE

MARGINS = (0.25, 0.30, 0.35)


def flag_promos(weekly: pd.DataFrame) -> pd.DataFrame:
    """
    A week is a promotion when the price is at least 10% below the regular price: the highest non-promo price
    over the previous 8 weeks. If all 8 were promo weeks the price has simply been cut, so the regular price
    falls back to the highest price in the window and the promotion ends.
    """
    out = []
    for _, item in weekly.sort_values(["item_id", "wm_yr_wk"]).groupby("item_id", sort=False):
        prices = item.sell_price.to_numpy(float)
        is_promo = np.zeros(len(prices), bool)
        regular = prices.copy()
        for t in range(1, len(prices)):
            window = slice(max(0, t - REGULAR_WINDOW_WEEKS), t)
            normal = prices[window][~is_promo[window]]
            regular[t] = normal.max() if len(normal) else prices[window].max()
            is_promo[t] = prices[t] <= (1 - PROMO_THRESHOLD) * regular[t] + 1e-9
        out.append(item.assign(regular_price=regular, is_promo=is_promo,
                               depth=np.where(is_promo, 1 - prices / regular, 0.0)))
    return pd.concat(out, ignore_index=True)


def promo_events(flagged: pd.DataFrame) -> pd.DataFrame:
    """One row per run of consecutive promo weeks."""
    flagged = flagged.sort_values(["item_id", "wm_yr_wk"])
    starts = flagged.is_promo & ~flagged.groupby("item_id").is_promo.shift(fill_value=False)
    promo = flagged.assign(event=starts.cumsum())[flagged.is_promo]
    events = promo.groupby("event").agg(
        item_id=("item_id", "first"), start_wk=("wm_yr_wk", "min"), end_wk=("wm_yr_wk", "max"),
        depth=("depth", "mean"), promo_price=("sell_price", "mean"), regular_price=("regular_price", "first"),
    )
    return events.reset_index(drop=True).rename_axis("event_id").reset_index()


def did(weekly: pd.DataFrame, flagged: pd.DataFrame, event: pd.Series) -> dict | None:
    """
    Effects per day for one promotion, or None when there aren't 4 clean weeks before and 2 weeks after.
    `weekly` has item_id, wm_yr_wk, units and days (days on sale that week).
    """
    weeks = np.sort(flagged.wm_yr_wk.unique())
    start, end = np.searchsorted(weeks, event.start_wk), np.searchsorted(weeks, event.end_wk)
    if start < PRE_WEEKS or end + POST_WEEKS >= len(weeks):
        return None
    windows = {"pre": weeks[start - PRE_WEEKS:start], "promo": weeks[start:end + 1],
               "post": weeks[end + 1:end + 1 + POST_WEEKS]}
    span = np.concatenate(list(windows.values()))

    promo_flags = flagged[flagged.wm_yr_wk.isin(span)].pivot(index="item_id", columns="wm_yr_wk", values="is_promo")
    treated_flags = promo_flags.loc[event.item_id]
    if treated_flags.isna().any() or treated_flags[windows["pre"]].astype(bool).any():
        return None
    complete = promo_flags.notna().all(axis=1)
    controls = promo_flags.index[complete & ~promo_flags.fillna(True).any(axis=1)]
    if controls.empty:
        return None

    sums = weekly[weekly.wm_yr_wk.isin(span)].set_index(["item_id", "wm_yr_wk"])[["units", "days"]]

    def per_day(items, window):
        part = sums.loc[(items, list(window)), :].groupby(level="item_id").sum()
        return part.units / part.days

    treated = {name: per_day([event.item_id], w).iloc[0] for name, w in windows.items()}
    control = {name: per_day(list(controls), w).mean() for name, w in windows.items()}

    incremental = (treated["promo"] - treated["pre"]) - (control["promo"] - control["pre"])
    dip = (treated["post"] - treated["pre"]) - (control["post"] - control["pre"])
    promo_days = sums.loc[([event.item_id], list(windows["promo"])), "days"].sum()
    post_days = sums.loc[([event.item_id], list(windows["post"])), "days"].sum()
    promo_units = sums.loc[([event.item_id], list(windows["promo"])), "units"].sum()
    return {
        "incremental_per_day": incremental,
        "lift_pct": incremental / treated["pre"] * 100 if treated["pre"] > 0 else np.nan,
        "dip_per_day": dip,
        "promo_units": promo_units,
        "baseline_units": promo_units - incremental * promo_days,
        "dip_units": dip * post_days,
        "n_controls": len(controls),
    }


def promo_profit(event: dict, margin: float = GROSS_MARGIN) -> float:
    """
    Margin made on promo sales, minus the margin those baseline sales would have made at the regular price,
    plus the margin lost (dip_units is negative) when shoppers buy less afterwards.
    """
    cost = event["regular_price"] * (1 - margin)
    return ((event["promo_price"] - cost) * event["promo_units"]
            - (event["regular_price"] - cost) * event["baseline_units"]
            + (event["regular_price"] - cost) * event["dip_units"])


def load_weekly(db=WAREHOUSE) -> pd.DataFrame:
    with duckdb.connect(str(db), read_only=True) as con:
        return con.sql("""
            select item_id, wm_yr_wk, sum(units) as units, count(*) as days, any_value(sell_price) as sell_price
            from main.fct_daily_sku group by item_id, wm_yr_wk
        """).df()


def run(weekly: pd.DataFrame | None = None) -> pd.DataFrame:
    weekly = load_weekly() if weekly is None else weekly
    flagged = flag_promos(weekly[["item_id", "wm_yr_wk", "sell_price"]])
    rows = []
    for _, event in promo_events(flagged).iterrows():
        effects = did(weekly, flagged, event)
        if effects is None:
            continue
        row = {**event.to_dict(), **effects}
        rows.append({**row, **{f"profit_{int(m * 100)}": promo_profit(row, m) for m in MARGINS}})
    return pd.DataFrame(rows)


def main():
    events = run()
    events.to_csv(PROCESSED / "promo_events.csv", index=False)
    print(f"{len(events)} promotions with clean before/after windows")
    print(f"Median lift {events.lift_pct.median():.1f}%  |  median dip afterwards {events.dip_per_day.median():.2f} units/day")
    for m in MARGINS:
        print(f"Profitable at {m:.0%} margin: {(events[f'profit_{int(m * 100)}'] > 0).mean():.0%}")


if __name__ == "__main__":
    main()
