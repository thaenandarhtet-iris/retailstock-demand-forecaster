import json
from pathlib import Path

from scrape.parsers import parse_open_prices, parse_webscraper_listing

FIXTURES = Path(__file__).parent / "fixtures"


def test_webscraper_parses_every_card():
    html = (FIXTURES / "webscraper_ajax.html").read_text()
    records = parse_webscraper_listing(html, scraped_at="2026-10-25T13:00:00Z", category="laptops")
    assert len(records) == html.count('class="card thumbnail"')
    assert all(r["price"] > 0 for r in records)
    assert not any(r["is_promo"] for r in records)
    assert records[0] == {
        "source": "webscraper_io", "sku": "60", "name": "Asus VivoBook X441NA-GA190", "category": "laptops",
        "store": "webscraper_io", "price": 295.99, "was_price": None, "is_promo": False,
        "observed_on": "2026-10-25", "scraped_at": "2026-10-25T13:00:00Z",
    }


def test_open_prices_keeps_only_us_usd_priced_rows():
    payload = json.loads((FIXTURES / "open_prices_page.json").read_text())
    records, dropped = parse_open_prices(payload, scraped_at="2026-10-25T13:00:00Z")
    assert dropped == 3
    assert len(records) == len(payload["items"]) - 3
    assert all(r["price"] > 0 and r["store"] for r in records)
    promo = next(r for r in records if r["is_promo"])
    source_row = next(i for i in payload["items"] if str(i["id"]) == promo["price_id"])
    assert promo["was_price"] == source_row["price_without_discount"]
