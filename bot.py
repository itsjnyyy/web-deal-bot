"""
Amazon Gaming Deal Monitor — Discord Bot
Polls the Keepa Deal Finder API every N hours and posts any name-brand gaming
component that has dropped ≥ MIN_DISCOUNT_PCT off its 90-day average.
"""

import asyncio
import json
import logging
import sqlite3
from datetime import datetime

import discord
import requests
from discord.ext import commands, tasks

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("deal-bot")

# ── Config ────────────────────────────────────────────────────────────────────
with open("config.json") as f:
    config = json.load(f)

DISCORD_TOKEN    = config["discord_token"]
CHANNEL_ID       = int(config["channel_id"])
KEEPA_API_KEY    = config["keepa_api_key"]
MIN_DISCOUNT_PCT = config.get("min_discount_percent", 40)
CHECK_HOURS      = config.get("check_interval_hours", 2)

# ── Name-brand gaming filter ──────────────────────────────────────────────────
# Deals must contain at least one of these brand names (case-insensitive).
GAMING_BRANDS = [
    # Peripherals
    "logitech", "razer", "corsair", "steelseries", "hyperx", "roccat",
    "glorious", "ducky", "keychron", "elgato", "astro", "sennheiser",
    # GPUs / AIBs
    "evga", "zotac", "sapphire", "xfx", "powercolor", "msi", "gigabyte",
    "asus rog", "asus tuf", "asus dual", "asus prime",
    # Monitors
    "lg ultragear", "lg ultranano", "benq", "aoc", "viewsonic",
    "alienware", "samsung odyssey", "asus rog swift", "msi optix",
    # Systems / Laptops
    "acer predator", "acer nitro", "hp omen", "dell g-series",
    # Storage
    "samsung 970", "samsung 980", "samsung 990", "wd black", "seagate barracuda",
    "seagate firecuda", "crucial p5", "crucial p3", "kingston fury",
    # Memory
    "g.skill", "corsair vengeance", "crucial ballistix",
    # Cooling / Cases
    "nzxt", "cooler master", "thermaltake", "be quiet", "fractal design",
    "lian li", "phanteks",
    # CPUs / Boards (popular retail combos)
    "amd ryzen", "intel core i", "asrock", "msi mpg", "msi mag",
    # Headsets
    "steelseries arctis", "razer blackshark", "corsair virtuoso",
    "hyperx cloud", "logitech g pro", "logitech g435",
]

# ── Keepa category IDs for Amazon.com ────────────────────────────────────────
# https://www.keepa.com/#!categorytree
CATEGORIES = {
    "Computers & Accessories":      284822,
    "Computer Components":          193870011,
    "Gaming Keyboards & Mice":      1232597011,
    "PC Gaming":                    2407749011,
    "Gaming Headsets":              3012290011,
    "Gaming Controllers":           402053011,
    "Computer Monitors":            1292115011,
    "Computer Cases":               1292110011,
    "CPU Processors":               229189,
    "Graphics Cards":               284823,
    "Internal SSDs":                1292116011,
    "RAM":                          172500,
    "PC Gaming Chairs":             4616531011,
}

# ── Database ──────────────────────────────────────────────────────────────────
DB_FILE = "deals_seen.db"


