import csv
import json
import os
import re
import time
import logging

from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

SITES = [
    {
        "name": "Sladurcheta",
        "url": "https://sladurcheta.bg/product/video-bebefon-chipolino-duo-view-5full-hd-ekran",
        "enabled": True,
        "selector": None,
    },
    {
        "name": "Ozone",
        "url": "https://www.ozone.bg/product/video-bebefon-chipolino-duo-view/",
        "enabled": True,
        "text_extract": {"start": "Цена:", "end": "Купи", "pick": "first"},
        "selector": None,
    },
    {
        "name": "E-Chipolino",
        "url": (
            "https://e-chipolino.com/p/73331-%D0%B2%D0%B8%D0%B4%D0%B5%D0%BE-"
            "%D0%B1%D0%B5%D0%B1%D0%B5%D1%84%D0%BE%D0%BD-duo-view-5full-hd-"
            "%D0%B5%D0%BA%D1%80%D0%B0%D0%BD"
        ),
        "enabled": True,
        "text_extract": {"start": "GTIN", "end": "количество", "pick": "min"},
        "selector": None,
    },

    {
        "name": "BG Hlapeta",
        "url": "https://bghlapeta.com/chipolino-duo-view-video-bebefon-5-incha-full-hd-ekran?adwords=true&gad_source=1&gad_campaignid=24069885534&gbraid=0AAAABASHlS1lQZkfbdVuC48hvE-KAZuIR&gclid=CjwKCAjwoaLWBhAWEiwAnyitu_MDMA2Cnb0Fi9v00Y_kFrc_lQyKj6BSKtHgsgAH_uNm6CXjlZo14RoCylAQAvD_BwE",
        "enabled": True,
        "selector": None,
    },
]

DATA_FILE = Path(__file__).parent / "price_history.csv"

# TELEGRAM

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
}

PRICE_RE = re.compile(r"[\d]+[.,]?\d*")

def _to_float(raw: str):
    """Превръща '515,90 лв.' / '515.9' -> 515.9 (float)."""
    if raw is None:
        return None
    match = PRICE_RE.search(raw.replace("\xa0", "").replace(" ", ""))
    if not match:
        return None
    num = match.group().replace(",", ".")
    try:
        return float(num)
    except ValueError:
        return None


def extract_price_jsonld(soup: BeautifulSoup):
    """Опитва да намери цена в <script type="application/ld+json"> (schema.org)."""
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            offers = item.get("offers")
            if isinstance(offers, list):
                offers = offers[0] if offers else None
            if isinstance(offers, dict) and offers.get("price"):
                return _to_float(str(offers["price"]))
    return None

def extract_price_meta(soup: BeautifulSoup):
    """Опитва мета тагове: product:price:amount, og:price:amount, itemprop=price."""
    meta_names = [
        ("property", "product:price:amount"),
        ("property", "og:price:amount"),
        ("name", "twitter:data1"),
    ]
    for attr, value in meta_names:
        tag = soup.find("meta", attrs={attr: value})
        if tag and tag.get("content"):
            price = _to_float(tag["content"])
            if price:
                return price

    itemprop_tag = soup.find(attrs={"itemprop": "price"})
    if itemprop_tag:
        price = _to_float(itemprop_tag.get("content") or itemprop_tag.get_text())
        if price:
            return price
    return None

def extract_price_selector(soup: BeautifulSoup, selector: str):
    """Fallback: ръчно зададен CSS селектор в config-а."""
    tag = soup.select_one(selector)
    if tag:
        return _to_float(tag.get_text())
    return None

def get_price(site: dict):
    """Връща (цена, метод) или (None, причина_за_грешка)."""
    try:
        resp = requests.get(site["url"], headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.error(f"{site['name']}: request failed: {exc}")
        return None, f"грешка при заявка: {exc}"

    if resp.status_code in (403, 429) or "cloudflare" in resp.text.lower()[:2000]:
        logger.warning(
            f"{site['name']}: possible bot protection "
            f"(HTTP {resp.status_code})"
        )
        return None, "вероятно блокирано от bot-защита"

    soup = BeautifulSoup(resp.text, "lxml")

    price = extract_price_jsonld(soup)
    if price:
        return price, "json-ld"

    price = extract_price_meta(soup)
    if price:
        return price, "meta-tag"

    if site.get("selector"):
        price = extract_price_selector(soup, site["selector"])
        if price:
            return price, "css-selector"

    return None, "Price not found."

def load_last_prices():
    """Зарежда последната записана цена за всеки сайт от CSV."""
    last = {}
    if not DATA_FILE.exists():
        return last
    with open(DATA_FILE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            last[row["site"]] = float(row["price"])
    return last

def save_price(site_name: str, price: float):
    is_new = not DATA_FILE.exists()
    with open(DATA_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["timestamp", "site", "price"])
        writer.writerow([datetime.now().isoformat(timespec="seconds"), site_name, price])

def send_notification(message: str):
    logger.info(f"Telegram notification: {message}")

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials are not configured.")
        return

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": message},
            timeout=10,
        )

        if not resp.ok:
            logger.error(
                f"Telegram error: {resp.status_code} {resp.text}"
            )

    except requests.RequestException as exc:
        logger.error(f"Telegram request failed: {exc}")

def send_daily_summary(prices: dict):
    """Праща обобщение с всички текущи цени - независимо дали са се променили."""
    if not prices:
        return
    lines = [f"• {name}: {price:.2f} €" for name, price in prices.items()]
    message = "Daily Prices - Chipolino Duo View \n" + "\n".join(lines)
    send_notification(message)

def run_once():
    last_prices = load_last_prices()
    current_prices = {}

    logger.info(
        f"Starting price check: {datetime.now():%Y-%m-%d %H:%M}"
    )

    for site in SITES:
        if not site.get("enabled", True):
            logger.info(
                f"{site['name']}: skipped (disabled in config)"
            )
            continue

        price, info = get_price(site)

        if price is None:
            logger.warning(f"{site['name']}: {info}")
            continue

        logger.info(
            f"{site['name']}: {price:.2f} лв./€ (method: {info})"
        )
        current_prices[site["name"]] = price

        old_price = last_prices.get(site["name"])
        if old_price is not None and price != old_price:
            diff = price - old_price
            arrow = "📉 поевтиняла" if diff < 0 else "📈 поскъпнала"
            send_notification(
                f"{site['name']}: цената се промени от {old_price:.2f} на "
                f"{price:.2f} ({arrow}, {diff:+.2f})"
            )

        save_price(site["name"], price)
        time.sleep(2)  # учтива пауза между заявките

    send_daily_summary(current_prices)

if __name__ == "__main__":
    run_once()