import json
from datetime import date, datetime, timezone
from pathlib import Path

from src.config import LANDING


def _append_jsonl(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def write_partition(source: str, records: list[dict], run: dict, day: date, root: Path = LANDING) -> Path:
    """
    Write a day's records in the same layout a GCS bucket would use, and log the run.

    The run log is written even when there are no records, so a broken scraper shows up as a zero-row day.
    """
    part = root / f"source={source}" / f"date={day.isoformat()}" / "part-0.jsonl"
    if records:
        part.unlink(missing_ok=True)
        _append_jsonl(part, records)
    _append_jsonl(root / "source=_runs" / f"date={day.isoformat()}" / f"{source}.jsonl", [run])
    return part


def run_and_log(source: str, scrape, day: date | None = None, root: Path = LANDING) -> Path:
    """
    Run `scrape()` (which returns records and run stats) and always write the run log, even when it crashes,
    so a broken scraper shows up in scrape health instead of the day just going missing.
    """
    started = datetime.now(timezone.utc)
    day = day or started.date()
    run = {"source": source, "started_at": started.strftime("%Y-%m-%dT%H:%M:%SZ")}
    try:
        records, stats = scrape()
    except Exception as error:
        write_partition(source, [], {**run, "pages": 0, "rows": 0, "parse_failures": 1, "null_prices": 0,
                                     "duration_s": _seconds_since(started), "error": repr(error)}, day, root)
        raise
    return write_partition(source, records, {**run, "null_prices": 0, **stats, "rows": len(records),
                                             "duration_s": _seconds_since(started)}, day, root)


def _seconds_since(started: datetime) -> float:
    return round((datetime.now(timezone.utc) - started).total_seconds(), 1)
