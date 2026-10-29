"""
Write the CSVs the Looker Studio report reads, one file per data source.

Usage:
    python -m src.pricing.export
"""
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from src.config import LEAD_TIME_DAYS, LOOKER, PROCESSED, WAREHOUSE
from src.inventory import promo_reorder_point

WHATIF_DEPTH = 0.20
# Grocery own-price elasticities sit roughly between -4 and 0. Estimates outside that come from tiny,
# confounded price moves, so the what-if clips to it and flags the SKU rather than planning stock on them.
PLAUSIBLE_BETA = (-4.0, 0.0)


def load_inputs() -> dict[str, pd.DataFrame]:
    with duckdb.connect(str(WAREHOUSE), read_only=True) as con:
        warehouse = {
            "recent_demand": con.sql("""
                select item_id, avg(units) as daily_units from main.fct_daily_sku
                where date > (select max(date) from main.fct_daily_sku) - interval 28 day group by item_id
            """).df(),
            "price_index": con.sql("select * from main.mart_competitor_price_index").df(),
            "scrape_health": con.sql("select * from main.mart_scrape_health order by run_date").df(),
        }
    files = {name: pd.read_csv(PROCESSED / f"{name}.csv") for name in ("promo_events", "elasticity", "backtest")}
    return {**files, **warehouse}


def promo_whatif(inputs: dict[str, pd.DataFrame], depth: float = WHATIF_DEPTH) -> pd.DataFrame:
    """Each SKU's reorder point now, and ahead of a promotion at `depth` off."""
    errors = inputs["backtest"]
    latest = errors[(errors.model == "prophet_price_promo") & (errors.origin == errors.origin.max())]
    data = (inputs["recent_demand"]
            .merge(inputs["elasticity"][["item_id", "beta_shrunk", "promo_coef"]], on="item_id")
            .merge(latest[["item_id", "error_std"]], on="item_id"))
    data["beta_used"] = data.beta_shrunk.clip(*PLAUSIBLE_BETA)
    data["beta_clipped"] = data.beta_used != data.beta_shrunk
    lead_demand = data.daily_units * LEAD_TIME_DAYS
    data["reorder_point_now"] = [promo_reorder_point(d, b, 0, 0, s) for d, b, s in
                                 zip(lead_demand, data.beta_used, data.error_std)]
    data["reorder_point_promo"] = [promo_reorder_point(d, b, p, depth, s) for d, b, p, s in
                                   zip(lead_demand, data.beta_used, data.promo_coef, data.error_std)]
    data["promo_depth"] = depth
    data["increase_pct"] = np.round((data.reorder_point_promo / data.reorder_point_now - 1) * 100, 1)
    return data


def run(looker: Path = LOOKER):
    inputs = load_inputs()
    looker.mkdir(parents=True, exist_ok=True)
    outputs = {
        "promo_events": inputs["promo_events"],
        "elasticity": inputs["elasticity"],
        "backtest": inputs["backtest"],
        "promo_whatif": promo_whatif(inputs),
        "price_index": inputs["price_index"],
        "scrape_health": inputs["scrape_health"],
    }
    for name, frame in outputs.items():
        frame.to_csv(looker / f"{name}.csv", index=False)
    return outputs


def main():
    outputs = run()
    whatif = outputs["promo_whatif"]
    print(f"Wrote {len(outputs)} files to {LOOKER.relative_to(PROCESSED.parent.parent)}")
    print(f"A {WHATIF_DEPTH:.0%} promo raises the median reorder point by {whatif.increase_pct.median():.0f}% "
          f"({whatif.beta_clipped.sum()} of {len(whatif)} SKUs had their elasticity clipped to {PLAUSIBLE_BETA})")


if __name__ == "__main__":
    main()
