import json
from datetime import date

from scrape.base import write_partition

RUN = {"source": "open_prices", "started_at": "2026-10-25T13:00:00Z", "pages": 1, "rows": 0,
       "parse_failures": 1, "null_prices": 0, "duration_s": 2.0}


def test_write_partition_always_logs_run(tmp_path):
    write_partition("open_prices", [], RUN, date(2026, 10, 25), root=tmp_path)
    assert not (tmp_path / "source=open_prices").exists()
    log = (tmp_path / "source=_runs" / "date=2026-10-25" / "open_prices.jsonl").read_text().splitlines()
    assert [json.loads(line)["rows"] for line in log] == [0]


def test_write_partition_writes_jsonl(tmp_path):
    records = [{"sku": "1", "price": 2.5}, {"sku": "2", "price": 3.0}]
    path = write_partition("open_prices", records, {**RUN, "rows": 2}, date(2026, 10, 25), root=tmp_path)
    assert path == tmp_path / "source=open_prices" / "date=2026-10-25" / "part-0.jsonl"
    assert [json.loads(line) for line in path.read_text().splitlines()] == records
