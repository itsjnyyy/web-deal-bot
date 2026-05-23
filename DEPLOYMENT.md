# 🚀 Deployment Guide — Amazon Gaming Deal Bot

There are 4 good ways to run this bot 24/7. Pick the one that fits your budget.

---

## Option Comparison

| Option              | Cost       | Difficulty | Best For                        |
|---------------------|------------|------------|---------------------------------|
| Railway             | ~$5/mo     | ⭐ Easiest  | Most people — deploy in minutes |
| Oracle Cloud        | **Free**   | ⭐⭐ Medium  | Free forever, needs Linux basics |
| DigitalOcean        | $4/mo      | ⭐⭐ Medium  | Reliable, easy Linux VPS        |
| Your own Windows PC | Free       | ⭐ Easy     | If your PC runs 24/7            |

---

---

## 🥇 Option A — Railway (Recommended, ~$5/mo)

Railway is the easiest cloud platform for Python bots. No server management needed.

### 1. Prep your project for Railway

Add a file called `Procfile` (no extension) to your project folder:

```
worker: python bot.py
```

Your folder should now look like:
```
amazon-deal-bot/
  bot.py
  config.json
  requirements.txt
  Procfile
```

> ⚠️ **Do NOT put your real tokens in `config.json` before uploading.**
> You'll set them as environment variables in Railway instead (see step 4).

### 2. Create a GitHub repo

1. Go to **https://github.com/new**
2. Name it `amazon-deal-bot`, set to **Private**, click **Create**
3. Open a terminal in your project folder and run:

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/amazon-deal-bot.git
git push -u origin main
```

### 3. Deploy to Railway

1. Go to **https://railway.app** → sign in with GitHub
2. Click **New Project** → **Deploy from GitHub repo**
3. Select your `amazon-deal-bot` repo
4. Railway will auto-detect Python and start building

### 4. Set environment variables (your secrets)

In Railway, go to your project → **Variables** tab → add these one by one:

| Variable Name           | Value                          |
|-------------------------|--------------------------------|
| `DISCORD_TOKEN`         | Your Discord bot token         |
| `CHANNEL_ID`            | Your Discord channel ID        |
| `KEEPA_API_KEY`         | Your Keepa API key             |
| `MIN_DISCOUNT_PERCENT`  | `40`                           |
| `CHECK_INTERVAL_HOURS`  | `2`                            |

### 5. Update bot.py to read from environment variables

Replace the config loading block at the top of `bot.py` (lines 17–24) with this:

```python
import os

DISCORD_TOKEN    = os.environ["DISCORD_TOKEN"]
CHANNEL_ID       = int(os.environ["CHANNEL_ID"])
KEEPA_API_KEY    = os.environ["KEEPA_API_KEY"]
MIN_DISCOUNT_PCT = int(os.environ.get("MIN_DISCOUNT_PERCENT", 40))
CHECK_HOURS      = int(os.environ.get("CHECK_INTERVAL_HOURS", 2))
```

Then commit and push:
```bash
git add bot.py
git commit -m "Use environment variables"
git push
```

Railway automatically redeploys on every push. ✅

### 6. Check logs

Railway → your project → **Deployments** → click latest deploy → **View Logs**
You should see: `Logged in as YourBot#1234 | Monitoring 14 categories | Min 40% off`

---

---

## 🆓 Option B — Oracle Cloud Free Tier (Always Free)

Oracle gives you a real Linux server **free forever** — no credit card charges after signup.

### 1. Create a free Oracle Cloud account

1. Go to **https://cloud.oracle.com** → **Start for free**
2. You'll need a credit card to verify identity (you will NOT be charged)
3. Choose your home region (pick closest to you, e.g. US East)

### 2. Create a free VM

1. Dashboard → **Compute** → **Instances** → **Create Instance**
2. Settings:
   - **Name**: `deal-bot`
   - **Image**: `Ubuntu 22.04` (click Edit to change)
   - **Shape**: `VM.Standard.A1.Flex` — set **1 OCPU, 6 GB RAM** (this is free)
