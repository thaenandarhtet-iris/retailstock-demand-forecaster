"""
Load the landing files and the M5 subset into DuckDB, as the raw layer dbt builds on.

Usage:
    python -m warehouse.load
"""
from pathlib import Path

import duckdb
import pandas as pd

from src.config import LANDING, M5_DEPT, M5_DIR, M5_SKUS, M5_STORE, WAREHOUSE

PRICE_COLUMNS = {
    "source": "VARCHAR", "sku": "VARCHAR", "name": "VARCHAR", "category": "VARCHAR", "store": "VARCHAR",
    "store_name": "VARCHAR", "price": "DOUBLE", "was_price": "DOUBLE", "is_promo": "BOOLEAN",
    "observed_on": "DATE", "scraped_at": "TIMESTAMP", "price_id": "VARCHAR",
}
RUN_COLUMNS = {
    "source": "VARCHAR", "started_at": "TIMESTAMP", "pages": "INTEGER", "rows": "INTEGER",
    "parse_failures": "INTEGER", "null_prices": "INTEGER", "duration_s": "DOUBLE",
}


def select_m5_items(prices: pd.DataFrame, n: int = M5_SKUS) -> list[str]:
    """The n items whose price changed most often; elasticity can't be measured on a price that never moves."""
    variation = prices.groupby("item_id").sell_price.nunique()
    return sorted(variation.sort_values(ascending=False, kind="stable").index[:n])


def _load_jsonl(con, table: str, files: list[Path], columns: dict[str, str]):
    """Fixed column types, so a day where one source lacks a field still lines up with the others."""
    if files:
        paths = ", ".join(f"'{f}'" for f in files)
        con.sql(f"create or replace table raw.{table} as select * from read_json([{paths}], "
                f"columns={columns}, format='newline_delimited')")
    else:
        con.sql(f"create or replace table raw.{table} ({', '.join(f'{c} {t}' for c, t in columns.items())})")


def load_m5(m5_dir: Path, n: int = M5_SKUS) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    calendar = pd.read_csv(m5_dir / "calendar.csv", parse_dates=["date"])
    prices = pd.read_csv(m5_dir / "sell_prices.csv")
    prices = prices[(prices.store_id == M5_STORE) & prices.item_id.str.startswith(M5_DEPT + "_")]
    items = select_m5_items(prices, n)
    prices = prices[prices.item_id.isin(items)]

    sales = pd.read_csv(m5_dir / "sales_train_evaluation.csv")
    sales = sales[(sales.store_id == M5_STORE) & sales.item_id.isin(items)]
    sales = sales.melt(id_vars=["item_id"], value_vars=[c for c in sales.columns if c.startswith("d_")],
                       var_name="d", value_name="units")
    sales = sales.merge(calendar[["d", "date"]], on="d")[["item_id", "date", "units"]]
    return sales, prices, calendar


def load_all(db: Path = WAREHOUSE, landing: Path = LANDING, m5_dir: Path = M5_DIR, n: int = M5_SKUS) -> dict[str, int]:
    db.parent.mkdir(parents=True, exist_ok=True)
    sales, prices, calendar = load_m5(m5_dir, n)
    with duckdb.connect(str(db)) as con:
        con.sql("create schema if not exists raw")
        _load_jsonl(con, "scraped_prices", sorted(landing.glob("source=*/date=*/part-*.jsonl")), PRICE_COLUMNS)
        _load_jsonl(con, "scrape_runs", sorted(landing.glob("source=_runs/date=*/*.jsonl")), RUN_COLUMNS)
        for table, frame in {"m5_sales_long": sales, "m5_prices": prices, "m5_calendar": calendar}.items():
            con.register("frame", frame)
            con.sql(f"create or replace table raw.{table} as select * from frame")
            con.unregister("frame")
        tables = ["scraped_prices", "scrape_runs", "m5_sales_long", "m5_prices", "m5_calendar"]
        return {t: con.execute(f"select count(*) from raw.{t}").fetchone()[0] for t in tables}


def main():
    for table, rows in load_all().items():
        print(f"raw.{table:<15} {rows:>9,} rows")


if __name__ == "__main__":
    main()
