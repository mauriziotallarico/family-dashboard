#!/usr/bin/env python3
"""
Family Dashboard Updater — run by PicoClaw at regular intervals.
Populates data/dashboard.json with real data from:
  - Family schedules (from memory files)
  - Weather (Open-Meteo, no API key needed)
  - Didup registro elettronico (Flavio's school data)
  - Google Calendar (future)

Usage:
    python3 scripts/update-dashboard.py
"""

import json
import os
import sys
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).parent
REPO_DIR = SCRIPT_DIR.parent
WORKSPACE = Path(os.environ.get("PICOCLAW_WORKSPACE", str(REPO_DIR.parent)))
DATA_PATH = REPO_DIR / "data" / "dashboard.json"
MEMORY_DIR = WORKSPACE / "memory"

# Day names in Italian
GIORNI_IT = {
    0: "Lunedì", 1: "Martedì", 2: "Mercoledì",
    3: "Giovedì", 4: "Venerdì", 5: "Sabato", 6: "Domenica"
}

# WMO weather code descriptions (Italian)
WMO_DESCRIPTIONS = {
    0: "Sereno", 1: "Prevalentemente sereno", 2: "Parzialmente nuvoloso",
    3: "Nuvoloso", 45: "Nebbia", 48: "Nebbia con brina",
    51: "Pioviggine leggera", 53: "Pioviggine", 55: "Pioviggine intensa",
    61: "Pioggia leggera", 63: "Pioggia", 65: "Pioggia intensa",
    71: "Neve leggera", 73: "Neve", 75: "Neve intensa",
    80: "Rovesci leggeri", 81: "Rovesci", 82: "Rovesci intensi",
    95: "Temporale", 96: "Temporale con grandine", 99: "Temporale con grandine intensa",
}

WMO_ICONS = {
    0: "01d", 1: "02d", 2: "03d", 3: "04d",
    45: "50d", 48: "50d",
    51: "09d", 53: "09d", 55: "09d",
    61: "10d", 63: "10d", 65: "10d",
    71: "13d", 73: "13d", 75: "13d",
    80: "09d", 81: "09d", 82: "09d",
    95: "11d", 96: "11d", 99: "11d",
}


def today_date():
    return date.today()

def tomorrow_date():
    return date.today() + timedelta(days=1)

def day_name(d):
    return GIORNI_IT.get(d.weekday(), "?")


# ===== WEATHER (Open-Meteo, free, no key) =====

