# 🎮 Amazon Gaming Deal Monitor — Discord Bot

Monitors **Slickdeals** for name-brand gaming component deals and posts a Discord embed whenever one drops your set minimum percentage off. Completely free to run — no API keys or paid subscriptions required.

---

## How it works

```
Every 2 hours:
  Slickdeals RSS feeds  ──►  filter by gaming brand  ──►  filter by discount %
              │
              └──► new deal found  ──►  Discord embed posted to all channels
                                   ──►  SQLite (prevents duplicate alerts)
```

- **Slickdeals RSS** is scraped for 16 gaming search terms — works reliably from cloud servers unlike scraping Amazon directly
- **50+ brand keywords** ensure only name-brand items get posted
- **SQLite** tracks every alert so you never see the same deal twice (unless the price drops 5%+ further)
- **Multiple channels** supported — post to as many servers as you want

---

## Brands monitored

| Category | Brands |
|---|---|
| Peripherals | Logitech, Razer, Corsair, SteelSeries, HyperX, Roccat, Glorious, Ducky, Keychron, Elgato, Astro, Sennheiser |
| GPUs | EVGA, Zotac, Sapphire, XFX, PowerColor, MSI, Gigabyte, ASUS ROG/TUF/Dual/Prime, RTX, GTX, RX 6/7, GeForce, Radeon |
| Monitors | LG Ultragear, BenQ, AOC, ViewSonic, Alienware, Samsung Odyssey, Acer Predator, Acer Nitro, HP Omen |
| Storage | WD Black, Seagate, Crucial, Kingston, Samsung 970/980/990 |
| Memory | G.Skill, Corsair Vengeance, Kingston Fury |
| Cases & Cooling | NZXT, Cooler Master, Thermaltake, be quiet!, Fractal Design, Lian Li, Phanteks, Deepcool |
| CPUs | AMD Ryzen, Intel Core, ASRock |
| Headsets | SteelSeries Arctis, Razer BlackShark, Corsair Virtuoso, HyperX Cloud, Logitech G Pro |

---

## Setup

### Step 1 — Create a Discord Bot

1. Go to **https://discord.com/developers/applications** → **New Application**
2. Go to **Bot** tab → copy the **Token**
3. Under **Privileged Gateway Intents**, enable **Message Content Intent**
4. Go to **OAuth2 → URL Generator**:
   - Scopes: ✅ `bot` and ✅ `applications.commands`
   - Bot Permissions: ✅ `Send Messages`, `Embed Links`, `Read Message History`
5. Copy the generated URL → open it → add the bot to your server

### Step 2 — Get Your Channel ID(s)

1. In Discord: Settings → Advanced → Enable **Developer Mode**
2. Right-click the channel you want deals posted in → **Copy Channel ID**
3. Repeat for any additional channels

### Step 3 — Deploy to Railway

1. Push this repo to a private GitHub repo
2. Go to **https://railway.app** → **New Project** → **Deploy from GitHub repo**
3. Select your repo → **Deploy Now**
4. Go to the **Variables** tab and add:

| Variable | Value |
|---|---|
| `DISCORD_TOKEN` | Your Discord bot token |
| `CHANNEL_ID` | One ID, or multiple comma-separated: `123,456,789` |
| `MIN_DISCOUNT_PERCENT` | Minimum % off to alert on (default: `40`) |
| `CHECK_INTERVAL_HOURS` | How often to scan in hours (default: `2`) |

Railway auto-redeploys on every variable change or code push.

### Step 4 — Add to more servers

Invite the bot to another server using the OAuth2 URL from Step 1, then append the new channel ID to `CHANNEL_ID` in Railway separated by a comma.

---

## Slash Commands

| Command | Description |
|---|---|
| `/check` | Force an immediate deal scan |
| `/stats` | Show total deals tracked + 5 most recent |
| `/help` | Show available commands |

---

## Adjusting settings (no code changes needed)

All settings are Railway environment variables:

- **Change discount threshold** → update `MIN_DISCOUNT_PERCENT` (e.g. `25` for more deals, `50` for fewer)
- **Scan more/less often** → update `CHECK_INTERVAL_HOURS`
- **Add a channel** → append its ID to `CHANNEL_ID` with a comma

After changing any variable, restart the Railway deployment for it to take effect.

---

## Adding/removing brands

Edit the `GAMING_BRANDS` list in `bot.py`. Brands are matched as case-insensitive substrings — `"samsung"` matches any title containing Samsung. Push to GitHub and Railway auto-redeploys.

---

## Adding/removing search terms

Edit the `SLICKDEALS_SEARCHES` list in `bot.py` to control what categories get searched on Slickdeals. Each term maps to one RSS feed query.

---

## What a deal alert looks like

```
🔥🔥 55% OFF — Razer DeathAdder V3 HyperSpeed Wireless Gaming Mouse
💰 Sale Price    📦 Was         💸 You Save
  $27.49           ~~$59.99~~     $32.50

🛒 View Deal
  Slickdeals

Amazon Gaming Deals via Slickdeals  •  Every 2h  •  Min 25% off
```

---

## File structure

```
amazon-deal-bot/
  bot.py              — Main bot (Slickdeals scraper, Discord embeds, slash commands)
  requirements.txt    — Python dependencies (discord.py, requests)
  Procfile            — Railway startup command
  config.example.json — Local config template (copy to config.json for local use)
  .gitignore          — Keeps config.json and deals_seen.db out of git
```

---

## Running locally

```bash
cp config.example.json config.json
# Edit config.json with your real tokens
pip install -r requirements.txt
python bot.py
```
