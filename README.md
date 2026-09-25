# 🏡 Family Dashboard

A self-updating family dashboard published on GitHub Pages, with a Telegram bot for data entry.

## Features

- **4 member cards** (Maurizio, Alessandra, Flavio, Ada) each with avatar, bio, today/tomorrow schedule, status, mood, personal notes
- **Shared sections**: Weather (Altopascio), Menu of the Day (daily reset), Reminders, Family Notes
- **4 visual themes**: Warm 🌅, Cool 🌊, Nature 🌿, Dark 🌙 (persisted per-browser)
- **Auto-updates** via GitHub Actions: 2× per day (07:00 + 19:00 CET)
- **Telegram bot** for all family members to update content from their phones
- **Weather** via OpenWeatherMap free tier
- **Zero backend** — pure static site + JSON + GitHub Actions

---

## Directory Structure

```
family-dashboard/
├── index.html                    ← The dashboard (GitHub Pages root)
├── data/
│   └── dashboard.json            ← All content data (auto-updated)
├── assets/
│   └── images/                   ← Profile pictures (upload here)
│       ├── maurizio.jpg
│       ├── alessandra.jpg
│       ├── flavio.jpg
│       └── ada.jpg
├── bot/
│   ├── bot.py                    ← Telegram bot (run on Raspberry Pi / VPS)
│   ├── fetch_weather.py          ← Weather fetcher (used by GitHub Actions)
│   └── requirements.txt
└── .github/
    └── workflows/
        └── update-dashboard.yml  ← Auto-update workflow
```

---

## Setup Guide

### 1. Create GitHub Repository

```bash
cd C:\Projects\Git-Personal\family-dashboard
git init
git add .
git commit -m "🏡 Initial family dashboard"
# Create repo on GitHub, then:
git remote add origin https://github.com/YOURUSERNAME/family-dashboard.git
git push -u origin main
```

### 2. Enable GitHub Pages

- Go to repo **Settings → Pages**
- Source: **Deploy from a branch**
- Branch: `gh-pages` / `root`

> The workflow uses `peaceiris/actions-gh-pages` which auto-creates the `gh-pages` branch.

### 3. Get API Keys & Tokens

#### OpenWeatherMap (free)
1. Sign up at https://openweathermap.org/api
2. Copy your API key

#### Telegram Bot
1. Message `@BotFather` on Telegram
2. `/newbot` → choose name and username
3. Copy the token

#### GitHub Personal Access Token
1. GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens
2. Give `Contents: Read and Write` permission on your dashboard repo
3. Copy the token

### 4. Add GitHub Secrets

In your repo → **Settings → Secrets and variables → Actions**:

| Secret name    | Value                          |
|---------------|-------------------------------|
| `OWM_API_KEY` | Your OpenWeatherMap API key   |
| `GITHUB_TOKEN` | (already provided by Actions) |

> The bot also needs `GITHUB_TOKEN` and `TELEGRAM_TOKEN` as environment variables where it runs.

### 5. Add Profile Pictures

Upload photos as:
- `assets/images/maurizio.jpg`
- `assets/images/alessandra.jpg`
- `assets/images/flavio.jpg`
- `assets/images/ada.jpg`

Recommended: square images, minimum 200×200px. The dashboard falls back to emoji if the image is missing.

### 6. Register Family Members in the Bot

1. Start the bot — each family member messages it on Telegram
2. Each member uses `/whoami` to get their Telegram user ID
3. Edit `bot/bot.py` → `FAMILY_MEMBERS` dict:

```python
FAMILY_MEMBERS = {
    123456789: "maurizio",    # ← replace with real IDs
    234567890: "alessandra",
    345678901: "flavio",
    456789012: "ada",
}
```

### 7. Run the Telegram Bot

**On Raspberry Pi or any Linux server:**

```bash
cd bot/
pip install -r requirements.txt

# Set environment variables
export TELEGRAM_TOKEN="your_token"
export GITHUB_TOKEN="your_github_token"
export GITHUB_REPO="yourusername/family-dashboard"
export OWM_API_KEY="your_owm_key"

python bot.py
```

**Run as a systemd service (recommended for Raspberry Pi):**

```ini
# /etc/systemd/system/family-dashboard-bot.service
[Unit]
Description=Family Dashboard Telegram Bot
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/family-dashboard/bot
Environment=TELEGRAM_TOKEN=xxx
Environment=GITHUB_TOKEN=xxx
Environment=GITHUB_REPO=yourusername/family-dashboard
Environment=OWM_API_KEY=xxx
ExecStart=/usr/bin/python3 /home/pi/family-dashboard/bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable family-dashboard-bot
sudo systemctl start family-dashboard-bot
```

---

## Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Open the interactive menu |
| `/whoami` | Show your Telegram ID |
| `/status 🏠 A casa` | Quick-update your status |
| `/reminder <text> [alta/media/bassa]` | Add a shared reminder |
| `/menu pranzo: pasta \| cena: pollo` | Update today's menu |
| `/clearreminders` | Clear all reminders (admin only) |
| `/help` | Show all commands |
| `/cancel` | Cancel current operation |

**Interactive menu** (via `/start`):
- Update today's / tomorrow's schedule
- Change status and mood
- Edit personal notes and bio
- Add reminders
- Update family menu and notes
- Refresh weather

---

## Customizing the Dashboard

### Change family name / location
Edit `data/dashboard.json`:
```json
"config": {
  "family_name": "YourName",
  "location": { "city": "YourCity", "lat": 0.0, "lon": 0.0 }
}
```

### Add/remove a member
Add a new key under `members` in `dashboard.json` following the existing structure.
Also add them to `MEMBER_ORDER` in `index.html` and `FAMILY_MEMBERS` in `bot.py`.

### Change update schedule
Edit `.github/workflows/update-dashboard.yml` → the `cron` lines.

### Themes
Four built-in themes (Warm, Cool, Nature, Dark) selectable from the header.
The choice is saved in `localStorage` per browser.
To add custom themes, extend the CSS variables in `index.html`.

---

## Data Format Summary

`data/dashboard.json` is the single source of truth.

```
_meta          → last_updated timestamp, version
config         → family_name, location (city, lat, lon)
shared
  ├── weather         → today + tomorrow (temp, description, icon, humidity, wind)
  ├── menu_of_the_day → date, lunch, dinner, notes  [auto-reset daily]
  ├── reminders[]     → id, text, priority, added_by, added_at
  └── notes           → free text
members
  └── <id>
       ├── display_name, emoji, color_theme (blue/rose/green/purple)
       ├── bio, avatar (path)
       ├── today   → date, schedule[], status, mood
       ├── tomorrow→ date, schedule[], status
       └── personal_notes
```

---

## License

MIT — free to use and adapt for your family!
