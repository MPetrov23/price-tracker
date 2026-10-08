import csv
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

SITES = [
    {
        "name": "RayaToys",
        "url": "https://rayatoys.com/bebeshka-kolichka-3-v-1-lionelo-mika",
        "enabled": True,
        "selector": None,
    },
    {
        "name": "BG Hlapeta",
        "url": "https://bghlapeta.com/lionelo-mika-plus-bebeshka-kolichka-3-v-1",
        "enabled": True,
        "selector": None,
    },
    {
        "name": "Ozone",
        "url": "https://www.ozone.bg/product/detska-kolichka-3-v-1-lionelo-mika-beije-sand/?utm_source=google&utm_medium=cpc&utm_campaign=P.%20MB.%20Mother%20%26%20Baby&utm_id=18946772327&gad_source=1&gad_campaignid=22913904692&gbraid=0AAAABA8ToTyHszWF4FUwuxi1aubZaW1qH&gclid=CjwKCAjw_pzWBhAkEiwAwDCi1aqzqbVsQ5JTewnY4Dzqmf8fik97whJWXJcCmCIFR26cYzHyvQ4FWRoCWLgQAvD_BwE",
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
        return None, f"грешка при заявка: {exc}"

    if resp.status_code in (403, 429) or "cloudflare" in resp.text.lower()[:2000]:
        return None, "вероятно блокирано от bot-защита (нужен Selenium/Playwright)"

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

    return None, "цена не е намерена - провери HTML структурата ръчно"

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
    """Праща известие в конзолата, а ако TELEGRAM_TOKEN/CHAT_ID са зададени - и в Telegram."""
    print(f"🔔 ИЗВЕСТИЕ: {message}")

    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return  # Telegram не е конфигуриран - виж глобалните променливи горе

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": message},
            timeout=10,
        )
        if not resp.ok:
            print(f"⚠️  Telegram грешка: {resp.status_code} {resp.text}")
    except requests.RequestException as exc:
        print(f"⚠️  Telegram заявката се провали: {exc}")


def send_daily_summary(prices: dict):
    """Праща обобщение с всички текущи цени - независимо дали са се променили."""
    if not prices:
        return
    lines = [f"• {name}: {price:.2f} лв./€" for name, price in prices.items()]
    message = "📊 Дневна справка - количка Lionelo Mika Plus:\n" + "\n".join(lines)
    send_notification(message)

def run_once():
    last_prices = load_last_prices()
    current_prices = {}
    print(f"\n=== Проверка на цени: {datetime.now():%Y-%m-%d %H:%M} ===\n")

    for site in SITES:
        if not site.get("enabled", True):
            print(f"⏭️  {site['name']}: пропуснат (изключен в config-а)")
            continue

        price, info = get_price(site)

        if price is None:
            print(f"⚠️  {site['name']}: {info}")
            continue

        print(f"✅ {site['name']}: {price:.2f} лв./€  (метод: {info})")
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