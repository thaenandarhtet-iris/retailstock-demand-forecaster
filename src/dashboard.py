"""
Write the Excel workbook the Tableau dashboard reads.

Usage:
    python -m src.dashboard
"""
import numpy as np
import pandas as pd

from src.config import PROCESSED, SEED

WORKBOOK = PROCESSED / "dashboard_data.xlsx"


def simulate_current_stock(plan: pd.DataFrame, seed: int = SEED) -> pd.DataFrame:
    """There is no live inventory feed, so stock on hand is simulated at 60-130% of each reorder point."""
    rng = np.random.default_rng(seed)
    status = plan[["store", "item", "safety_stock", "reorder_point"]].copy()
    status["current_stock"] = (status.reorder_point * rng.uniform(0.6, 1.3, len(status))).round(0)
    status["needs_reorder"] = status.current_stock < status.reorder_point
    return status


def main():
    results = pd.read_csv(PROCESSED / "forecast_results.csv", parse_dates=["date"])
    metrics = pd.read_csv(PROCESSED / "forecast_metrics.csv")
    plan = pd.read_csv(PROCESSED / "replenishment_table.csv")
    status = simulate_current_stock(plan)

    with pd.ExcelWriter(WORKBOOK) as writer:
        results.to_excel(writer, sheet_name="forecast_vs_actual", index=False)
        metrics.to_excel(writer, sheet_name="accuracy_by_sku", index=False)
        status.to_excel(writer, sheet_name="reorder_status", index=False)
    print(f"Saved {WORKBOOK.relative_to(PROCESSED.parent.parent)}: {status.needs_reorder.sum()} of {len(status)} SKUs below reorder point")


if __name__ == "__main__":
    main()