3. Under **SSH Keys**: click **Generate a key pair** → download both files
4. Click **Create**

### 3. Connect to your server

On Windows, open PowerShell:

```powershell
ssh -i C:\path\to\your-key.key ubuntu@YOUR_SERVER_IP
```

*(Replace path and IP with your actual values — the IP is shown in Oracle's instance page)*

### 4. Set up Python and upload your bot

On the server:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python pip
sudo apt install python3-pip -y

# Create a folder for your bot
mkdir ~/deal-bot && cd ~/deal-bot
```

Back on your Windows PC, upload your files using PowerShell:

```powershell
scp -i C:\path\to\key.key bot.py requirements.txt config.json ubuntu@YOUR_IP:~/deal-bot/
```

Back on the server, install dependencies:

```bash
cd ~/deal-bot
pip3 install -r requirements.txt
```

Edit your config with real credentials:

```bash
nano config.json
# Paste your real tokens, Ctrl+X → Y → Enter to save
```

### 5. Run forever with systemd

Create a service file:

```bash
sudo nano /etc/systemd/system/deal-bot.service
```

Paste this (replace `/home/ubuntu/deal-bot`  if your path is different):

```ini
[Unit]
Description=Amazon Gaming Deal Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/deal-bot
ExecStart=/usr/bin/python3 /home/ubuntu/deal-bot/bot.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable deal-bot
sudo systemctl start deal-bot
```

Check it's running:

```bash
sudo systemctl status deal-bot
# You should see: Active: active (running)

# View live logs:
sudo journalctl -u deal-bot -f
```

---

---

## 💧 Option C — DigitalOcean Droplet ($4/mo)

The simplest paid Linux VPS. More beginner-friendly than Oracle.

### 1. Create a Droplet

1. **https://digitalocean.com** → Create → Droplets
2. Settings:
   - **Region**: closest to you
   - **OS**: Ubuntu 22.04
   - **Size**: Basic → Regular → **$4/mo (512MB RAM)** — plenty for a Discord bot
   - **Authentication**: Password (easier) or SSH key
3. Click **Create Droplet**

### 2. Connect and deploy

Open PowerShell and SSH in:

```powershell
ssh root@YOUR_DROPLET_IP
```

Then follow the **exact same steps as Option B, Step 4–5** above.
(DigitalOcean gives you `root` access by default, so use `root` instead of `ubuntu`)

---

---

## 🖥️ Option D — Your Own Windows PC (Free)

Best if your PC runs 24/7 (or you don't mind downtime when it's off).

### Run on startup with Task Scheduler

1. Create a file called `run_bot.bat` in your project folder:

```bat
@echo off
cd C:\Users\jcala\Documents\amazon-deal-bot
python bot.py
```

2. Open **Task Scheduler** (search for it in Start menu)
3. Click **Create Basic Task** on the right
4. Fill in:
   - **Name**: Amazon Deal Bot
   - **Trigger**: When the computer starts
   - **Action**: Start a program → browse to your `run_bot.bat`
5. Finish. The bot now starts automatically on reboot.

### Keep it running if the terminal closes

Install `pythonw` runner or use Windows Terminal's "run minimized" setting.
Or, run it in a minimized PowerShell window that you leave open.

---

## 🔄 Updating the bot after changes

| Platform        | How to update                                                      |
|-----------------|--------------------------------------------------------------------|
| Railway         | `git add . && git commit -m "update" && git push` — auto-redeploys |
| Oracle / DO     | `scp` the new `bot.py` to server, then `sudo systemctl restart deal-bot` |
| Your own PC     | Edit files directly, restart the Task Scheduler task               |

---

## 🐛 Troubleshooting

| Problem | Fix |
|---|---|
| Bot comes online but posts nothing | Check Keepa API key is valid and has tokens remaining at keepa.com |
| `Channel not found` in logs | Make sure the bot has been invited to your server and has permission to see the channel |
| Bot goes offline randomly | On Railway, check if you've exceeded the free tier usage |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` again |
| Database errors | Delete `deals_seen.db` and restart — it will recreate itself |
