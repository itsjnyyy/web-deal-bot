"""
Amazon Gaming Deal Monitor — Discord Bot (Free Version)
Uses Playwright to scrape Amazon's Today's Deals page.
No API key required.
"""

import asyncio
import json
import logging
import os
import re
import sqlite3
from datetime import datetime

import discord
from discord.ext import commands, tasks
from playwright.async_api import async_playwright

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("deal-bot")

# ── Config (reads from environment variables on Railway, or config.json locally)
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
CHANNEL_ID       = int(get_config("CHANNEL_ID", 0))
MIN_DISCOUNT_PCT = int(get_config("MIN_DISCOUNT_PERCENT", 40))
CHECK_HOURS      = int(get_config("CHECK_INTERVAL_HOURS", 2))

# ── Amazon deal category URLs to scan ─────────────────────────────────────────
# These are Amazon's Today's Deals pages filtered by gaming/computer categories
DEAL_URLS = [
    # PC Gaming
    "https://www.amazon.com/deals?deals-widget=%7B%22version%22%3A1%2C%22viewIndex%22%3A0%2C%22presetId%22%3A%22deals-collection-all-deals%22%2C%22sorting%22%3A%22BY_SCORE%22%7D&ref=s9_acss_bw_cg_GBNavN_3a1_w",
    # Electronics Deals
    "https://www.amazon.com/gp/goldbox?deals-widget=%7B%22version%22%3A1%2C%22viewIndex%22%3A0%2C%22presetId%22%3A%22deals-collection-all-deals%22%7D",
]

# ── Gaming brand filter ────────────────────────────────────────────────────────
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
]

def is_gaming_brand(title: str) -> bool:
    t = title.lower()
    return any(brand in t for brand in GAMING_BRANDS)

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

def already_alerted(deal_id: str, price: float) -> bool:
    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute(
            "SELECT price FROM deals WHERE deal_id = ?", (deal_id,)
        ).fetchone()
    if row is None:
        return False
    return price >= row[0] * 0.95  # re-alert if drops 5%+ further

def record_deal(deal_id, title, price, discount):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO deals VALUES (?,?,?,?,?)",
            (deal_id, title, price, discount, datetime.utcnow().isoformat()),
        )

# ── Amazon scraper ─────────────────────────────────────────────────────────────
async def scrape_amazon_deals() -> list[dict]:
    """
    Uses Playwright to load Amazon's deals pages and extract deal cards.
    Returns qualifying deals as a list of dicts.
    """
    found = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        page = await context.new_page()

        # Block images/fonts to load faster
        await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf}", lambda r: r.abort())

        for url in DEAL_URLS:
            try:
                log.info(f"Scraping: {url[:60]}...")
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)  # let JS render deals

                # Scroll to load more deals
                for _ in range(3):
                    await page.evaluate("window.scrollBy(0, 1500)")
                    await page.wait_for_timeout(1000)

                # Extract deal cards — Amazon uses various selectors, try multiple
                deals_data = await page.evaluate("""
                    () => {
                        const results = [];

                        // Selector patterns Amazon uses for deal cards
                        const cards = document.querySelectorAll(
                            '[data-testid="deal-card"], .DealCard, [class*="DealCard"], .octopus-dlp-item-section'
                        );

                        cards.forEach(card => {
                            try {
                                // Title
                                const titleEl = card.querySelector(
                                    '[data-testid="deal-card-title"], .a-truncate-cut, [class*="title"], h2, .a-size-base-plus'
                                );
                                const title = titleEl ? titleEl.innerText.trim() : '';

                                // Current price
                                const priceEl = card.querySelector(
                                    '.a-price .a-offscreen, [data-testid="deal-price"], .dealPriceBadge, [class*="DealPrice"]'
                                );
                                const priceText = priceEl ? priceEl.innerText.trim() : '';

                                // Discount badge
                                const discountEl = card.querySelector(
                                    '[class*="badge"], [class*="discount"], [class*="saving"], .savingsPercentage'
                                );
                                const discountText = discountEl ? discountEl.innerText.trim() : '';

                                // Original price
                                const origEl = card.querySelector(
                                    '.a-text-strike, [class*="original"], [class*="list-price"]'
                                );
                                const origText = origEl ? origEl.innerText.trim() : '';

                                // Product URL
                                const linkEl = card.querySelector('a[href]');
                                const link = linkEl ? linkEl.href : '';

                                // Image
                                const imgEl = card.querySelector('img');
                                const img = imgEl ? imgEl.src : '';

                                if (title && (priceText || discountText)) {
                                    results.push({ title, priceText, discountText, origText, link, img });
                                }
                            } catch(e) {}
                        });

                        return results;
                    }
                """)

                log.info(f"  Found {len(deals_data)} raw cards on page")

                for item in deals_data:
                    title = item.get("title", "")
                    if not title or not is_gaming_brand(title):
                        continue

                    # Parse discount %
                    discount_pct = None
                    discount_text = item.get("discountText", "")
                    match = re.search(r"(\d+)\s*%", discount_text)
                    if match:
                        discount_pct = int(match.group(1))

                    # If no badge, try calculating from prices
                    if discount_pct is None:
                        price_str = re.sub(r"[^\d.]", "", item.get("priceText", ""))
                        orig_str  = re.sub(r"[^\d.]", "", item.get("origText",  ""))
                        if price_str and orig_str:
                            try:
                                price = float(price_str)
                                orig  = float(orig_str)
                                if orig > price > 0:
                                    discount_pct = round((1 - price / orig) * 100)
                            except ValueError:
                                pass

                    if discount_pct is None or discount_pct < MIN_DISCOUNT_PCT:
                        continue

                    # Parse current price
                    price_str = re.sub(r"[^\d.]", "", item.get("priceText", "0"))
                    try:
                        price = float(price_str)
                    except ValueError:
                        price = 0.0

                    orig_str = re.sub(r"[^\d.]", "", item.get("origText", "0"))
                    try:
                        orig = float(orig_str)
                    except ValueError:
                        orig = 0.0

                    link = item.get("link", "")
                    # Extract ASIN from link as deal ID
                    asin_match = re.search(r"/dp/([A-Z0-9]{10})", link)
                    deal_id = asin_match.group(1) if asin_match else re.sub(r"\W", "", title[:30])

                    if deal_id in found:
                        continue

                    found[deal_id] = {
                        "deal_id":      deal_id,
                        "title":        title,
                        "price":        price,
                        "orig":         orig,
                        "discount_pct": discount_pct,
                        "url":          link or f"https://www.amazon.com/dp/{deal_id}",
                        "image_url":    item.get("img", ""),
                    }
                    log.info(f"  ✓ {discount_pct}% off — {title[:55]}")

            except Exception as exc:
                log.warning(f"Error scraping {url[:50]}: {exc}")

        await browser.close()

    log.info(f"Scrape complete. {len(found)} qualifying deal(s).")
    return list(found.values())