def fetch_weather():
    """Fetch weather from Open-Meteo for Altopascio."""
    import urllib.request
    url = (
        "https://api.open-meteo.com/v1/forecast?"
        "latitude=43.8135&longitude=10.6773"
        "&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum"
        "&forecast_days=2&timezone=Europe/Rome"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        
        weather = {}
        for i, label in enumerate(["today", "tomorrow"]):
            wcode = data["daily"]["weather_code"][i]
            weather[label] = {
                "date": data["daily"]["time"][i],
                "description": WMO_DESCRIPTIONS.get(wcode, f"Codice {wcode}"),
                "temp_min": round(data["daily"]["temperature_2m_min"][i]),
                "temp_max": round(data["daily"]["temperature_2m_max"][i]),
                "icon": WMO_ICONS.get(wcode, "03d"),
                "humidity": data["current"]["relative_humidity_2m"] if i == 0 else 0,
                "wind_speed": round(data["current"]["wind_speed_10m"]) if i == 0 else 0,
                "precipitation_mm": data["daily"]["precipitation_sum"][i],
            }
        return weather
    except Exception as e:
        print(f"⚠️  Weather fetch failed: {e}")
        return None


# ===== FLAVIO SCHEDULE =====

FLAVIO_ORARIO = {
    "Lunedì": [
        {"time": "08:10", "event": "Storia e Geografia — Rossi M."},
        {"time": "09:10", "event": "TAC — Meli A."},
        {"time": "10:10", "event": "Inglese — Febi R."},
        {"time": "11:10", "event": "Storia della Musica — Mascolo F."},
        {"time": "12:10", "event": "Religione — Battaglia M."},
        {"time": "14:10", "event": "Pianoforte (2° str.) — Pieruccioni L."},
        {"time": "15:10", "event": "Sax — Mazzola M."},
    ],
    "Martedì": [
        {"time": "08:10", "event": "Scienze — Lovi I."},
        {"time": "09:10", "event": "Storia della Musica — Mascolo F."},
        {"time": "10:10", "event": "Italiano — Moncini M."},
        {"time": "11:10", "event": "Storia dell'Arte — Lorenzini M."},
        {"time": "12:10", "event": "Matematica — Marini F."},
    ],
    "Mercoledì": [
        {"time": "08:10", "event": "Scienze — Lovi I."},
        {"time": "09:10", "event": "Inglese — Febi R."},
        {"time": "10:10", "event": "Matematica (2h) — Marini F."},
        {"time": "13:10", "event": "Sax — Mazzola M."},
        {"time": "14:10", "event": "Quartetto Sax Junior — Mazzola M."},
    ],
    "Giovedì": [
        {"time": "08:10", "event": "TEM (2h) — Giusti M."},
        {"time": "10:10", "event": "Storia e Geografia — Rossi M."},
        {"time": "11:10", "event": "Inglese — Febi R."},
        {"time": "12:10", "event": "Italiano — Moncini M."},
        {"time": "13:10", "event": "Orchestra di Fiati — Gaggini E."},
    ],
    "Venerdì": [
        {"time": "08:10", "event": "TAC (2h) — Meli A."},
        {"time": "10:10", "event": "Motorie (2h) — Tedeschi B."},
    ],
    "Sabato": [
        {"time": "08:10", "event": "Storia e Geografia — Rossi M."},
        {"time": "09:10", "event": "Italiano (2h) — Moncini M."},
        {"time": "11:10", "event": "Storia dell'Arte — Lorenzini M."},
    ],
}

FLAVIO_TRASPORTI = {
    "Lunedì": "🚌 Bus 851 (16:35 P.le Verdi → 16:49 Altopascio)",
    "Martedì": "🚌 Bus 851 (14:15 P.le Verdi → 14:29 Altopascio)",
    "Mercoledì": "🚆 Treno (15:39 Stazione → 15:54 Altopascio)",
    "Giovedì": "🚌 Bus 851 (14:15 P.le Verdi → 14:29 Altopascio)",
    "Venerdì": "🚆 Treno (12:31 Stazione → 12:40 Altopascio)",
    "Sabato": "🚆 Treno (12:31 Stazione → 12:40 Altopascio)",
}

FLAVIO_USCITA = {
    "Lunedì": "~16:20", "Martedì": "~13:10", "Mercoledì": "~15:20",
    "Giovedì": "~14:10", "Venerdì": "~12:10", "Sabato": "~12:10",
}


def get_flavio_schedule(d):
    giorno = day_name(d)
    if giorno == "Domenica":
        return [], "🏠 A casa", ""
    
    schedule = list(FLAVIO_ORARIO.get(giorno, []))
    trasporto = FLAVIO_TRASPORTI.get(giorno, "")
    uscita = FLAVIO_USCITA.get(giorno, "")
    
    if trasporto and uscita:
        schedule.append({"time": uscita.replace("~", ""), "event": f"Ritorno: {trasporto}"})
    
    status = f"🏫 Scuola — Uscita {uscita}" if giorno != "Domenica" else "🏠 A casa"
    return schedule, status, trasporto


# ===== ALESSANDRA SCHEDULE =====

ALESSANDRA_ORARIO = {
    "Lunedì": [
        {"time": "08:00", "event": "Scuola: 2B (1ª ora)"},
        {"time": "09:00", "event": "Scuola: 2B (2ª ora)"},
        {"time": "10:00", "event": "Scuola: 2B (3ª ora)"},
        {"time": "11:00", "event": "Scuola: 1B (4ª ora)"},
    ],
    "Martedì": [
        {"time": "08:00", "event": "Scuola: 2B (1ª ora)"},
        {"time": "09:00", "event": "Scuola: 1B (2ª ora)"},
        {"time": "10:00", "event": "Scuola: 1B (3ª ora)"},
    ],
    "Mercoledì": [
        {"time": "08:00", "event": "Scuola: 1B (1ª ora)"},
        {"time": "09:00", "event": "Scuola: 1B (2ª ora)"},
        {"time": "12:00", "event": "Scuola: 2B (5ª ora)"},
        {"time": "13:00", "event": "Scuola: 2B (6ª ora)"},
    ],
    "Giovedì": [
        {"time": "10:00", "event": "Scuola: 2B (3ª ora)"},
        {"time": "11:00", "event": "Scuola: 2B (4ª ora)"},
        {"time": "13:00", "event": "Scuola: 1B (6ª ora)"},
    ],
    "Venerdì": [
        {"time": "09:00", "event": "Scuola: 2B (2ª ora)"},
        {"time": "10:00", "event": "Scuola: 2B (3ª ora)"},
        {"time": "11:00", "event": "Scuola: 1B (4ª ora)"},
        {"time": "12:00", "event": "Scuola: 1B (5ª ora)"},
    ],
}


def get_alessandra_schedule(d):
    giorno = day_name(d)
    if giorno in ("Sabato", "Domenica"):
        return [], "🏠 A casa"
    schedule = list(ALESSANDRA_ORARIO.get(giorno, []))
    if schedule:
        status = f"👩‍🏫 Scuola Valchiusa — {len(schedule)} ore"
    else:
        status = "🏠 A casa"
    return schedule, status


# ===== ADA SCHEDULE =====

ADA_ORARIO = {
    "Lunedì":    {"ingresso": "08:15", "uscita": "16:15", "tipo": "giorno lungo"},
    "Martedì":   {"ingresso": "08:15", "uscita": "13:15", "tipo": "giorno corto"},
    "Mercoledì": {"ingresso": "08:15", "uscita": "13:15", "tipo": "giorno corto"},
    "Giovedì":   {"ingresso": "08:15", "uscita": "16:15", "tipo": "giorno lungo"},
    "Venerdì":   {"ingresso": "08:15", "uscita": "12:15", "tipo": "giorno corto"},
}


def get_ada_schedule(d):
    giorno = day_name(d)
    if giorno in ("Sabato", "Domenica"):
        return [], "🏠 A casa"
    
    info = ADA_ORARIO.get(giorno)
    if not info:
        return [], "🏠 A casa"
    
    schedule = [
        {"time": info["ingresso"], "event": "Ingresso scuola"},
        {"time": info["uscita"], "event": f"Uscita scuola ({info['tipo']})"},
    ]
    status = f"🏫 Scuola — Uscita {info['uscita']}"
    return schedule, status


# ===== DIDUP (Flavio's school data) =====

def fetch_didup_data():
    """Fetch homework and reminders from Didup."""
    didup_cmd = "python3 skills/didup/didup-query"
    results = {"compiti": [], "promemoria": []}
    
    try:
        # Compiti settimana
        out = subprocess.run(
            f"{didup_cmd} compiti-settimana".split(),
            capture_output=True, text=True, timeout=30,
            cwd=str(WORKSPACE)
        )
        if out.returncode == 0:
            for line in out.stdout.strip().splitlines():
                line = line.strip()
                if line.startswith("📝"):
                    line = line[2:].strip()
                    parts = line.split(" | ", 1)
                    if len(parts) == 2:
                        results["compiti"].append({
                            "date": parts[0].strip(),
                            "text": parts[1].strip()[:200],
                        })
        
        # Promemoria
        out = subprocess.run(
            f"{didup_cmd} promemoria".split(),
            capture_output=True, text=True, timeout=30,
            cwd=str(WORKSPACE)
        )
        if out.returncode == 0:
            for line in out.stdout.strip().splitlines():
                line = line.strip()
                if line.startswith("📅"):
                    line = line[2:].strip()
                    results["promemoria"].append(line[:200])
    except Exception as e:
        print(f"⚠️  Didup fetch failed: {e}")
    
    return results


# ===== MAIN UPDATE =====

def build_dashboard():
    today = today_date()
    tomorrow = tomorrow_date()
    today_str = today.isoformat()
    tomorrow_str = tomorrow.isoformat()
    giorno_oggi = day_name(today)
    giorno_domani = day_name(tomorrow)
    
    print(f"📊 Building dashboard for {today_str} ({giorno_oggi})")
    
    # Weather
    print("🌤️  Fetching weather...")
    weather = fetch_weather()
    
    # Didup
    print("📚 Fetching Didup data...")
    didup = fetch_didup_data()
    
    # Flavio
    flavio_today_sched, flavio_today_status, _ = get_flavio_schedule(today)
    flavio_tomorrow_sched, flavio_tomorrow_status, _ = get_flavio_schedule(tomorrow)
    
    # Alessandra
    ale_today_sched, ale_today_status = get_alessandra_schedule(today)
    ale_tomorrow_sched, ale_tomorrow_status = get_alessandra_schedule(tomorrow)
    
    # Ada
    ada_today_sched, ada_today_status = get_ada_schedule(today)
    ada_tomorrow_sched, ada_tomorrow_status = get_ada_schedule(tomorrow)
    
    # Build reminders from Didup
    reminders = []
    for i, p in enumerate(didup.get("promemoria", [])):
        reminders.append({
            "id": f"didup_{i}",
            "text": f"📚 {p}",
            "priority": "high",
            "added_by": "picoclaw",
            "added_at": datetime.now().isoformat(),
        })
    
    # Build Flavio personal notes from homework
    compiti_lines = []
    for c in didup.get("compiti", [])[:8]:
        compiti_lines.append(f"📝 {c['date']}: {c['text'][:100]}")
    flavio_notes = "\n".join(compiti_lines) if compiti_lines else "Nessun compito registrato"
    
    # Dashboard JSON
    dashboard = {
        "_meta": {
            "last_updated": datetime.now().isoformat(),
            "version": "2.0",
            "updated_by": "picoclaw"
        },
        "config": {
            "family_name": "Tallarico",
            "theme": "warm",
            "location": {
                "city": "Altopascio",
                "country": "IT",
                "lat": 43.8135,
                "lon": 10.6773
            }
        },
        "shared": {
            "menu_of_the_day": {
                "date": today_str,
                "lunch": "",
                "dinner": "",
                "notes": ""
            },
            "reminders": reminders,
            "notes": "",
            "weather": weather or {}
        },
        "members": {
            "maurizio": {
                "display_name": "Maurizio",
                "emoji": "👨‍💻",
                "color_theme": "blue",
                "bio": "Software Engineer. Papà di Flavio e Ada. Creatore di PicoClaw 🦞",
                "avatar": "assets/images/maurizio.jpg",
                "today": {
                    "date": today_str,
                    "schedule": [],
                    "status": "💼 Lavoro",
                    "mood": "😊"
                },
                "tomorrow": {
                    "date": tomorrow_str,
                    "schedule": [],
                    "status": ""
                },
                "personal_notes": ""
            },
            "alessandra": {
                "display_name": "Alessandra",
                "emoji": "👩‍🏫",
                "color_theme": "rose",
                "bio": "Prof.ssa — Classi 1B e 2B, Scuola Valchiusa. Mamma di Flavio e Ada.",
                "avatar": "assets/images/alessandra.jpg",
                "today": {
                    "date": today_str,
                    "schedule": ale_today_sched,
                    "status": ale_today_status,
                    "mood": ""
                },
                "tomorrow": {
                    "date": tomorrow_str,
                    "schedule": ale_tomorrow_sched,
                    "status": ale_tomorrow_status
                },
                "personal_notes": ""
            },
            "flavio": {
                "display_name": "Flavio",
                "emoji": "🎷",
                "color_theme": "green",
                "bio": "Liceo Artistico Musicale Passaglia, Classe 1M. Sax e Pianoforte.",
                "avatar": "assets/images/flavio.jpg",
                "today": {
                    "date": today_str,
                    "schedule": flavio_today_sched,
                    "status": flavio_today_status,
                    "mood": ""
                },
                "tomorrow": {
                    "date": tomorrow_str,
                    "schedule": flavio_tomorrow_sched,
                    "status": flavio_tomorrow_status
                },
                "personal_notes": flavio_notes
            },
            "ada": {
                "display_name": "Ada",
                "emoji": "🎨",
                "color_theme": "purple",
                "bio": "Scuola primaria. Ama disegnare e giocare.",
                "avatar": "assets/images/ada.jpg",
                "today": {
                    "date": today_str,
                    "schedule": ada_today_sched,
                    "status": ada_today_status,
                    "mood": ""
                },
                "tomorrow": {
                    "date": tomorrow_str,
                    "schedule": ada_tomorrow_sched,
                    "status": ada_tomorrow_status
                },
                "personal_notes": ""
            }
        }
    }
    
    return dashboard


def main():
    dashboard = build_dashboard()
    
    # Write JSON
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Dashboard written to {DATA_PATH}")
    
    # Summary
    for member_id, member in dashboard["members"].items():
        today = member.get("today", {})
        n_events = len(today.get("schedule", []))
        print(f"   {member['emoji']} {member['display_name']}: {n_events} eventi oggi — {today.get('status', '')}")
    
    weather = dashboard["shared"].get("weather", {})
    if "today" in weather:
        w = weather["today"]
        print(f"   🌤️ Meteo: {w['description']}, {w['temp_min']}°–{w['temp_max']}°C")
    
    reminders = dashboard["shared"].get("reminders", [])
    print(f"   🔔 {len(reminders)} promemoria")


if __name__ == "__main__":
    main()
