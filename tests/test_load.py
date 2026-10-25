import json
from pathlib import Path

import duckdb
import pandas as pd

from warehouse.load import load_all, select_m5_items

M5_FIXTURES = Path(__file__).parent / "fixtures" / "m5"


def _write(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def _landing(root: Path) -> Path:
    record = {"source": "webscraper_io", "sku": "60", "name": "x", "category": "laptops", "store": "webscraper_io",
              "price": 295.99, "was_price": None, "is_promo": False, "observed_on": "2026-10-25",
              "scraped_at": "2026-10-25T13:00:00Z"}
    run = {"source": "webscraper_io", "started_at": "2026-10-25T13:00:00Z", "pages": 1, "rows": 1,
           "parse_failures": 0, "null_prices": 0, "duration_s": 1.0}
    _write(root / "source=webscraper_io" / "date=2026-10-25" / "part-0.jsonl", [record, {**record, "sku": "61"}])
    _write(root / "source=_runs" / "date=2026-10-25" / "webscraper_io.jsonl", [run])
    _write(root / "source=_runs" / "date=2026-10-26" / "webscraper_io.jsonl", [{**run, "rows": 0, "parse_failures": 3}])
    return root


def test_select_m5_items_prefers_price_variation():
    prices = pd.DataFrame({
        "item_id": ["a"] * 3 + ["b"] * 5 + ["c"] * 3,
        "sell_price": [1, 1, 1, 1, 2, 3, 4, 5, 1, 2, 3],
    })
    assert select_m5_items(prices, n=2) == ["b", "c"]


def test_load_all_tolerates_missing_day(tmp_path):
    db = tmp_path / "w.duckdb"
    counts = load_all(db=db, landing=_landing(tmp_path / "landing"), m5_dir=M5_FIXTURES)
    assert counts["scraped_prices"] == 2
    assert counts["scrape_runs"] == 2


def test_load_all_m5_subset(tmp_path):
    db = tmp_path / "w.duckdb"
    load_all(db=db, landing=_landing(tmp_path / "landing"), m5_dir=M5_FIXTURES)
    with duckdb.connect(str(db)) as con:
        sales = con.sql("select * from raw.m5_sales_long").df()
        prices = con.sql("select distinct store_id, item_id from raw.m5_prices").df()
    assert set(sales.item_id) == {"FOODS_3_001", "FOODS_3_002"}
    assert len(sales) == 2 * 21
    assert set(prices.store_id) == {"CA_1"} and set(prices.item_id) == {"FOODS_3_001", "FOODS_3_002"}
