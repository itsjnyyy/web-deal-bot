# 🎮 Amazon Gaming Deal Monitor — Discord Bot

Monitors Amazon for **name-brand gaming components** (GPUs, monitors, keyboards, mice,
headsets, RAM, SSDs, cases, CPUs, etc.) and posts a Discord embed whenever one drops
**40% or more** off its 90-day average price.

---

## How it works

```
Every N hours:
  Keepa Deal API  ──►  filter by gaming brand  ──►  filter by discount %
        │
        └──► new deal found  ──►  Discord embed  ──►  SQLite (prevent duplicates)
```

- **Keepa API** provides reliable Amazon price data without scraping
- **14 categories** are scanned: GPUs, monitors, peripherals, storage, RAM, cases, etc.
- **50+ brand keywords** ensure only name-brand items get posted
- **SQLite** tracks every alert so you never see the same deal twice (unless price drops further)

---

## Setup

### Step 1 — Get a Keepa API Key

1. Go to **https://keepa.com/** and create a free account
2. Go to **https://keepa.com/#!api** and subscribe to a plan
   - **Free tier**: 100 tokens/day — enough to test but limited (each category scan uses ~10 tokens)
   - **Personal plan (~$19/mo)**: 2,000 tokens/day — runs comfortably with 2h checks
3. Copy your API key

### Step 2 — Create a Discord Bot

1. Go to **https://discord.com/developers/applications** → **New Application**
2. Go to **Bot** tab → **Add Bot** → copy the **Token**
3. Under **Privileged Gateway Intents**, enable **Message Content Intent**
4. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot`
   - Bot Permissions: `Send Messages`, `Embed Links`, `Read Message History`, `Manage Messages`
5. Copy the generated URL → open it → add bot to your server

### Step 3 — Get Your Channel ID

1. In Discord: Settings → Advanced → Enable **Developer Mode**
2. Right-click the channel you want deals posted in → **Copy ID**

### Step 4 — Configure

Edit `config.json`:

```json
{
  "discord_token":        "MTIz...",
  "channel_id":           "123456789012345678",
  "keepa_api_key":        "abcdefghijklmnop",
  "min_discount_percent": 40,
  "check_interval_hours": 2
}
```

| Setting                  | Description                                          |
|--------------------------|------------------------------------------------------|
| `discord_token`          | Your Discord bot token                               |
| `channel_id`             | Channel where deals get posted                       |
| `keepa_api_key`          | Your Keepa API key                                   |
| `min_discount_percent`   | Minimum discount to alert (default: 40)              |
| `check_interval_hours`   | How often to scan (default: 2, minimum recommended: 1) |

### Step 5 — Install & Run

```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot
python bot.py
```

---

## Discord Commands

| Command      | Description                               | Who can use     |
|--------------|-------------------------------------------|-----------------|
| `!check`     | Force an immediate deal scan              | Manage Messages |
| `!stats`     | Show total deals tracked + recent alerts  | Everyone        |
| `!dealhelp`  | Show available commands                   | Everyone        |

---

## Customization

### Add/remove brands

In `bot.py`, edit the `GAMING_BRANDS` list. Brands are matched as substrings (case-insensitive),
so `"samsung"` matches "Samsung 990 Pro SSD" and "Samsung Odyssey Monitor".

### Add/remove categories

In `bot.py`, edit the `CATEGORIES` dict. To find Keepa category IDs:
- Visit https://keepa.com/#!categorytree
- Navigate to the category and copy the ID from the URL

### Change minimum discount

In `config.json`, set `"min_discount_percent"` to any value (e.g. 50 for stricter filtering).

---

## Running 24/7

### On Windows (Task Scheduler)

1. Create a `.bat` file:
   ```bat
   @echo off
   cd C:\path\to\amazon-deal-bot
   python bot.py
   ```
2. Open Task Scheduler → Create Basic Task → set trigger to "At startup"

### On Linux/Mac (systemd or screen)

```bash
# Using screen (simplest)
screen -S deal-bot
python bot.py
# Ctrl+A, D to detach

# Using systemd (production)
# Create /etc/systemd/system/deal-bot.service
```

---

## What a deal alert looks like

```
🔥🔥 55% OFF — Razer DeathAdder V3 HyperSpeed Wireless Gaming Mouse
💰 Sale Price    📦 Was (90d avg)   💸 You Save
  $27.49           ~~$59.99~~         $32.50

📂 Category              📈 Price History         🛒 Buy Now
  Gaming Keyboards       CamelCamelCamel          Amazon Link
  & Mice

Amazon Gaming Deals  •  Updates every 2h  •  Min 40% off
```

---

## Token usage (Keepa)

Each API call to the deal endpoint uses approximately **10 tokens per category**.
With 14 categories and checks every 2 hours → ~14 × 12 = **168 tokens/day**.
This requires at least the entry-level paid plan ($19/mo for 2,000 tokens/day).

For the free tier (100/day), set `check_interval_hours` to 12 and reduce categories.