# ── Discord embed builder ─────────────────────────────────────────────────────
def deal_color(pct: int) -> discord.Color:
    if pct >= 70: return discord.Color.red()
    if pct >= 60: return discord.Color.from_rgb(220, 20, 20)
    if pct >= 50: return discord.Color.from_rgb(255, 80, 0)
    return discord.Color.from_rgb(255, 165, 0)

def build_embed(deal: dict) -> discord.Embed:
    price = deal["price"]
    orig  = deal["orig"]
    pct   = deal["discount_pct"]
    fire  = "🔥" if pct < 50 else ("🔥🔥" if pct < 60 else "🔥🔥🔥")

    embed = discord.Embed(
        title     = f"{fire} {pct}% OFF — {deal['title'][:180]}",
        url       = deal["url"],
        color     = deal_color(pct),
        timestamp = datetime.utcnow(),
    )

    if price > 0:
        embed.add_field(name="💰 Sale Price",    value=f"**${price:.2f}**",     inline=True)
    if orig > 0:
        embed.add_field(name="📦 Was",           value=f"~~${orig:.2f}~~",      inline=True)
    if price > 0 and orig > 0:
        embed.add_field(name="💸 You Save",      value=f"**${orig-price:.2f}**", inline=True)

    if deal.get("deal_id") and len(deal["deal_id"]) == 10:
        embed.add_field(
            name="📈 Price History",
            value=f"[CamelCamelCamel](https://camelcamelcamel.com/product/{deal['deal_id']})",
            inline=True,
        )
    embed.add_field(name="🛒 Buy Now", value=f"[View on Amazon]({deal['url']})", inline=True)

    if deal.get("image_url"):
        embed.set_thumbnail(url=deal["image_url"])

    embed.set_footer(text=f"Amazon Gaming Deals  •  Updates every {CHECK_HOURS}h  •  Min {MIN_DISCOUNT_PCT}% off")
    return embed


# ── Discord bot ───────────────────────────────────────────────────────────────
intents = discord.Intents.default()
bot     = commands.Bot(command_prefix="!", intents=intents)

@tasks.loop(hours=CHECK_HOURS)
async def deal_loop():
    log.info("Starting deal scan...")
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        log.error(f"Channel {CHANNEL_ID} not found")
        return

    deals  = await scrape_amazon_deals()
    posted = 0

    for deal in sorted(deals, key=lambda d: d["discount_pct"], reverse=True):
        if already_alerted(deal["deal_id"], deal["price"]):
            continue
        await channel.send(embed=build_embed(deal))
        record_deal(deal["deal_id"], deal["title"], deal["price"], deal["discount_pct"])
        posted += 1
        await asyncio.sleep(1.5)

    log.info(f"Done — posted {posted} new deal(s).")

@deal_loop.before_loop
async def before_loop():
    await bot.wait_until_ready()

@bot.event
async def on_ready():
    db_init()
    deal_loop.start()
    log.info(f"Logged in as {bot.user}  |  Min {MIN_DISCOUNT_PCT}% off  |  Every {CHECK_HOURS}h")
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(
            f"🤖 **Amazon Gaming Deal Monitor online!**\n"
            f"Scanning Amazon deals every **{CHECK_HOURS}h** for name-brand items ≥ **{MIN_DISCOUNT_PCT}% off**.\n"
            f"Use `!check` to scan now, `!stats` to see tracked deals."
        )

@bot.command(name="check")
@commands.has_permissions(manage_messages=True)
async def cmd_check(ctx):
    await ctx.send("🔍 Running manual deal scan...")
    await deal_loop()

@bot.command(name="stats")
async def cmd_stats(ctx):
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
    await ctx.send(embed=embed)

@bot.command(name="dealhelp")
async def cmd_help(ctx):
    embed = discord.Embed(title="🎮 Gaming Deal Bot Commands", color=discord.Color.green())
    embed.add_field(name="!check",    value="Force a deal scan right now *(mod only)*", inline=False)
    embed.add_field(name="!stats",    value="Show total deals tracked + recent alerts",  inline=False)
    embed.add_field(name="!dealhelp", value="Show this help message",                    inline=False)
    await ctx.send(embed=embed)

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
