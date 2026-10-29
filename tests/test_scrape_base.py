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


def test_failed_run_still_logs_and_reraises(tmp_path):
    import pytest
    from scrape.base import run_and_log

    def broken():
        raise RuntimeError("site down")

    with pytest.raises(RuntimeError):
        run_and_log("webscraper_io", broken, day=date(2026, 10, 25), root=tmp_path)
    run = json.loads((tmp_path / "source=_runs" / "date=2026-10-25" / "webscraper_io.jsonl").read_text())
    assert run["rows"] == 0 and run["parse_failures"] == 1 and "site down" in run["error"]


def test_open_prices_counts_failed_location_and_keeps_others():
    import requests
    from scrape import open_prices

    class Session:
        def get(self, url, params, timeout):
            if url.endswith("locations"):
                return Resp({"items": [{"id": 1, "osm_address_country_code": "US"},
                                       {"id": 2, "osm_address_country_code": "US"}]})
            if params["location_id"] == 1:
                raise requests.ConnectionError("boom")
            return Resp({"items": [], "pages": 1})

    class Resp:
        def __init__(self, payload):
            self.payload = payload
        def raise_for_status(self):
            pass
        def json(self):
            return self.payload

    open_prices.DELAY_S = 0
    records, stats = open_prices.scrape(Session(), "2026-10-25T13:00:00Z", since="2026-09-25")
    assert stats["parse_failures"] == 1 and stats["pages"] == 1
