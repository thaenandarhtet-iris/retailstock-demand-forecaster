import json
from datetime import date
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
