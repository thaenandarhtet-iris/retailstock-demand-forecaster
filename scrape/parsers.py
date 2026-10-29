"""
Turn raw pages into price records. Pure functions, so they can be tested on saved pages.

Every record has: source, sku, name, category, store, price, was_price, is_promo, observed_on, scraped_at.
"""
import re
from html.parser import HTMLParser


class _CardParser(HTMLParser):
    """Collects title, product id and price from each `.card.thumbnail` on a webscraper.io listing."""

    def __init__(self):
        super().__init__()
        self.cards = []
        self._in_price = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = (attrs.get("class") or "").split()
        if "thumbnail" in classes:
            self.cards.append({})
        elif self.cards and tag == "a" and "title" in classes:
            self.cards[-1]["name"] = attrs["title"]
            self.cards[-1]["sku"] = attrs["href"].rstrip("/").rsplit("/", 1)[-1]
        elif self.cards and tag == "h4" and "price" in classes:
            self._in_price = True

    def handle_data(self, data):
        if self._in_price:
            self.cards[-1]["price"] = float(re.sub(r"[^\d.]", "", data))
            self._in_price = False


def parse_webscraper_listing(html: str, scraped_at: str, category: str) -> list[dict]:
    parser = _CardParser()
    parser.feed(html)
    return [
        {
            "source": "webscraper_io", "sku": card["sku"], "name": card["name"], "category": category,
            "store": "webscraper_io", "price": card["price"], "was_price": None, "is_promo": False,
            "observed_on": scraped_at[:10], "scraped_at": scraped_at,
        }
        for card in parser.cards
    ]


def parse_open_prices(payload: dict, scraped_at: str) -> tuple[list[dict], int]:
    """
    Keep US, USD, barcoded prices. Returns the records and how many rows were dropped.

    The API ignores its own country filter, so the US check happens here.
    """
    records, dropped = [], 0
    for item in payload["items"]:
        location = item.get("location") or {}
        if (
            item.get("price") is None
            or item.get("currency") != "USD"
            or location.get("osm_address_country_code") != "US"
            or not item.get("product_code")
        ):
            dropped += 1
            continue
        product = item.get("product") or {}
        categories = product.get("categories_tags") or []
        records.append({
            "source": "open_prices",
            "sku": item["product_code"],
            "name": product.get("product_name"),
            "category": categories[-1] if categories else None,
            "store": str(item["location_id"]),
            "store_name": f"{location.get('osm_name')} {location.get('osm_address_city')}",
            "price": float(item["price"]),
            "was_price": item.get("price_without_discount"),
            "is_promo": bool(item.get("price_is_discounted")),
            "observed_on": item["date"],
            "scraped_at": scraped_at,
            "price_id": str(item["id"]),
        })
    return records, dropped
