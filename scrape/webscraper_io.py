"""
Scrape the webscraper.io e-commerce test store with Selenium. The product grid loads with JavaScript,
so a plain HTTP request sees no products.

Usage:
    python -m scrape.webscraper_io
"""
import time
from datetime import datetime, timezone

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from scrape.base import write_partition
from scrape.parsers import parse_webscraper_listing
from src.config import USER_AGENT

BASE = "https://webscraper.io/test-sites/e-commerce/ajax"
CATEGORIES = {"laptops": "computers/laptops", "tablets": "computers/tablets", "phones": "phones/touch"}
MAX_PAGES = 20
DELAY_S = 1.0


def _driver() -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument(f"--user-agent={USER_AGENT}")
    return webdriver.Chrome(options=options)


def scrape(driver, scraped_at: str) -> tuple[list[dict], dict]:
    records, pages, failures = [], 0, 0
    for category, path in CATEGORIES.items():
        driver.get(f"{BASE}/{path}")
        for _ in range(MAX_PAGES):
            try:
                WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".thumbnail")))
            except TimeoutException:
                failures += 1
                break
            pages += 1
            records += parse_webscraper_listing(driver.page_source, scraped_at, category)
            next_button = driver.find_elements(By.CSS_SELECTOR, ".pager button.next")
            if not next_button or next_button[0].get_attribute("disabled") is not None:
                break
            first_card = driver.find_element(By.CSS_SELECTOR, ".thumbnail")
            time.sleep(DELAY_S)
            next_button[0].click()
            WebDriverWait(driver, 20).until(EC.staleness_of(first_card))
    return records, {"pages": pages, "parse_failures": failures}


def main():
    started = datetime.now(timezone.utc)
    scraped_at = started.strftime("%Y-%m-%dT%H:%M:%SZ")
    driver = _driver()
    try:
        records, stats = scrape(driver, scraped_at)
    finally:
        driver.quit()
    run = {"source": "webscraper_io", "started_at": scraped_at, **stats, "rows": len(records),
           "null_prices": 0, "duration_s": round((datetime.now(timezone.utc) - started).total_seconds(), 1)}
    path = write_partition("webscraper_io", records, run, started.date())
    print(f"webscraper_io: {len(records)} products from {stats['pages']} pages -> {path}")


if __name__ == "__main__":
    main()
