"""
Amazon Gaming Deal Monitor — Discord Bot
Primary: Playwright stealth scraping Amazon directly.
Fallback: CamelCamelCamel + Slickdeals RSS.
"""

import asyncio
import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

# ── Install Playwright browser at runtime (Railway) ───────────────────────────
print("Installing Playwright Chromium...", flush=True)
subprocess.run(
    [sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"],
    capture_output=False,
)
print("Chromium ready.", flush=True)

import discord
from discord import app_commands
from discord.ext import tasks
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("deal-bot")

# ── Config ────────────────────────────────────────────────────────────────────
def get_config(key, default=None):
    val = os.environ.get(key)
    if val:
        return val
    try:
        with open("config.json") as f:
            return json.load(f).get(key, default)
    except FileNotFoundError:
        return default

DISCORD_TOKEN    = get_config("DISCORD_TOKEN")
CHANNEL_IDS      = [
    int(cid.strip())
    for cid in get_config("CHANNEL_ID", "0").split(",")
    if cid.strip().isdigit()
]
MIN_DISCOUNT_PCT = int(get_config("MIN_DISCOUNT_PERCENT", 40))
CHECK_HOURS      = int(get_config("CHECK_INTERVAL_HOURS", 2))

# ── CamelCamelCamel + Slickdeals fallback feeds ───────────────────────────────
SLICKDEALS_SEARCHES = [
    # Peripherals
    "gaming mouse", "gaming keyboard", "gaming headset", "gaming monitor",
    "mechanical keyboard", "wireless gaming mouse", "gaming mousepad",
    # GPUs
    "RTX 4060", "RTX 4070", "RTX 4080", "RTX 4090",
    "RTX 5070", "RTX 5080", "RTX 5090",
    "RX 7600", "RX 7700", "RX 7800", "RX 7900",
    "graphics card sale", "GPU deal",
    # Storage & RAM
    "Samsung 990 Pro", "Samsung 980 Pro", "WD Black SN850",
    "Seagate FireCuda", "Crucial T700", "Kingston Fury Renegade",
    "DDR5 RAM", "DDR4 RAM", "G.Skill Trident",
    # Brands — direct
    "Logitech G502", "Logitech G Pro", "Logitech G29", "Logitech G923", "Logitech G733",
    "Razer DeathAdder", "Razer BlackShark", "Razer Huntsman", "Razer Basilisk",
    "Corsair K70", "Corsair HS80", "Corsair Virtuoso", "Corsair Vengeance",
    "SteelSeries Arctis", "SteelSeries Apex", "SteelSeries Rival",
    "HyperX Cloud", "HyperX Alloy", "HyperX Pulsefire",
    "ASUS ROG", "ASUS TUF gaming", "MSI gaming",
    "Alienware monitor", "LG UltraGear", "Samsung Odyssey",
    "BenQ gaming", "AOC gaming monitor",
    # Monitors
    "gaming monitor 144hz", "gaming monitor 165hz", "gaming monitor 240hz",
    "4K gaming monitor", "ultrawide gaming monitor", "curved gaming monitor",
    # Controllers & Console
    "DualSense controller", "PS5 controller", "Xbox Elite Series 2",
    "Xbox Series controller", "8BitDo controller", "SCUF controller",
    "Switch Pro controller", "Nintendo Switch OLED",
    # Steering wheels
    "Logitech G923", "Logitech G29", "Thrustmaster T300",
    "Thrustmaster TX", "Fanatec CSL", "racing wheel deal",
    # Headsets
    "Astro A50", "Turtle Beach Stealth", "SteelSeries Arctis Nova",
    "Razer Kaira", "Xbox wireless headset", "PS5 Pulse 3D",
    # Cases & Cooling
    "NZXT H510", "Lian Li Lancool", "Fractal Design",
    "Cooler Master case", "Phanteks Eclipse", "be quiet case",
    "AIO liquid cooler", "Noctua cooler", "DeepCool cooler",
    # Capture & Streaming
    "Elgato 4K60", "AVerMedia capture card", "Elgato Stream Deck",
    # Laptops
    "ASUS ROG laptop", "Razer Blade laptop", "MSI gaming laptop",
    "Alienware laptop", "Acer Predator laptop", "Lenovo Legion laptop",
]

# ── Best Buy & Newegg RSS deal feeds ─────────────────────────────────────────
BESTBUY_SEARCHES = [
    "gaming mouse", "gaming keyboard", "gaming headset", "gaming monitor",
    "graphics card", "gaming laptop", "SSD", "gaming controller",
    "racing wheel", "mechanical keyboard", "CPU processor",
    "Logitech", "Razer", "Corsair", "SteelSeries", "HyperX",
    "ASUS ROG", "MSI gaming", "Alienware", "Samsung gaming",
]

NEWEGG_SEARCHES = [
    "gaming mouse", "gaming keyboard", "gaming headset", "gaming monitor",
    "graphics card RTX", "graphics card RX", "NVMe SSD", "DDR5 RAM",
    "gaming laptop", "PC case gaming", "CPU AMD", "CPU Intel",
    "Logitech", "Razer", "Corsair", "ASUS ROG", "MSI",
    "mechanical keyboard", "racing wheel", "gaming controller",
]

# ── Gaming brand + keyword filter ─────────────────────────────────────────────
GAMING_BRANDS = [
    "logitech", "razer", "corsair", "steelseries", "hyperx", "roccat",
    "glorious", "ducky", "keychron", "elgato", "astro", "sennheiser",
    "evga", "zotac", "sapphire", "xfx", "powercolor", "msi", "gigabyte",
    "asus rog", "asus tuf", "asus dual", "asus prime", "asus",
    "lg ultragear", "benq", "aoc", "viewsonic", "alienware",
    "samsung odyssey", "samsung 970", "samsung 980", "samsung 990",
    "acer predator", "acer nitro", "hp omen",
    "wd black", "seagate", "crucial", "kingston", "g.skill",
    "nzxt", "cooler master", "thermaltake", "be quiet", "fractal design",
    "lian li", "phanteks", "deepcool",
    "amd ryzen", "intel core", "asrock",
    "rtx", "gtx", "rx 6", "rx 7", "geforce", "radeon",
    "steelseries arctis", "razer blackshark", "corsair virtuoso",
    "hyperx cloud", "logitech g pro",
    "dualsense", "dualshock", "xbox elite", "joycon", "joy-con",
    "8bitdo", "powera", "nacon", "scuf", "victrix", "backbone",
    "thrustmaster", "fanatec", "moza racing", "simagic",
    "logitech g29", "logitech g920", "logitech g923",
    "sony pulse", "turtle beach", "astro a50", "astro a40", "astro a30",
    "razer kaira", "avermedia",
]

GAMING_KEYWORDS = [
    "gaming", "mechanical keyboard", "gpu", "graphics card", "geforce",
    "radeon", "nvme ssd", "ddr5", "ddr4", "controller", "racing wheel",
    "capture card", "144hz", "165hz", "240hz",
]

def is_gaming_item(title: str) -> bool:
    t = title.lower()
    return any(b in t for b in GAMING_BRANDS) or any(k in t for k in GAMING_KEYWORDS)

# ── Database ──────────────────────────────────────────────────────────────────
DB_FILE = "deals_seen.db"

def db_init():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS deals (
                deal_id     TEXT PRIMARY KEY,
                title       TEXT,
                price       REAL,
                discount    INTEGER,
                alerted_at  TEXT
            )
        """)

def already_alerted_today(deal_id: str, price: float) -> bool:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute(
            "SELECT price, alerted_at FROM deals WHERE deal_id = ?", (deal_id,)
        ).fetchone()
    if row is None:
        return False
    prev_price, alerted_at = row
    if price < prev_price * 0.95:
        return False
    return alerted_at[:10] == today

def already_alerted_ever(deal_id: str, price: float) -> bool:
    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute(
            "SELECT price FROM deals WHERE deal_id = ?", (deal_id,)
        ).fetchone()
    if row is None:
        return False
    return price >= row[0] * 0.95

def record_deal(deal_id, title, price, discount):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO deals VALUES (?,?,?,?,?)",
            (deal_id, title, price, discount, datetime.utcnow().isoformat()),
        )

# ── Scraper ───────────────────────────────────────────────────────────────────
def extract_discount(text: str, price_text: str = "", orig_text: str = "") -> int | None:
    """Try every method to extract a discount percentage."""
    for pattern in [r"(\d+)\s*%\s*off", r"(\d+)\s*%\s*discount",
                    r"save\s+(\d+)\s*%", r"-(\d+)%", r"(\d+)%\s*drop"]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return int(m.group(1))
    # Calculate from price strings
    p = re.sub(r"[^\d.]", "", price_text)
    o = re.sub(r"[^\d.]", "", orig_text)
    if p and o:
        try:
            sale, orig = float(p), float(o)
            if orig > sale > 0:
                return round((1 - sale / orig) * 100)
        except ValueError:
            pass
    return None


async def scrape_amazon_deals() -> list[dict]:
    found = {}

    # ── Primary: Playwright stealth ───────────────────────────────────────────
    # p_n_pct-off-with-tax:2250765011 = any discount filter on Amazon search
    amazon_urls = [
        # Featured deals pages
        "https://www.amazon.com/deals?deals-widget=%7B%22version%22%3A1%2C%22viewIndex%22%3A0%2C%22presetId%22%3A%22deals-collection-all-deals%22%2C%22sorting%22%3A%22BY_SCORE%22%7D",
        "https://www.amazon.com/gp/goldbox",
        # Brand searches filtered to discounted items only
        "https://www.amazon.com/s?k=logitech+gaming&rh=p_n_pct-off-with-tax%3A2250765011",
        "https://www.amazon.com/s?k=razer+gaming&rh=p_n_pct-off-with-tax%3A2250765011",
        "https://www.amazon.com/s?k=corsair+gaming&rh=p_n_pct-off-with-tax%3A2250765011",
        "https://www.amazon.com/s?k=asus+rog&rh=p_n_pct-off-with-tax%3A2250765011",
        "https://www.amazon.com/s?k=steelseries&rh=p_n_pct-off-with-tax%3A2250765011",
        "https://www.amazon.com/s?k=hyperx+gaming&rh=p_n_pct-off-with-tax%3A2250765011",
        "https://www.amazon.com/s?k=msi+gaming&rh=p_n_pct-off-with-tax%3A2250765011",
        "https://www.amazon.com/s?k=gaming+monitor&rh=p_n_pct-off-with-tax%3A2250765011",
        "https://www.amazon.com/s?k=graphics+card+rtx&rh=p_n_pct-off-with-tax%3A2250765011",
        "https://www.amazon.com/s?k=gaming+headset&rh=p_n_pct-off-with-tax%3A2250765011",
        "https://www.amazon.com/s?k=racing+wheel+gaming&rh=p_n_pct-off-with-tax%3A2250765011",
        "https://www.amazon.com/s?k=nvme+ssd&rh=p_n_pct-off-with-tax%3A2250765011",
        "https://www.amazon.com/s?k=gaming+keyboard+mechanical&rh=p_n_pct-off-with-tax%3A2250765011",
        "https://www.amazon.com/s?k=gaming+mouse+wireless&rh=p_n_pct-off-with-tax%3A2250765011",
    ]
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 900},
                locale="en-US",
                timezone_id="America/New_York",
            )
            page = await context.new_page()
            page.on("console", lambda msg: log.info(f"  BROWSER: {msg.text[:300]}") if any(x in msg.text for x in ["CARD_", "PAGE_", "COUNTS"]) else None)
            await Stealth().apply_stealth_async(page)

            # Visit homepage first to look human
            await page.goto("https://www.amazon.com", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            for url in amazon_urls:
                try:
                    log.info(f"  Playwright: {url[:60]}...")
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(5000)
                    # Scroll to trigger lazy loading of deal cards
                    for _ in range(5):
                        await page.evaluate("window.scrollBy(0, 1200)")
                        await page.wait_for_timeout(1500)
                    await page.wait_for_timeout(2000)
                    # Wait specifically for deal cards to appear
                    try:
                        await page.wait_for_selector(
                            ".dcl-product-detail, [data-component-type='s-search-result']",
                            timeout=10000
                        )
                    except Exception:
                        pass

                    page_content = await page.content()
                    page_size = len(page_content)
                    log.info(f"  Page size: {page_size} bytes")
                    if page_size < 50000:
                        log.warning("  Page too small — likely blocked")
                        continue

                    cards = await page.evaluate("""
                        () => {
                            const results = [];

                            // Amazon deals page uses dcl-product-detail
                            // Amazon search uses s-search-results container with [data-asin] children
                            const dealCards = [...document.querySelectorAll('.dcl-product-detail')];

                            // For search pages: find the results container then get data-asin items
                            const searchContainer = document.querySelector('[data-component-type="s-search-results"]');
                            const searchCards = searchContainer
                                ? [...searchContainer.querySelectorAll('[data-asin]:not([data-asin=""])')]
                                    .filter(el => el.tagName === 'DIV' && el.querySelector('.a-price'))
                                : [];

                            const cards = dealCards.length > 0 ? dealCards : searchCards;

                            cards.forEach((card) => {
                                try {
                                    const asin = card.getAttribute('data-asin');
                                    const link = asin ? 'https://www.amazon.com/dp/' + asin : '';
                                    if (!link) return;
                                    const imgEl = card.querySelector('img');
                                    const img = imgEl ? imgEl.src : '';
                                    const allText = card.innerText || '';
                                    results.push({ rawText: allText, link: link, img: img });
                                } catch(e) {}
                            });
                            return results;
                        }
                    """)
                    log.info(f"  Found {len(cards)} cards")

                    for item in cards:
                        raw_text = item.get("rawText", "").strip()
                        link     = item.get("link", "")
                        if not link or not raw_text:
                            continue

                        # Extract ASIN
                        asin_m = re.search(r"/dp/([A-Z0-9]{10})", link)
                        if not asin_m:
                            continue
                        deal_id = asin_m.group(1)
                        if deal_id in found:
                            continue

                        # Extract discount % first
                        discount_pct = extract_discount(raw_text)
                        if discount_pct is None or discount_pct < MIN_DISCOUNT_PCT:
                            continue

                        # Extract title from URL slug — Amazon puts it there even when
                        # it's stripped from the card HTML
                        # e.g. /Traeger-TFB57PZBO-Bronze-Pellet-Grill/dp/B07GLK1NC2
                        url_title_m = re.search(r"amazon\.com/([^/]+)/dp/[A-Z0-9]{10}", link)
                        if url_title_m:
                            title = url_title_m.group(1).replace("-", " ").strip()
                        else:
                            title = ""

                        if not title or not is_gaming_item(title):
                            continue

                        # Extract prices — lowest is sale price, highest is original
                        prices = []
                        for x in re.findall(r"\$([0-9]+(?:\.[0-9]{2})?)", raw_text):
                            try:
                                val = float(x)
                                if val > 0:
                                    prices.append(val)
                            except ValueError:
                                pass
                        price = min(prices) if prices else 0.0
                        orig  = max(prices) if len(prices) > 1 else 0.0

                        found[deal_id] = {
                            "deal_id":      deal_id,
                            "title":        title,
                            "price":        price,
                            "orig":         orig,
                            "discount_pct": discount_pct,
                            "url":          f"https://www.amazon.com/dp/{deal_id}",
                            "image_url":    item.get("img", ""),
                            "source":       "Amazon",
                        }
                        log.info(f"  ✓ [Amazon] {discount_pct}% off — {title[:55]}")

                except Exception as e:
                    log.warning(f"  Playwright page error: {e}")

            await browser.close()
        log.info(f"Playwright done — {len(found)} deal(s)")

    except Exception as e:
        log.warning(f"Playwright failed: {e}")

    # ── Fallback: CamelCamelCamel + Slickdeals ────────────────────────────────
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }
    loop = asyncio.get_event_loop()

    def fetch_url(url):
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read()

    def parse_rss(items, source):
        for item in items:
            title = (item.findtext("title") or "").strip()
            link  = (item.findtext("link")  or "").strip()
            desc  = (item.findtext("description") or "").strip()
            if not title or not link or not is_gaming_item(title):
                continue
            combined = title + " " + desc
            discount_pct = extract_discount(combined)
            if discount_pct is None:
                prices = []
                for x in re.findall(r"\$([0-9]+(?:\.[0-9]{2})?)", combined):
                    try:
                        val = float(x)
                        if val > 0:
                            prices.append(val)
                    except ValueError:
                        pass
                best = None
                for i in range(len(prices)):
                    for j in range(len(prices)):
                        if i != j and prices[j] > prices[i] > 0:
                            pct = round((1 - prices[i] / prices[j]) * 100)
                            if best is None or pct > best:
                                best = pct
                discount_pct = best
            if discount_pct is None or discount_pct < MIN_DISCOUNT_PCT:
                continue
            prices = []
            for x in re.findall(r"\$([0-9]+(?:\.[0-9]{2})?)", combined):
                try:
                    val = float(x)
                    if val > 0:
                        prices.append(val)
                except ValueError:
                    pass
            price = min(prices) if prices else 0.0
            orig  = max(prices) if len(prices) > 1 else 0.0
            # Build deal ID from ASIN (Amazon), SKU (Best Buy), or itemNumber (Newegg)
            asin_m = re.search(r"/dp/([A-Z0-9]{10})|/product/([A-Z0-9]{10})", link)
            bb_m   = re.search(r"skuId=(\d+)", link)
            ne_m   = re.search(r"/p/([A-Z0-9\-]+)", link)
            if asin_m:
                deal_id  = asin_m.group(1) or asin_m.group(2)
                deal_url = f"https://www.amazon.com/dp/{deal_id}"
            elif bb_m:
                deal_id  = f"bb_{bb_m.group(1)}"
                deal_url = link
            elif ne_m:
                deal_id  = f"ne_{ne_m.group(1)}"
                deal_url = link
            else:
                deal_id  = re.sub(r"[^\w]", "", link[-40:])
                deal_url = link
            if deal_id in found:
                continue
            found[deal_id] = {
                "deal_id": deal_id, "title": title, "price": price,
                "orig": orig, "discount_pct": discount_pct,
                "url": deal_url, "image_url": "", "source": source,
            }
            log.info(f"  ✓ [{source}] {discount_pct}% off — {title[:55]}")

    for search in SLICKDEALS_SEARCHES:
        try:
            url = f"https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&q={urllib.parse.quote(search)}&rss=1"
            xml_data = await loop.run_in_executor(None, fetch_url, url)
            root = ET.fromstring(xml_data)
            ch = root.find("channel")
            items = ch.findall("item") if ch is not None else []
            parse_rss(items, "Slickdeals")
        except Exception as e:
            log.warning(f"  Slickdeals ('{search}'): {e}")

    # ── Best Buy RSS ──────────────────────────────────────────────────────────
    for search in BESTBUY_SEARCHES:
        try:
            url = f"https://www.bestbuy.com/site/searchpage.jsp?st={urllib.parse.quote(search)}&cp=1&_dyncharset=UTF-8&id=pcat17071&type=page&sc=Global&usc=All+Categories&ks=960&keys=keys&iht=n&rss=true"
            xml_data = await loop.run_in_executor(None, fetch_url, url)
            root = ET.fromstring(xml_data)
            ch = root.find("channel")
            items = ch.findall("item") if ch is not None else []
            if items:
                log.info(f"  Best Buy '{search}': {len(items)} items")
            parse_rss(items, "Best Buy")
        except Exception as e:
            log.warning(f"  Best Buy ('{search}'): {e}")

    # ── Newegg RSS ────────────────────────────────────────────────────────────
    for search in NEWEGG_SEARCHES:
        try:
            url = f"https://www.newegg.com/p/pl?d={urllib.parse.quote(search)}&N=4131%204017&Order=1&PageSize=36&rss=1"
            xml_data = await loop.run_in_executor(None, fetch_url, url)
            root = ET.fromstring(xml_data)
            ch = root.find("channel")
            items = ch.findall("item") if ch is not None else []
            if items:
                log.info(f"  Newegg '{search}': {len(items)} items")
            parse_rss(items, "Newegg")
        except Exception as e:
            log.warning(f"  Newegg ('{search}'): {e}")

    log.info(f"Scrape complete — {len(found)} qualifying deal(s) total.")
    return list(found.values())


# ── Discord embed ─────────────────────────────────────────────────────────────
def deal_color(pct):
    if pct >= 70: return discord.Color.red()
    if pct >= 60: return discord.Color.from_rgb(220, 20, 20)
    if pct >= 50: return discord.Color.from_rgb(255, 80, 0)
    return discord.Color.from_rgb(255, 165, 0)

def build_embed(deal):
    price, orig, pct = deal["price"], deal["orig"], deal["discount_pct"]
    fire = "🔥" if pct < 50 else ("🔥🔥" if pct < 60 else "🔥🔥🔥")
    embed = discord.Embed(
        title     = f"{fire} {pct}% OFF — {deal['title'][:180]}",
        url       = deal["url"],
        color     = deal_color(pct),
        timestamp = datetime.utcnow(),
    )
    if price > 0:
        embed.add_field(name="💰 Sale Price", value=f"**${price:.2f}**",        inline=True)
    if orig > 0:
        embed.add_field(name="📦 Was",        value=f"~~${orig:.2f}~~",         inline=True)
    if price > 0 and orig > 0:
        embed.add_field(name="💸 You Save",   value=f"**${orig - price:.2f}**", inline=True)
    if deal.get("deal_id") and len(deal["deal_id"]) == 10:
        embed.add_field(
            name="📈 Price History",
            value=f"[CamelCamelCamel](https://camelcamelcamel.com/product/{deal['deal_id']})",
            inline=True,
        )
    embed.add_field(name="🛒 Buy Now", value=f"[View on Amazon]({deal['url']})", inline=True)
    if deal.get("image_url"):
        embed.set_thumbnail(url=deal["image_url"])
    source = deal.get("source", "Amazon")
    embed.set_footer(text=f"Via {source}  •  Every {CHECK_HOURS}h  •  Min {MIN_DISCOUNT_PCT}% off")
    return embed


# ── Presence ──────────────────────────────────────────────────────────────────
async def set_presence(state, deal_count=0):
    if state == "scanning":
        activity = discord.Activity(type=discord.ActivityType.watching, name="for gaming deals 🔍")
        status = discord.Status.idle
    elif state == "found" and deal_count > 0:
        activity = discord.Activity(type=discord.ActivityType.playing, name=f"{deal_count} deal(s) just dropped 🔥")
        status = discord.Status.online
    else:
        with sqlite3.connect(DB_FILE) as conn:
            total = conn.execute("SELECT COUNT(*) FROM deals").fetchone()[0]
        activity = discord.Activity(type=discord.ActivityType.watching, name=f"for deals | {total} tracked 💸")
        status = discord.Status.online
    await bot.change_presence(status=status, activity=activity)


# ── Core scan ─────────────────────────────────────────────────────────────────
_scan_lock = asyncio.Lock()

async def run_scan(manual=False):
    if _scan_lock.locked():
        log.info("Scan already in progress, skipping.")
        return 0
    async with _scan_lock:
        return await _do_scan(manual)

async def _do_scan(manual=False):
    log.info(f"Starting {'manual' if manual else 'auto'} scan...")
    await set_presence("scanning")

    channels = [bot.get_channel(cid) for cid in CHANNEL_IDS]
    channels = [c for c in channels if c is not None]
    if not channels:
        log.error("No valid channels found")
        await set_presence("idle")
        return 0

    deals  = await scrape_amazon_deals()
    posted = 0

    check_fn = already_alerted_ever if manual else already_alerted_today
    for deal in sorted(deals, key=lambda d: d["discount_pct"], reverse=True):
        if check_fn(deal["deal_id"], deal["price"]):
            continue
        for channel in channels:
            await channel.send(embed=build_embed(deal))
            await asyncio.sleep(0.5)
        record_deal(deal["deal_id"], deal["title"], deal["price"], deal["discount_pct"])
        posted += 1
        await asyncio.sleep(1.0)

    log.info(f"Done — posted {posted} new deal(s).")
    if posted > 0:
        await set_presence("found", posted)
        await asyncio.sleep(30)
    await set_presence("idle")
    return posted



# ── Background loop ───────────────────────────────────────────────────────────
@tasks.loop(hours=CHECK_HOURS)
async def deal_loop():
    await run_scan()

@deal_loop.before_loop
async def before_loop():
    await bot.wait_until_ready()


# ── Bot setup ─────────────────────────────────────────────────────────────────
intents = discord.Intents.default()

class DealBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        log.info("Slash commands synced")

bot = DealBot()


# ── Slash commands ────────────────────────────────────────────────────────────
@bot.tree.command(name="check", description="Force an immediate deal scan")
async def slash_check(interaction: discord.Interaction):
    await interaction.response.send_message("🔍 Scanning Amazon for deals, this may take a minute...")
    try:
        posted = await run_scan(manual=True)
        if posted == 0:
            await interaction.followup.send(
                f"😴 No new deals found right now that are ≥ **{MIN_DISCOUNT_PCT}% off**. Try again later!"
            )
    except Exception as e:
        log.error(f"/check error: {e}")
        await interaction.followup.send(f"❌ Something went wrong: `{e}`")

@bot.tree.command(name="stats", description="Show deal tracking stats")
async def slash_stats(interaction: discord.Interaction):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            total  = conn.execute("SELECT COUNT(*) FROM deals").fetchone()[0]
            recent = conn.execute(
                "SELECT title, discount, alerted_at FROM deals ORDER BY alerted_at DESC LIMIT 5"
            ).fetchall()
        embed = discord.Embed(title="📊 Deal Monitor Stats", color=discord.Color.blurple())
        embed.add_field(name="Total Deals Tracked", value=str(total), inline=False)
        if recent:
            lines = "\n".join(f"• **{r[1]}%** off — {r[0][:55]}…" for r in recent)
            embed.add_field(name="5 Most Recent", value=lines, inline=False)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: `{e}`")

@bot.tree.command(name="help", description="Show available commands")
async def slash_help(interaction: discord.Interaction):
    embed = discord.Embed(title="🎮 Gaming Deal Bot Commands", color=discord.Color.green())
    embed.add_field(name="/check", value="Force a deal scan right now",              inline=False)
    embed.add_field(name="/stats", value="Show total deals tracked + recent alerts", inline=False)
    embed.add_field(name="/help",  value="Show this help message",                   inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.error
async def on_app_command_error(interaction, error):
    log.error(f"Slash error: {error}")
    msg = f"❌ Error: `{error}`"
    if interaction.response.is_done():
        await interaction.followup.send(msg)
    else:
        await interaction.response.send_message(msg)


# ── Events ────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    db_init()
    deal_loop.start()
    log.info(f"Logged in as {bot.user}  |  Min {MIN_DISCOUNT_PCT}% off  |  Every {CHECK_HOURS}h")
    await set_presence("idle")
    for cid in CHANNEL_IDS:
        channel = bot.get_channel(cid)
        if channel:
            await channel.send(
                f"🤖 **Amazon Gaming Deal Monitor online!**\n"
                f"Scanning Amazon every **{CHECK_HOURS}h** for name-brand items ≥ **{MIN_DISCOUNT_PCT}% off**.\n"
                f"Use `/check` to scan now, `/stats` to see tracked deals."
            )

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
