"""
Amazon Gaming Deal Monitor — Discord Bot
Scrapes Slickdeals RSS feeds (cloud-friendly, no API key needed).
Slash commands only.
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

import discord
from discord import app_commands
from discord.ext import tasks

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
CHANNEL_IDS = [
    int(cid.strip())
    for cid in get_config("CHANNEL_ID", "0").split(",")
    if cid.strip().isdigit()
]
MIN_DISCOUNT_PCT = int(get_config("MIN_DISCOUNT_PERCENT", 40))
CHECK_HOURS      = int(get_config("CHECK_INTERVAL_HOURS", 2))

# ── Slickdeals search terms ───────────────────────────────────────────────────
SLICKDEALS_SEARCHES = [
    # PC components & peripherals
    "gaming monitor", "gaming keyboard", "gaming mouse", "gaming headset",
    "graphics card", "GPU", "gaming laptop", "SSD", "RAM DDR",
    "gaming chair", "CPU processor", "PC case",
    "mechanical keyboard", "wireless mouse", "gaming microphone",
    # Console controllers
    "PS5 controller", "PlayStation controller", "DualSense",
    "Xbox controller", "Xbox Series controller",
    "Nintendo Switch controller", "Switch Pro controller",
    "gaming controller wireless",
    # Steering wheels & sim racing
    "racing wheel", "steering wheel PC", "Logitech G wheel",
    "Thrustmaster wheel", "Fanatec wheel", "sim racing pedals",
    "racing simulator", "force feedback wheel",
    # Console headsets
    "PS5 headset", "PlayStation headset", "Xbox headset",
    "Nintendo Switch headset", "console gaming headset",
    "wireless gaming headset",
    # Console accessories
    "PS5 accessories", "Xbox accessories", "Nintendo Switch accessories",
    "capture card", "gaming webcam",
]

# ── Gaming brand filter ───────────────────────────────────────────────────────
GAMING_BRANDS = [
    # PC peripherals
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
    # Console controllers
    "dualsense", "dualshock", "playstation controller",
    "xbox controller", "xbox elite", "xbox series",
    "nintendo switch pro", "switch pro controller", "joycon", "joy-con",
    "8bitdo", "powera", "nacon", "scuf", "victrix", "backbone",
    # Steering wheels & sim racing
    "logitech g29", "logitech g920", "logitech g923",
    "thrustmaster", "fanatec", "moza racing", "simagic",
    "hori racing", "pxn wheel",
    # Console headsets
    "sony pulse", "pulse 3d", "pulse explore",
    "xbox wireless headset", "astro a50", "astro a40", "astro a30",
    "steelseries arctis nova", "razer kaira", "corsair hs",
    "turtle beach", "plantronics", "jabra",
    # Capture & streaming
    "elgato capture", "avermedia", "razer ripsaw",
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
    return price >= row[0] * 0.95

def record_deal(deal_id, title, price, discount):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO deals VALUES (?,?,?,?,?)",
            (deal_id, title, price, discount, datetime.utcnow().isoformat()),
        )

# ── Slickdeals scraper ────────────────────────────────────────────────────────
async def scrape_amazon_deals() -> list[dict]:
    """
    Fetches Slickdeals RSS feeds for each gaming search term.
    Slickdeals aggregates Amazon deals and works reliably from cloud IPs.
    """
    found = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }

    loop = asyncio.get_event_loop()

    def fetch_feed(search):
        url = f"https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&q={urllib.parse.quote(search)}&rss=1"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read()

    for search in SLICKDEALS_SEARCHES:
        try:
            xml_data = await loop.run_in_executor(None, fetch_feed, search)
            root = ET.fromstring(xml_data)
            channel_el = root.find("channel")
            items = channel_el.findall("item") if channel_el is not None else []
            log.info(f"  Slickdeals '{search}': {len(items)} results")

            for item in items:
                title = (item.findtext("title") or "").strip()
                link  = (item.findtext("link")  or "").strip()
                desc  = (item.findtext("description") or "").strip()

                if not title or not link:
                    continue
                if not is_gaming_brand(title):
                    continue

                # Parse discount % from title or description
                discount_pct = None
                for text in [title, desc]:
                    match = re.search(r"(\d+)\s*%\s*off", text, re.IGNORECASE)
                    if match:
                        discount_pct = int(match.group(1))
                        break

                # Try calculating from prices e.g. "$29.99 (reg $59.99)"
                if discount_pct is None:
                    prices = re.findall(r"\$([0-9]+(?:\.[0-9]{2})?)", title + " " + desc)
                    if len(prices) >= 2:
                        try:
                            sale = float(prices[0])
                            orig = float(prices[1])
                            if orig > sale > 0:
                                discount_pct = round((1 - sale / orig) * 100)
                        except ValueError:
                            pass

                if discount_pct is None or discount_pct < MIN_DISCOUNT_PCT:
                    continue

                # Extract prices
                prices = re.findall(r"\$([0-9]+(?:\.[0-9]{2})?)", title + " " + desc)
                try:
                    price = float(prices[0]) if prices else 0.0
                    orig  = float(prices[1]) if len(prices) > 1 else 0.0
                except (ValueError, IndexError):
                    price, orig = 0.0, 0.0

                deal_id = re.sub(r"[^\w]", "", link[-40:])
                if deal_id in found:
                    continue

                found[deal_id] = {
                    "deal_id":      deal_id,
                    "title":        title,
                    "price":        price,
                    "orig":         orig,
                    "discount_pct": discount_pct,
                    "url":          link,
                    "image_url":    "",
                }
                log.info(f"  ✓ {discount_pct}% off — {title[:60]}")

        except Exception as exc:
            log.warning(f"Slickdeals error for '{search}': {exc}")

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
        embed.add_field(name="💰 Sale Price", value=f"**${price:.2f}**",       inline=True)
    if orig > 0:
        embed.add_field(name="📦 Was",        value=f"~~${orig:.2f}~~",        inline=True)
    if price > 0 and orig > 0:
        embed.add_field(name="💸 You Save",   value=f"**${orig - price:.2f}**", inline=True)
    embed.add_field(name="🛒 View Deal", value=f"[Slickdeals]({deal['url']})", inline=True)
    if deal.get("image_url"):
        embed.set_thumbnail(url=deal["image_url"])
    embed.set_footer(text=f"Amazon Gaming Deals via Slickdeals  •  Every {CHECK_HOURS}h  •  Min {MIN_DISCOUNT_PCT}% off")
    return embed

# ── Core scan ─────────────────────────────────────────────────────────────────
async def set_presence(state: str, deal_count: int = 0):
    """Update the bot rich presence status."""
    if state == "scanning":
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="for gaming deals 🔍"
        )
        status = discord.Status.idle
    elif state == "found" and deal_count > 0:
        activity = discord.Activity(
            type=discord.ActivityType.playing,
            name=f"{deal_count} deal(s) just dropped 🔥"
        )
        status = discord.Status.online
    else:
        with sqlite3.connect(DB_FILE) as conn:
            total = conn.execute("SELECT COUNT(*) FROM deals").fetchone()[0]
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=f"for deals | {total} tracked 💸"
        )
        status = discord.Status.online
    await bot.change_presence(status=status, activity=activity)


async def run_scan() -> int:
    log.info("Starting deal scan...")
    await set_presence("scanning")

    channels = [bot.get_channel(cid) for cid in CHANNEL_IDS]
    channels = [c for c in channels if c is not None]
    if not channels:
        log.error("No valid channels found from CHANNEL_ID config")
        await set_presence("idle")
        return 0

    deals  = await scrape_amazon_deals()
    posted = 0

    for deal in sorted(deals, key=lambda d: d["discount_pct"], reverse=True):
        if already_alerted(deal["deal_id"], deal["price"]):
            continue
        for channel in channels:
            await channel.send(embed=build_embed(deal))
            await asyncio.sleep(0.5)
        record_deal(deal["deal_id"], deal["title"], deal["price"], deal["discount_pct"])
        posted += 1
        await asyncio.sleep(1.0)

    log.info(f"Done — posted {posted} new deal(s) to {len(channels)} channel(s).")
    if posted > 0:
        await set_presence("found", posted)
        await asyncio.sleep(30)  # show "X deals just dropped" for 30s then revert
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
        log.info("Slash commands synced globally")

bot = DealBot()

# ── Slash commands ────────────────────────────────────────────────────────────
@bot.tree.command(name="check", description="Force an immediate deal scan")
async def slash_check(interaction: discord.Interaction):
    await interaction.response.send_message("🔍 Scanning for deals, this may take a minute...")
    try:
        posted = await run_scan()
        if posted == 0:
            await interaction.followup.send(
                f"😴 No new deals found right now that are ≥ **{MIN_DISCOUNT_PCT}% off** from a name brand. Try again later!"
            )
        # If deals were found they're already posted to the channel — no followup needed
    except Exception as e:
        log.error(f"/check error: {e}")
        await interaction.followup.send(f"❌ Something went wrong during the scan: `{e}`")

@bot.tree.command(name="stats", description="Show how many deals have been tracked")
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
        log.error(f"/stats error: {e}")
        await interaction.response.send_message(f"❌ Error fetching stats: `{e}`")

@bot.tree.command(name="help", description="Show available bot commands")
async def slash_help(interaction: discord.Interaction):
    embed = discord.Embed(title="🎮 Gaming Deal Bot Commands", color=discord.Color.green())
    embed.add_field(name="/check", value="Force a deal scan right now",               inline=False)
    embed.add_field(name="/stats", value="Show total deals tracked + recent alerts",  inline=False)
    embed.add_field(name="/help",  value="Show this help message",                    inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    log.error(f"Slash command error: {error}")
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
                f"Scanning Slickdeals every **{CHECK_HOURS}h** for name-brand gaming items ≥ **{MIN_DISCOUNT_PCT}% off**.\n"
                f"Use `/check` to scan now, `/stats` to see tracked deals."
            )

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
