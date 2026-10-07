> 🇮🇹 [Versione italiana](README.md)

# 🏡 Family Dashboard

A self-updating family dashboard published on GitHub Pages, with a Telegram bot for data entry.

## Features

- **4 member cards** (Maurizio, Alessandra, Flavio, Ada) each with avatar, bio, today/tomorrow schedule, status, mood, personal notes
- **Shared sections**: Weather (Altopascio), Menu of the Day (daily reset), Reminders, Family Notes
- **🌡️ Home Sensors (Domoticz)**: temperature, humidity and battery level per room, with colored cards, room icons, and low-battery visual alerts
- **📚 Flavio's School Register (Argo Didup)**: weekly homework, reminders — auto-integrated into personal notes and shared reminders
- **🎨 Ada's School Register (ClasseViva)**: today/tomorrow lessons with topics, homework, grades, noticeboard, disciplinary notes, absences — all rendered in Ada's card
- **📅 Google Calendar (Family)**: events from the shared family calendar automatically distributed to member cards
- **🚏 Flavio's Transport**: recommended trains Lucca → Altopascio table with current-day highlighting
- **4 visual themes**: Warm 🌅, Cool 🌊, Nature 🌿, Dark 🌙 (persisted per-browser)
- **Auto-updates**: 2× per day (07:30 + 15:00) via PicoClaw 🦞 on Raspberry Pi
- **Telegram bot** for all family members to update content from their phones
- **Weather** via Open-Meteo (free, no API key required)
- **Zero backend** — pure static site + JSON + local update script

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
├── scripts/
│   ├── update-dashboard.py       ← Main data update script
│   └── github-push.py            ← Auto-push to GitHub
├── bot/
│   ├── bot.py                    ← Telegram bot (run on Raspberry Pi / VPS)
│   ├── fetch_weather.py          ← Weather fetcher
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

## Data Integrations

### 🌡️ Domoticz (Home Sensors)

The dashboard reads temperature and humidity sensors from a local [Domoticz](https://www.domoticz.com/) instance.

**Setup:**
1. Create `.domoticz-credentials` in the PicoClaw workspace root:
```
DOMOTICZ_URL=http://localhost:9090
DOMOTICZ_USER=admin
DOMOTICZ_PASS=your_password
```
2. Temp+Humidity sensors are auto-detected
3. Cards show: temperature (with color-coded top bar by range), humidity, battery level with visual alert

**Battery thresholds:**
- 🔋 > 30% → normal (grey)
- 🔋 15–30% → low (orange)
- 🪫 < 15% → critical (red, pulsing)

### 📚 Argo Didup (Flavio's School Register)

Integration with the Argo Didup Famiglia electronic register for Liceo Passaglia.
- **Weekly homework** → Flavio's personal notes
- **Reminders** → shared reminders section (past-due items filtered out)

### 🎨 ClasseViva (Ada's School Register)

Integration with the ClasseViva (Spaggiari) electronic register for primary school.
- **Today/tomorrow lessons** with topics and teachers
- **Homework and agenda** (14-day lookahead)
- **Grades** with color indicator
- **Noticeboard** communications
- **Disciplinary notes** and **absences**

### 📅 Google Calendar

Family calendar events automatically distributed to member cards.
- Parents (Maurizio, Alessandra) see **all** events
- Children see only events matching their name
- Service Account configured with shared calendar access

### 🌤️ Weather (Open-Meteo)

Free weather forecasts via [Open-Meteo](https://open-meteo.com/), no API key needed.
- Today and tomorrow: min/max temperature, humidity, wind, precipitation
- OpenWeatherMap icons for visual compatibility

### 🚏 Flavio's Transport

Recommended trains Lucca → Altopascio table for each day of the week.
- Auto-highlighting of the current day
- Exit times, recommended transport, notes and alternatives

---

## Data Format Summary

`data/dashboard.json` is the single source of truth.

```
_meta          → last_updated timestamp, version
config         → family_name, location (city, lat, lon)
shared
  ├── weather           → today + tomorrow (temp, description, icon, humidity, wind, precipitation)
  ├── sensors[]         → Domoticz: id, name, icon, temp, humidity, battery, last_update, battery_warning
  ├── menu_of_the_day   → date, lunch, dinner, notes  [auto-reset daily]
  ├── reminders[]       → id, text, priority, added_by, added_at
  ├── calendar_events   → today[], tomorrow[] (time, event, all_day, summary)
  └── notes             → free text
members
  └── <id>
       ├── display_name, emoji, color_theme (blue/rose/green/purple)
       ├── bio, avatar (path)
       ├── today       → date, schedule[], status, mood
       ├── tomorrow    → date, schedule[], status
       ├── transport[] → [Flavio only] day, exit_time, mode, departure, arrival, notes
       ├── school_data → [Ada only] lezioni_oggi[], lezioni_domani[], agenda[], voti[], bacheca[], note[], assenze_count
       └── personal_notes
```

---

## License

MIT — free to use and adapt for your family!
