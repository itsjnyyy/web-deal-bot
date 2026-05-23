# 🎮 Amazon Gaming Deal Monitor — Discord Bot

Monitors Amazon for **name-brand gaming components** and posts a Discord embed whenever one drops **40% or more** off its listed price. No API key or paid subscription required — fully free to run.

---

## How it works

```
Every 2 hours:
  Playwright (headless Chrome)  ──►  scrapes Amazon deals pages
        │
        └──► filter by gaming brand  ──►  filter by discount %
                    │
                    └──► new deal found  ──►  Discord embed  ──►  SQLite (prevent duplicates)
```

- **Playwright** scrapes Amazon's Today's Deals pages using a headless Chromium browser
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
3. Repeat for any additional channels you want

### Step 3 — Deploy to Railway

1. Push this repo to a private GitHub repo
2. Go to **https://railway.app** → **New Project** → **Deploy from GitHub repo**
3. Select your repo → **Deploy Now**
4. Go to **Variables** tab and add:

| Variable | Value |
|---|---|
| `DISCORD_TOKEN` | Your Discord bot token |
| `CHANNEL_ID` | One channel ID, or multiple separated by commas: `123,456,789` |
| `MIN_DISCOUNT_PERCENT` | Minimum discount to alert on (default: `40`) |
| `CHECK_INTERVAL_HOURS` | How often to scan in hours (default: `2`) |

Railway will auto-redeploy whenever you change a variable or push new code.

### Step 4 — Add to more servers

Just invite the bot to another server using the OAuth2 URL from Step 1, then add the new channel ID to `CHANNEL_ID` in Railway, separated by a comma.

---

## Slash Commands

| Command | Description |
|---|---|
| `/check` | Force an immediate deal scan |
| `/stats` | Show total deals tracked + 5 most recent |
| `/help` | Show available commands |

---

## Adjusting settings

All settings are controlled via Railway environment variables — no code changes needed:

- **Raise/lower the discount threshold** → change `MIN_DISCOUNT_PERCENT` (e.g. `30` for more deals, `50` for fewer)
- **Scan more/less often** → change `CHECK_INTERVAL_HOURS`
- **Add a new channel** → append its ID to `CHANNEL_ID` with a comma

---

## Adding/removing brands

Edit the `GAMING_BRANDS` list in `bot.py`. Brands are matched as substrings (case-insensitive), so `"samsung"` matches anything with Samsung in the title. After editing, push to GitHub and Railway will auto-redeploy.

---

## What a deal alert looks like

```
🔥🔥 55% OFF — Razer DeathAdder V3 HyperSpeed Wireless Gaming Mouse
💰 Sale Price    📦 Was         💸 You Save
  $27.49           ~~$59.99~~     $32.50

📈 Price History          🛒 Buy Now
  CamelCamelCamel          View on Amazon

Amazon Gaming Deals  •  Updates every 2h  •  Min 40% off
```

---

## File structure

```
amazon-deal-bot/
  bot.py              — Main bot (scraper, Discord embeds, slash commands)
  requirements.txt    — Python dependencies
  Procfile            — Railway startup command
  nixpacks.toml       — Railway build config (installs Chromium)
  config.example.json — Local config template (copy to config.json for local use)
  .gitignore          — Keeps config.json and deals_seen.db out of git
```

---

## Running locally

```bash
cp config.example.json config.json
# Edit config.json with your real tokens
pip install -r requirements.txt
playwright install chromium
python bot.py
```