def db_init():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS deals (
                asin        TEXT PRIMARY KEY,
                title       TEXT,
                price_cents INTEGER,
                discount    INTEGER,
                alerted_at  TEXT
            )
        """)


def already_alerted(asin: str, price_cents: int) -> bool:
    """
    Returns True if we sent this ASIN before at a price within 5% of current.
    Allows re-alerting if the price drops significantly further.
    """
    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute(
            "SELECT price_cents FROM deals WHERE asin = ?", (asin,)
        ).fetchone()
    if row is None:
        return False
    prev_price = row[0]
    # Re-alert only if new price is >5% cheaper than the last alert
    return price_cents >= prev_price * 0.95


def record_deal(asin, title, price_cents, discount):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO deals VALUES (?,?,?,?,?)",
            (asin, title, price_cents, discount, datetime.utcnow().isoformat()),
        )


# ── Keepa deal fetcher ────────────────────────────────────────────────────────
def is_gaming_brand(title: str) -> bool:
    t = title.lower()
    return any(brand in t for brand in GAMING_BRANDS)


def fetch_keepa_deals() -> list[dict]:
    """
    Calls Keepa's Deal Finder for each gaming category.
    Returns a deduplicated list of qualifying deal dicts.
    """
    found: dict[str, dict] = {}

    for cat_name, cat_id in CATEGORIES.items():
        try:
            resp = requests.get(
                "https://api.keepa.com/deal",
                params={
                    "key":          KEEPA_API_KEY,
                    "domainId":     1,           # 1 = amazon.com
                    "deltaPercent": MIN_DISCOUNT_PCT,
                    "categories":   cat_id,
                    "page":         0,
                    "priceTypes":   0,           # 0 = Amazon price
                },
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            log.warning(f"Keepa request failed ({cat_name}): {exc}")
            continue

        for item in data.get("deals", {}).get("items", []):
            asin  = item.get("asin")
            title = item.get("title", "")

            if not asin or asin in found:
                continue
            if not is_gaming_brand(title):
                continue

            # Keepa stores prices as integer cents; -1 = unavailable
            current_list = item.get("current", [])
            avg90_list   = item.get("avg90",   [])
            if not current_list or current_list[0] < 0:
                continue

            current_cents = current_list[0]
            orig_cents    = avg90_list[0] if avg90_list and avg90_list[0] > 0 else None

            # Fall back to the "was" price field if no 90-day avg
            if orig_cents is None:
                was_list = item.get("was", [])
                if was_list and was_list[0] > 0:
                    orig_cents = was_list[0]

            if orig_cents is None or orig_cents <= current_cents:
                continue

            discount_pct = round((1 - current_cents / orig_cents) * 100)
            if discount_pct < MIN_DISCOUNT_PCT:
                continue

            found[asin] = {
                "asin":          asin,
                "title":         title,
                "current_cents": current_cents,
                "orig_cents":    orig_cents,
                "discount_pct":  discount_pct,
                "category":      cat_name,
                "url":           f"https://www.amazon.com/dp/{asin}?tag=YOUR_AFFILIATE_TAG",
                "image_url":     item.get("image"),
            }
            log.info(f"  Found deal: {discount_pct}% off — {title[:60]}")

    log.info(f"Keepa scan complete. {len(found)} qualifying deal(s) found.")
    return list(found.values())


# ── Discord embed builder ─────────────────────────────────────────────────────
DISCOUNT_COLORS = {
    40: discord.Color.from_rgb(255, 165, 0),   # orange  40-49%
    50: discord.Color.from_rgb(255, 80,  0),   # deep orange 50-59%
    60: discord.Color.from_rgb(220, 20,  20),  # red     60-69%
    70: discord.Color.red(),                   # bright red 70%+
}


def deal_color(pct: int) -> discord.Color:
    for threshold in sorted(DISCOUNT_COLORS.keys(), reverse=True):
        if pct >= threshold:
            return DISCOUNT_COLORS[threshold]
    return discord.Color.orange()


def build_embed(deal: dict) -> discord.Embed:
    current = deal["current_cents"] / 100
    orig    = deal["orig_cents"]    / 100
    savings = orig - current
    pct     = deal["discount_pct"]

    # Fire emoji tier based on discount size
    fire = "🔥" if pct < 50 else ("🔥🔥" if pct < 60 else "🔥🔥🔥")

    embed = discord.Embed(
        title     = f"{fire} {pct}% OFF — {deal['title'][:180]}",
        url       = deal["url"],
        color     = deal_color(pct),
        timestamp = datetime.utcnow(),
    )
    embed.add_field(name="💰 Sale Price",    value=f"**${current:.2f}**",      inline=True)
    embed.add_field(name="📦 Was (90d avg)", value=f"~~${orig:.2f}~~",         inline=True)
    embed.add_field(name="💸 You Save",      value=f"**${savings:.2f}**",      inline=True)
    embed.add_field(name="📂 Category",      value=deal["category"],            inline=True)
    embed.add_field(
        name="📈 Price History",
        value=f"[CamelCamelCamel](https://camelcamelcamel.com/product/{deal['asin']})",
        inline=True,
    )
    embed.add_field(
        name="🛒 Buy Now",
        value=f"[Amazon Link]({deal['url']})",
        inline=True,
    )

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
        log.error(f"Channel {CHANNEL_ID} not found — check config.json")
        return

    loop   = asyncio.get_event_loop()
    deals  = await loop.run_in_executor(None, fetch_keepa_deals)
    posted = 0

    for deal in sorted(deals, key=lambda d: d["discount_pct"], reverse=True):
        if already_alerted(deal["asin"], deal["current_cents"]):
            continue
        await channel.send(embed=build_embed(deal))
        record_deal(deal["asin"], deal["title"], deal["current_cents"], deal["discount_pct"])
        posted += 1
        await asyncio.sleep(1.5)   # avoid rate-limiting Discord

    if posted == 0:
        log.info("No new deals to post.")
    else:
        log.info(f"Posted {posted} new deal(s).")


@deal_loop.before_loop
async def before_loop():
    await bot.wait_until_ready()


# ── Bot commands ──────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    db_init()
    deal_loop.start()
    log.info(f"Logged in as {bot.user}  |  Monitoring {len(CATEGORIES)} categories  |  Min {MIN_DISCOUNT_PCT}% off")
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(
            f"🤖 **Amazon Gaming Deal Monitor online!**\n"
            f"Scanning {len(CATEGORIES)} categories every **{CHECK_HOURS}h** "
            f"for name-brand items ≥ **{MIN_DISCOUNT_PCT}% off**.\n"
            f"Use `!check` to force a scan now or `!stats` to see tracked deals."
        )


@bot.command(name="check")
@commands.has_permissions(manage_messages=True)
async def cmd_check(ctx):
    """Force an immediate deal scan (requires Manage Messages permission)."""
    await ctx.send("🔍 Running manual deal scan...")
    await deal_loop()


@bot.command(name="stats")
async def cmd_stats(ctx):
    """Show deal tracking statistics."""
    with sqlite3.connect(DB_FILE) as conn:
        total = conn.execute("SELECT COUNT(*) FROM deals").fetchone()[0]
        recent = conn.execute(
            "SELECT title, discount, alerted_at FROM deals ORDER BY alerted_at DESC LIMIT 5"
        ).fetchall()

    embed = discord.Embed(title="📊 Deal Monitor Stats", color=discord.Color.blurple())
    embed.add_field(name="Total Deals Tracked", value=str(total), inline=False)
    if recent:
        lines = "\n".join(
            f"• **{r[1]}%** off — {r[0][:55]}…  `{r[2][:10]}`"
            for r in recent
        )
        embed.add_field(name="5 Most Recent Alerts", value=lines, inline=False)
    embed.set_footer(text=f"Checking every {CHECK_HOURS}h  •  Min {MIN_DISCOUNT_PCT}% off")
    await ctx.send(embed=embed)


@bot.command(name="dealhelp")
async def cmd_help(ctx):
    """Show available commands."""
    embed = discord.Embed(title="🎮 Gaming Deal Bot Commands", color=discord.Color.green())
    embed.add_field(name="!check",    value="Force a deal scan right now *(mod only)*", inline=False)
    embed.add_field(name="!stats",    value="Show total deals tracked + recent alerts",  inline=False)
    embed.add_field(name="!dealhelp", value="Show this help message",                    inline=False)
    await ctx.send(embed=embed)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
