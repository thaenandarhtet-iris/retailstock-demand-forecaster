"""
Pull the last 30 days of US shelf prices from the Open Prices API (Open Food Facts, ODbL licence).

Usage:
    python -m scrape.open_prices
"""
import time
from datetime import datetime, timedelta, timezone

import requests

from scrape.base import write_partition
from scrape.parsers import parse_open_prices
from src.config import USER_AGENT

API = "https://prices.openfoodfacts.org/api/v1"
LOOKBACK_DAYS = 30
DELAY_S = 1.0


def _get(session: requests.Session, path: str, **params) -> dict:
    time.sleep(DELAY_S)
    response = session.get(f"{API}/{path}", params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def us_location_ids(session: requests.Session) -> list[int]:
    """The country filter is ignored by the API, so filter the busiest locations here."""
    locations = _get(session, "locations", size=100, order_by="-price_count")["items"]
    return [l["id"] for l in locations if l.get("osm_address_country_code") == "US"]


def scrape(session: requests.Session, scraped_at: str, since: str) -> tuple[list[dict], dict]:
    records, pages, dropped = [], 0, 0
    for location_id in us_location_ids(session):
        page = 1
        while True:
            payload = _get(session, "prices", location_id=location_id, size=100, order_by="-date", page=page)
            pages += 1
            batch, n_dropped = parse_open_prices(payload, scraped_at)
            records += [r for r in batch if r["observed_on"] >= since]
            dropped += n_dropped
            oldest = min((i["date"] for i in payload["items"]), default=since)
            if page >= payload.get("pages", 1) or oldest < since:
                break
            page += 1
    return records, {"pages": pages, "parse_failures": 0, "null_prices": dropped}


def main():
    started = datetime.now(timezone.utc)
    scraped_at = started.strftime("%Y-%m-%dT%H:%M:%SZ")
    since = (started - timedelta(days=LOOKBACK_DAYS)).date().isoformat()
    with requests.Session() as session:
        session.headers["User-Agent"] = USER_AGENT
        records, stats = scrape(session, scraped_at, since)
    run = {"source": "open_prices", "started_at": scraped_at, **stats, "rows": len(records),
           "duration_s": round((datetime.now(timezone.utc) - started).total_seconds(), 1)}
    path = write_partition("open_prices", records, run, started.date())
    print(f"open_prices: {len(records)} US prices since {since} from {stats['pages']} pages -> {path}")


if __name__ == "__main__":
    main()
