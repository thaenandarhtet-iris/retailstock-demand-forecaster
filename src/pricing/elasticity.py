"""
Own-price elasticity per SKU: how much weekly demand moves, in percent, when the price moves 1%.

Prices in M5 weren't set at random (retailers tend to discount slow sellers), so these describe what happened
rather than proving cause and effect.

Usage:
    python -m src.pricing.elasticity
"""
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from src.config import PROCESSED
from src.pricing.promo import flag_promos, load_weekly

MIN_PRICES = 4


def fit_sku(weekly: pd.DataFrame) -> dict:
    """
    log(1 + units) on log(price), a promo flag and week-of-year, with robust (HC1) standard errors.
    log1p keeps zero-sales weeks in the fit.
    """
    n_prices = weekly.sell_price.nunique()
    if n_prices < MIN_PRICES:
        return {"beta": np.nan, "se": np.nan, "ci_low": np.nan, "ci_high": np.nan, "promo_coef": 0.0,
                "n_prices": n_prices}
    data = weekly.assign(is_promo=weekly.is_promo.astype(float))
    model = smf.ols("np.log1p(units) ~ np.log(sell_price) + is_promo + C(week_of_year)", data=data).fit(cov_type="HC1")
    term = "np.log(sell_price)"
    low, high = model.conf_int().loc[term]
    return {"beta": model.params[term], "se": model.bse[term], "ci_low": low, "ci_high": high,
            "promo_coef": model.params["is_promo"], "n_prices": n_prices}


def shrink(fits: pd.DataFrame) -> pd.DataFrame:
    """
    Pull noisy estimates towards the department average (empirical Bayes): the larger an SKU's standard error
    compared with the real spread between SKUs, the further it moves. SKUs with too few prices just get the average.
    """
    usable = fits.n_prices >= MIN_PRICES
    dept_mean = fits.loc[usable, "beta"].mean()
    tau2 = max(fits.loc[usable, "beta"].var() - (fits.loc[usable, "se"] ** 2).mean(), 1e-6)
    weight = np.where(usable, tau2 / (tau2 + fits.se.fillna(np.inf) ** 2), 0.0)
    return fits.assign(
        weight=weight,
        beta_shrunk=np.where(usable, weight * fits.beta + (1 - weight) * dept_mean, dept_mean),
        pooled=~usable,
    )


def run(weekly: pd.DataFrame | None = None) -> pd.DataFrame:
    weekly = load_weekly() if weekly is None else weekly
    flagged = flag_promos(weekly[["item_id", "wm_yr_wk", "sell_price"]])
    data = weekly.merge(flagged[["item_id", "wm_yr_wk", "is_promo"]], on=["item_id", "wm_yr_wk"])
    data = data[data.days == 7].assign(week_of_year=lambda d: d.wm_yr_wk % 100)
    fits = pd.DataFrame([{"item_id": item, **fit_sku(g)} for item, g in data.groupby("item_id")])
    return shrink(fits)


def main():
    fits = run()
    fits.to_csv(PROCESSED / "elasticity.csv", index=False)
    usable = fits[~fits.pooled]
    print(f"{len(fits)} SKUs: {len(usable)} estimated, {fits.pooled.sum()} given the department average")
    print(f"Median elasticity {usable.beta.median():.2f} raw, {fits.beta_shrunk.median():.2f} after shrinkage")
    print(f"Price-elastic (beta < -1): {(fits.beta_shrunk < -1).mean():.0%}  |  "
          f"95% CI excludes zero: {((usable.ci_high < 0) | (usable.ci_low > 0)).mean():.0%}")


if __name__ == "__main__":
    main()
