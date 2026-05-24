# 🎮 Amazon Gaming Deal Monitor — Discord Bot

Monitors Amazon for name-brand gaming component deals and posts a Discord embed whenever one meets your minimum discount threshold. Completely free to run — no API keys or paid subscriptions required.

---

## How it works

```
Every 2 hours:
  Playwright (stealth browser)
    ├── Amazon featured deals page
    ├── Amazon Goldbox
    └── 12 brand/category searches (Logitech, Razer, Corsair, ASUS ROG, etc.)
                │
                └── filter by gaming brand/keyword + discount %
                            │
  Slickdeals RSS (60+ search terms, backup)
                            │
                            └── new deal found ──► Discord embed ──► SQLite (dedup)
```

- **Playwright stealth** loads Amazon pages like a real browser, bypassing bot detection
- **Brand searches** query Amazon directly for discounted items by brand — catches regular sale items, not just featured deals
- **Slickdeals RSS** runs as a backup across 60+ search terms to catch anything Playwright misses
- **SQLite** tracks every alert — auto scans skip deals already posted today, manual `/check` skips exact duplicates only

---

## Brands & categories monitored

| Category | Brands / Keywords |
|---|---|
| Peripherals | Logitech G, Razer, Corsair, SteelSeries, HyperX, Roccat, Glorious, Ducky, Keychron |
| GPUs | EVGA, Zotac, Sapphire, XFX, PowerColor, MSI, Gigabyte, ASUS ROG/TUF, RTX, RX series, GeForce, Radeon |
| Monitors | LG Ultragear, BenQ, AOC, ViewSonic, Alienware, Samsung Odyssey, Acer Predator, HP Omen |
| Storage | WD Black, Seagate FireCuda, Crucial, Kingston Fury, Samsung 970/980/990 |
| Memory | G.Skill, Corsair Vengeance, Kingston Fury, DDR4/DDR5 |
| Cases & Cooling | NZXT, Cooler Master, Thermaltake, be quiet!, Fractal Design, Lian Li, Phanteks, Deepcool |
| CPUs | AMD Ryzen, Intel Core, ASRock |
| Headsets | SteelSeries Arctis, Razer BlackShark, Corsair Virtuoso, HyperX Cloud, Astro A50/A40/A30, Turtle Beach |
| Controllers | DualSense, Xbox Elite, 8BitDo, SCUF, Victrix, Backbone, PowerA |
| Steering Wheels | Logitech G29/G920/G923, Thrustmaster, Fanatec, Moza Racing, Simagic |
| Laptops | ASUS ROG, Razer Blade, MSI, Alienware, Acer Predator, Lenovo Legion |
| Capture/Streaming | Elgato, AVerMedia |

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

Railway auto-redeploys whenever you change a variable or push new code. After changing a variable, restart the deployment for it to take effect.

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

- **Change discount threshold** → update `MIN_DISCOUNT_PERCENT` (e.g. `25` for more deals, `50` for fewer). Restart Railway after changing.
- **Scan more/less often** → update `CHECK_INTERVAL_HOURS`
- **Add a channel** → append its ID to `CHANNEL_ID` with a comma

---

## Customizing brands and searches

**Add/remove brands** — edit `GAMING_BRANDS` in `bot.py`. Brands are matched as case-insensitive substrings.

**Add/remove Slickdeals search terms** — edit `SLICKDEALS_SEARCHES` in `bot.py`.

**Add/remove Amazon brand searches** — edit `amazon_urls` in the `scrape_amazon_deals()` function. The URL format is:
```
https://www.amazon.com/s?k=BRAND+KEYWORD&rh=p_n_pct-off-with-tax%3A2250765011
```
The `p_n_pct-off-with-tax` filter tells Amazon to only return discounted items.

Push to GitHub after any changes and Railway auto-redeploys.

---

## What a deal alert looks like

```
🔥🔥 55% OFF — Razer DeathAdder V3 HyperSpeed Wireless Gaming Mouse
💰 Sale Price    📦 Was         💸 You Save
  $27.49           ~~$59.99~~     $32.50

📈 Price History          🛒 Buy Now
  CamelCamelCamel          View on Amazon

Via Amazon  •  Every 2h  •  Min 10% off
```

---

## Discord rich presence

The bot's status updates dynamically:

| State | Status | Activity |
|---|---|---|
| Idle | 🟢 Online | `Watching for deals \| 42 tracked 💸` |
| Scanning | 🟡 Idle | `Watching for gaming deals 🔍` |
| Deal found | 🟢 Online | `Playing 3 deal(s) just dropped 🔥` (30s then reverts) |

---

## File structure

```
amazon-deal-bot/
  bot.py              — Main bot (Playwright scraper, Slickdeals RSS, Discord embeds, slash commands)
  requirements.txt    — Python dependencies (discord.py, playwright, playwright-stealth, requests)
  Procfile            — Railway startup command
  nixpacks.toml       — Railway build config (installs Chromium at build time)
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
