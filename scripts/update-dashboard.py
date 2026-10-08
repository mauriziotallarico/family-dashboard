#!/usr/bin/env python3
"""
Family Dashboard Updater — run by PicoClaw at regular intervals.
Populates data/dashboard.json with real data from:
  - Family schedules (from memory files)
  - Weather (Open-Meteo, no API key needed)
  - Didup registro elettronico (Flavio's school data)
  - Google Calendar (family events)

Usage:
    python3 scripts/update-dashboard.py
"""

import json
import os
import re
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

# Google Calendar
FAMILY_CALENDAR_ID = "family02997430890770199008@group.calendar.google.com"
GCAL_PYTHON = str(WORKSPACE / ".venv" / "bin" / "python3")
GCAL_SCRIPT = str(WORKSPACE / "skills" / "google-calendar" / "gcal.py")

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


# ===== DOMOTICZ SENSORS =====

DOMOTICZ_ROOM_ICONS = {
    "Corridoio": "🚪",
    "Studio": "💻",
    "Camera Matrimoniale": "🛏️",
}


def fetch_domoticz_sensors():
    """Fetch temperature/humidity sensors from Domoticz."""
    import urllib.request
    import base64

    creds_path = WORKSPACE / ".domoticz-credentials"
    if not creds_path.exists():
        print("⚠️  Domoticz credentials not found")
        return []

    creds = {}
    for line in creds_path.read_text().strip().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            creds[k.strip()] = v.strip()

    domoticz_url = creds.get("DOMOTICZ_URL", "http://localhost:9090")
    domoticz_user = creds.get("DOMOTICZ_USER", "")
    domoticz_pass = creds.get("DOMOTICZ_PASS", "")

    url = f"{domoticz_url}/json.htm?type=command&param=getdevices&used=true&order=Name"

    try:
        req = urllib.request.Request(url)
        if domoticz_user:
            auth_str = base64.b64encode(f"{domoticz_user}:{domoticz_pass}".encode()).decode()
            req.add_header("Authorization", f"Basic {auth_str}")

        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        sensors = []
        for device in data.get("result", []):
            # Only Temp+Humidity sensors
            if device.get("Type", "") not in ("Temp + Humidity",):
                continue

            idx = str(device.get("idx", ""))
            name = device.get("Name", f"Sensor {idx}")
            temp = device.get("Temp", 0)
            humidity = device.get("Humidity", 0)
            battery = device.get("BatteryLevel", 255)
            last_update = device.get("LastUpdate", "")
            icon = DOMOTICZ_ROOM_ICONS.get(name, "🏠")

            sensors.append({
                "id": idx,
                "name": name,
                "icon": icon,
                "temp": round(temp, 1),
                "humidity": int(humidity),
                "battery": int(battery),
                "last_update": last_update,
                "battery_warning": battery < 20,
            })

        return sensors

    except Exception as e:
        print(f"⚠️  Domoticz fetch failed: {e}")
        return []

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
    ],
    "Martedì": [
        {"time": "08:10", "event": "Scienze — Lovi I."},
        {"time": "09:10", "event": "Storia della Musica — Mascolo F."},
        {"time": "10:10", "event": "Italiano — Moncini M."},
        {"time": "11:10", "event": "Storia dell'Arte — Lorenzini M."},
        {"time": "12:10", "event": "Matematica — Marini F."},
        {"time": "14:10", "event": "Sax — Mazzola M."},
    ],
    "Mercoledì": [
        {"time": "08:10", "event": "Scienze — Lovi I."},
        {"time": "09:10", "event": "Inglese — Febi R."},
        {"time": "10:10", "event": "Matematica (2h) — Marini F."},
        {"time": "14:30", "event": "Sax — Mazzola M. 📍 Fillungo"},
        {"time": "15:30", "event": "Quartetto Sax Junior — Mazzola M. 📍 Fillungo"},
    ],
    "Giovedì": [
        {"time": "08:10", "event": "TEM (2h) — Giusti M."},
        {"time": "10:10", "event": "Storia e Geografia — Rossi M."},
        {"time": "11:10", "event": "Inglese — Febi R."},
        {"time": "12:10", "event": "Italiano — Moncini M."},
        {"time": "14:10", "event": "Orchestra di Fiati — Cesari D., Fortino S., Gaggini E., Manente D."},
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
    "Lunedì": "🚆 Treno 15:31 (Stazione FS → 15:40 Altopascio) ⭐",
    "Martedì": "🚆 Treno 15:31 (Stazione FS → 15:40 Altopascio) ⭐",
    "Mercoledì": "🚆 Treno 16:31 (Stazione FS → 16:40 Altopascio)",
    "Giovedì": "🚆 Treno 14:31 (Stazione FS → 14:40 Altopascio)",
    "Venerdì": "🚆 Treno 12:31 (Stazione FS → 12:40 Altopascio)",
    "Sabato": "🚆 Treno 12:31 (Stazione FS → 12:40 Altopascio)",
}

FLAVIO_USCITA = {
    "Lunedì": "~15:10", "Martedì": "~15:10", "Mercoledì": "~15:30",
    "Giovedì": "~14:10", "Venerdì": "~12:10", "Sabato": "~12:10",
}

# Structured transport recommendations for dashboard table
FLAVIO_TRASPORTI_TABLE = [
    {
        "day": "Lunedì",
        "exit_time": "~15:10",
        "exit_place": "S. Agostino",
        "mode": "train",
        "mode_label": "🚆 Treno",
        "departure": "15:31",
        "departure_place": "Stazione FS Lucca",
        "arrival": "15:40",
        "arrival_place": "Altopascio",
        "line": "Treno regionale",
        "notes": "⭐ Ideale! 15 min a piedi per stazione. Backup: treno 15:39 (arrivo 15:54)",
    },
    {
        "day": "Martedì",
        "exit_time": "~15:10",
        "exit_place": "S. Agostino",
        "mode": "train",
        "mode_label": "🚆 Treno",
        "departure": "15:31",
        "departure_place": "Stazione FS Lucca",
        "arrival": "15:40",
        "arrival_place": "Altopascio",
        "line": "Treno regionale",
        "notes": "⭐ Ideale! 15 min a piedi per stazione. Backup: treno 15:39 (arrivo 15:54)",
    },
    {
        "day": "Mercoledì",
        "exit_time": "~15:30",
        "exit_place": "Fillungo",
        "mode": "train",
        "mode_label": "🚆 Treno",
        "departure": "16:31",
        "departure_place": "Stazione FS Lucca",
        "arrival": "16:40",
        "arrival_place": "Altopascio",
        "line": "Treno regionale",
        "notes": "20 min a piedi per stazione, ~40 min attesa. Alternativa: bus 851 (16:35 P.le Verdi)",
    },
    {
        "day": "Giovedì",
        "exit_time": "~14:10",
        "exit_place": "S. Agostino",
        "mode": "train",
        "mode_label": "🚆 Treno",
        "departure": "14:31",
        "departure_place": "Stazione FS Lucca",
        "arrival": "14:40",
        "arrival_place": "Altopascio",
        "line": "Treno regionale",
        "notes": "15 min a piedi per stazione. Alternativa: bus 851 (14:15 P.le Verdi, strettissimo)",
    },
    {
        "day": "Venerdì",
        "exit_time": "~12:10",
        "exit_place": "Cavallerizza",
        "mode": "train",
        "mode_label": "🚆 Treno",
        "departure": "12:31",
        "departure_place": "Stazione FS Lucca",
        "arrival": "12:40",
        "arrival_place": "Altopascio",
        "line": "Treno regionale",
        "notes": "Treno nettamente migliore (bus solo alle 14:15)",
    },
    {
        "day": "Sabato",
        "exit_time": "~12:10",
        "exit_place": "S. Agostino",
        "mode": "train",
        "mode_label": "🚆 Treno",
        "departure": "12:31",
        "departure_place": "Stazione FS Lucca",
        "arrival": "12:40",
        "arrival_place": "Altopascio",
        "line": "Treno regionale",
        "notes": "Treno nettamente migliore (bus solo alle 14:15)",
    },
]


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


# ===== CLASSEVIVA (Ada's school data) =====

def fetch_classeviva_data():
    """Fetch lessons, agenda, grades, absences, noticeboard from ClasseViva for Ada.
    
    Uses the Python API directly for structured data instead of CLI parsing.
    """
    results = {
        "lezioni_oggi": [],       # list of {"ora": int, "materia": str, "docente": str, "argomento": str}
        "lezioni_domani": [],     # same structure
        "agenda": [],             # list of {"data": str, "testo": str, "autore": str}
        "voti": [],               # list of {"data": str, "materia": str, "voto": str, "note": str, "colore": str}
        "assenze": [],            # list of {"data": str, "tipo": str, "giustificata": bool}
        "bacheca": [],            # list of {"data": str, "titolo": str, "letta": bool}
        "note": [],               # list of {"data": str, "tipo": str, "autore": str, "testo": str}
    }

    try:
        import importlib.machinery
        mod = importlib.machinery.SourceFileLoader(
            'classeviva_mod',
            str(WORKSPACE / 'skills' / 'classeviva' / 'classeviva-query')
        ).load_module()
        
        creds = mod.load_credentials()
        client = mod.ClasseVivaClient(creds['CLASSEVIVA_USERNAME'], creds['CLASSEVIVA_PASSWORD'])
        client.login()
        
        today = date.today()
        tomorrow = today + timedelta(days=1)
        
        # Lezioni di oggi
        for lesson in client.lessons_today():
            results["lezioni_oggi"].append({
                "ora": lesson.get("evtHPos", 0),
                "materia": lesson.get("subjectDesc", "?"),
                "docente": lesson.get("authorName", "?"),
                "argomento": lesson.get("lessonArg", ""),
            })
        results["lezioni_oggi"].sort(key=lambda x: x["ora"])
        
        # Lezioni di domani
        for lesson in client.lessons_day(tomorrow.isoformat()):
            results["lezioni_domani"].append({
                "ora": lesson.get("evtHPos", 0),
                "materia": lesson.get("subjectDesc", "?"),
                "docente": lesson.get("authorName", "?"),
                "argomento": lesson.get("lessonArg", ""),
            })
        results["lezioni_domani"].sort(key=lambda x: x["ora"])
        
        # Agenda prossimi 14 giorni (compiti e impegni)
        start = today.isoformat()
        end = (today + timedelta(days=14)).isoformat()
        for item in client.agenda(start, end):
            results["agenda"].append({
                "data": item.get("evtDatetimeBegin", "")[:10],
                "testo": item.get("notes", ""),
                "autore": item.get("authorName", ""),
            })
        
        # Voti
        for g in client.grades():
            results["voti"].append({
                "data": g.get("evtDate", ""),
                "materia": g.get("subjectDesc", "?"),
                "voto": g.get("displayValue", g.get("decimalValue", "?")),
                "note": g.get("notesForFamily", ""),
                "colore": g.get("color", ""),
            })
        results["voti"].sort(key=lambda x: x["data"], reverse=True)
        
        # Assenze
        for e in client.absences():
            results["assenze"].append({
                "data": e.get("evtDate", ""),
                "tipo": e.get("evtCode", ""),
                "giustificata": e.get("isJustified", False),
            })
        
        # Bacheca (ultime 5 comunicazioni)
        for b in client.noticeboard()[:5]:
            results["bacheca"].append({
                "data": b.get("pubDT", "")[:10],
                "titolo": b.get("cntTitle", ""),
                "letta": b.get("readStatus", False),
            })
        
        # Note disciplinari
        notes_data = client.notes()
        if notes_data:
            for key, label in [("NTTE", "Docente"), ("NTCL", "Classe"),
                               ("NTWN", "Richiamo"), ("NTST", "Sanzione")]:
                for n in notes_data.get(key, []):
                    results["note"].append({
                        "data": n.get("evtDate", ""),
                        "tipo": label,
                        "autore": n.get("authorName", ""),
                        "testo": n.get("readNote", n.get("evtText", "")),
                    })
    
    except Exception as e:
        print(f"⚠️  ClasseViva fetch failed: {e}")
        import traceback
        traceback.print_exc()

    return results


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


# ===== GOOGLE CALENDAR (Family events) =====

# Keywords to associate events with family members
MEMBER_KEYWORDS = {
    "flavio":     ["flavio", "pallavolo flavio"],
    "ada":        ["ada"],
    "alessandra": ["alessandra", "ale"],
    "maurizio":   ["maurizio", "papà"],
}


def fetch_calendar_events(target_dates):
    """Fetch family calendar events for the given dates (list of date objects).
    
    Returns a dict keyed by date ISO string, each value is a list of event dicts:
      {"time": "HH:MM", "end_time": "HH:MM", "event": "...", "all_day": bool, "members": [...]}
    """
    if not target_dates:
        return {}

    # We need enough days to cover today+tomorrow
    days_ahead = (max(target_dates) - min(target_dates)).days + 1
    days_ahead = max(days_ahead, 2)
    from_date = min(target_dates).isoformat()

    cmd = [GCAL_PYTHON, GCAL_SCRIPT, "list",
           "--from-date", from_date,
           "--days", str(days_ahead),
           "--calendar", FAMILY_CALENDAR_ID]
    
    try:
        out = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=30,
            cwd=str(WORKSPACE)
        )
        if out.returncode != 0:
            print(f"⚠️  Google Calendar fetch failed: {out.stderr.strip()}")
            return {}
    except Exception as e:
        print(f"⚠️  Google Calendar fetch failed: {e}")
        return {}

    # Parse the gcal.py output
    events_by_date = {d.isoformat(): [] for d in target_dates}
    
    current_event = {}
    for line in out.stdout.splitlines():
        line = line.strip()
        if line.startswith("📅 "):
            # Save previous event
            if current_event:
                _store_event(current_event, events_by_date, target_dates)
            current_event = {"summary": line[2:].strip()}
        elif line.startswith("Start: "):
            current_event["start"] = line[7:].strip()
        elif line.startswith("End: "):
            current_event["end"] = line[5:].strip()
        elif line.startswith("Location: "):
            current_event["location"] = line[10:].strip()
        elif line.startswith("ID: "):
            current_event["id"] = line[4:].strip()
    
    # Don't forget last event
    if current_event:
        _store_event(current_event, events_by_date, target_dates)

    return events_by_date


def _store_event(raw, events_by_date, target_dates):
    """Parse a raw event dict and store it in events_by_date if it matches target dates."""
    start_str = raw.get("start", "")
    end_str = raw.get("end", "")
    summary = raw.get("summary", "")
    location = raw.get("location", "")

    all_day = False
    event_date = None
    time_str = ""
    end_time_str = ""

    if "T" in start_str:
        # Timed event: "2026-09-25T17:00:00+02:00"
        try:
            dt = datetime.fromisoformat(start_str)
            event_date = dt.date()
            time_str = dt.strftime("%H:%M")
        except ValueError:
            return
        if "T" in end_str:
            try:
                dt_end = datetime.fromisoformat(end_str)
                end_time_str = dt_end.strftime("%H:%M")
            except ValueError:
                pass
    else:
        # All-day event: "2026-09-27"
        all_day = True
        try:
            event_date = date.fromisoformat(start_str)
        except ValueError:
            return

    date_key = event_date.isoformat() if event_date else None
    if date_key not in events_by_date:
        return

    # Determine which members this event is relevant to
    members = _match_members(summary)

    event_label = f"📅 {summary}"
    if location:
        event_label += f" ({location})"

    event_obj = {
        "time": time_str if time_str else "tutto il giorno",
        "event": event_label,
        "all_day": all_day,
        "summary": summary,
        "members": members,
    }
    if end_time_str:
        event_obj["end_time"] = end_time_str

    events_by_date[date_key].append(event_obj)


def _match_members(summary):
    """Return list of member IDs that match the event summary, or all members if no match."""
    summary_lower = summary.lower()
    matched = []
    for member_id, keywords in MEMBER_KEYWORDS.items():
        for kw in keywords:
            if kw in summary_lower:
                matched.append(member_id)
                break
    # If no specific match, it's a family-wide event → all members
    if not matched:
        matched = list(MEMBER_KEYWORDS.keys())
    return matched


def _calendar_events_for_member(cal_events_for_date, member_id):
    """Filter calendar events for a specific member.
    
    Parents (maurizio, alessandra) see ALL family calendar events,
    regardless of member matching. Children only see events matched to them.
    """
    PARENTS = {"maurizio", "alessandra"}
    if member_id in PARENTS:
        # Parents see every event from the family calendar
        return [
            {"time": e["time"], "event": e["event"]}
            for e in cal_events_for_date
        ]
    else:
        return [
            {"time": e["time"], "event": e["event"]}
            for e in cal_events_for_date
            if member_id in e.get("members", [])
        ]


# ===== MAIN UPDATE =====

def build_dashboard():
    today = today_date()
    tomorrow = tomorrow_date()
    today_str = today.isoformat()
    tomorrow_str = tomorrow.isoformat()
    giorno_oggi = day_name(today)
    giorno_domani = day_name(tomorrow)
    
    print(f"📊 Building dashboard for {today_str} ({giorno_oggi})")
    
    # Track fetch errors for transparency on the dashboard
    fetch_errors = []  # list of {"source": str, "message": str, "timestamp": str}
    
    # Weather
    print("🌤️  Fetching weather...")
    weather = fetch_weather()
    if weather is None:
        fetch_errors.append({
            "source": "Meteo (Open-Meteo)",
            "message": "Impossibile recuperare dati meteo",
            "timestamp": datetime.now().isoformat(),
        })
    
    # Didup
    print("📚 Fetching Didup data...")
    didup = fetch_didup_data()
    if not didup.get("compiti") and not didup.get("promemoria"):
        fetch_errors.append({
            "source": "Registro Flavio (Argo Didup)",
            "message": "Nessun dato ricevuto — il registro potrebbe essere irraggiungibile",
            "timestamp": datetime.now().isoformat(),
        })
    
    # ClasseViva (Ada)
    print("🎨 Fetching ClasseViva data (Ada)...")
    classeviva = fetch_classeviva_data()
    _cv_has_data = any([
        classeviva.get("lezioni_oggi"),
        classeviva.get("lezioni_domani"),
        classeviva.get("agenda"),
        classeviva.get("voti"),
        classeviva.get("bacheca"),
        classeviva.get("note"),
        classeviva.get("assenze"),
    ])
    if not _cv_has_data:
        fetch_errors.append({
            "source": "Registro Ada (ClasseViva)",
            "message": "Nessun dato ricevuto — ClasseViva potrebbe essere irraggiungibile",
            "timestamp": datetime.now().isoformat(),
        })
    
    # Domoticz sensors
    print("🌡️  Fetching Domoticz sensors...")
    sensors = fetch_domoticz_sensors()
    print(f"   Found {len(sensors)} sensors")
    if not sensors:
        fetch_errors.append({
            "source": "Sensori Casa (Domoticz)",
            "message": "Nessun sensore disponibile — Domoticz potrebbe essere offline",
            "timestamp": datetime.now().isoformat(),
        })

    # Google Calendar (Family)
    print("📅 Fetching Google Calendar events...")
    cal_events = fetch_calendar_events([today, tomorrow])
    cal_today = cal_events.get(today_str, [])
    cal_tomorrow = cal_events.get(tomorrow_str, [])
    print(f"   Found {len(cal_today)} events today, {len(cal_tomorrow)} events tomorrow")
    
    if fetch_errors:
        print(f"⚠️  {len(fetch_errors)} fetch error(s) detected:")
        for fe in fetch_errors:
            print(f"   ❌ {fe['source']}: {fe['message']}")
    
    # Flavio
    flavio_today_sched, flavio_today_status, _ = get_flavio_schedule(today)
    flavio_today_sched += _calendar_events_for_member(cal_today, "flavio")
    flavio_tomorrow_sched, flavio_tomorrow_status, _ = get_flavio_schedule(tomorrow)
    flavio_tomorrow_sched += _calendar_events_for_member(cal_tomorrow, "flavio")
    
    # Alessandra
    ale_today_sched, ale_today_status = get_alessandra_schedule(today)
    ale_today_sched += _calendar_events_for_member(cal_today, "alessandra")
    ale_tomorrow_sched, ale_tomorrow_status = get_alessandra_schedule(tomorrow)
    ale_tomorrow_sched += _calendar_events_for_member(cal_tomorrow, "alessandra")
    
    # Ada
    ada_today_sched, ada_today_status = get_ada_schedule(today)
    ada_today_sched += _calendar_events_for_member(cal_today, "ada")
    ada_tomorrow_sched, ada_tomorrow_status = get_ada_schedule(tomorrow)
    ada_tomorrow_sched += _calendar_events_for_member(cal_tomorrow, "ada")
    
    # Maurizio (calendar events only)
    mau_today_sched = _calendar_events_for_member(cal_today, "maurizio")
    mau_tomorrow_sched = _calendar_events_for_member(cal_tomorrow, "maurizio")
    
    # Build reminders from Didup (Flavio) — skip past-due items
    reminders = []
    _date_prefix_re = re.compile(r"^(\d{4}-\d{2}-\d{2})")
    reminder_idx = 0
    for p in didup.get("promemoria", []):
        m = _date_prefix_re.match(p)
        if m:
            try:
                item_date = date.fromisoformat(m.group(1))
                if item_date < today:
                    print(f"   ⏭️  Skipping past-due promemoria: {p[:60]}")
                    continue
            except ValueError:
                pass  # malformed date → include it anyway
        reminders.append({
            "id": f"didup_{reminder_idx}",
            "text": f"📚 {p}",
            "priority": "high",
            "added_by": "picoclaw",
            "added_at": datetime.now().isoformat(),
        })
        reminder_idx += 1
    
    # Add ClasseViva reminders (Ada agenda items = compiti/impegni) — skip past-due items
    for i, a in enumerate(classeviva.get("agenda", [])):
        try:
            item_date = date.fromisoformat(a["data"])
            if item_date < today:
                print(f"   ⏭️  Skipping past-due ClasseViva agenda: {a['data']} {a['testo'][:40]}")
                continue
        except (ValueError, KeyError):
            pass  # malformed date → include it anyway
        reminders.append({
            "id": f"classeviva_{i}",
            "text": f"🎨 Ada: {a['data']} — {a['testo'][:150]}",
            "priority": "high",
            "added_by": "picoclaw",
            "added_at": datetime.now().isoformat(),
        })
    
    # Build Flavio personal notes from homework — skip past-due items
    compiti_lines = []
    for c in didup.get("compiti", []):
        try:
            item_date = date.fromisoformat(c["date"])
            if item_date < today:
                print(f"   ⏭️  Skipping past-due compito: {c['date']} {c['text'][:40]}")
                continue
        except (ValueError, KeyError):
            pass  # malformed date → include it anyway
        compiti_lines.append(f"📝 {c['date']}: {c['text'][:100]}")
        if len(compiti_lines) >= 8:
            break
    flavio_notes = "\n".join(compiti_lines) if compiti_lines else "Nessun compito registrato"
    
    # Build Ada personal notes from ClasseViva (structured)
    ada_school_data = {
        "lezioni_oggi": classeviva.get("lezioni_oggi", []),
        "lezioni_domani": classeviva.get("lezioni_domani", []),
        "agenda": classeviva.get("agenda", []),
        "voti": classeviva.get("voti", [])[:10],
        "assenze_count": len(classeviva.get("assenze", [])),
        "bacheca": classeviva.get("bacheca", []),
        "note": classeviva.get("note", []),
    }
    
    # Also build a text summary for personal_notes (fallback)
    ada_notes_parts = []
    if classeviva.get("lezioni_oggi"):
        ada_notes_parts.append("📚 Lezioni di oggi:")
        for lesson in classeviva["lezioni_oggi"]:
            line = f"  Ora {lesson['ora']}: {lesson['materia']} ({lesson['docente']})"
            if lesson.get("argomento"):
                line += f"\n    → {lesson['argomento'][:120]}"
            ada_notes_parts.append(line)
    if classeviva.get("agenda"):
        ada_notes_parts.append("\n📅 Compiti/Impegni:")
        for a in classeviva["agenda"][:5]:
            ada_notes_parts.append(f"  {a['data']} — {a['testo'][:100]}")
    if classeviva.get("voti"):
        ada_notes_parts.append("\n🎯 Voti recenti:")
        for v in classeviva["voti"][:5]:
            ada_notes_parts.append(f"  {v['data']} | {v['materia']} | {v['voto']}")
    if classeviva.get("bacheca"):
        ada_notes_parts.append("\n📋 Bacheca:")
        for b in classeviva["bacheca"][:3]:
            status = "🆕" if not b["letta"] else "✅"
            ada_notes_parts.append(f"  {status} {b['data']} — {b['titolo'][:80]}")
    if classeviva.get("note"):
        ada_notes_parts.append("\n⚠️ Note disciplinari:")
        for n in classeviva["note"]:
            ada_notes_parts.append(f"  {n['data']} | {n['tipo']}: {n['testo'][:100]}")
    ada_notes = "\n".join(ada_notes_parts) if ada_notes_parts else ""
    
    # Dashboard JSON
    dashboard = {
        "_meta": {
            "last_updated": datetime.now().isoformat(),
            "version": "2.1",
            "updated_by": "picoclaw",
            "fetch_errors": fetch_errors,
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
            "calendar_events": {
                "today": [
                    {
                        "time": e["time"],
                        "event": e["event"],
                        "all_day": e.get("all_day", False),
                        "summary": e.get("summary", ""),
                    }
                    for e in cal_today
                ],
                "tomorrow": [
                    {
                        "time": e["time"],
                        "event": e["event"],
                        "all_day": e.get("all_day", False),
                        "summary": e.get("summary", ""),
                    }
                    for e in cal_tomorrow
                ],
            },
            "notes": "",
            "weather": weather or {},
            "sensors": sensors or [],
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
                    "schedule": mau_today_sched,
                    "status": "💼 Lavoro",
                    "mood": "😊"
                },
                "tomorrow": {
                    "date": tomorrow_str,
                    "schedule": mau_tomorrow_sched,
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
                "transport": FLAVIO_TRASPORTI_TABLE,
                "personal_notes": flavio_notes
            },
            "ada": {
                "display_name": "Ada",
                "emoji": "🎨",
                "color_theme": "purple",
                "bio": "Scuola primaria IC Altopascio. Ama disegnare e giocare.",
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
                "school_data": ada_school_data,
                "personal_notes": ada_notes
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
    
    cal = dashboard["shared"].get("calendar_events", {})
    n_cal_today = len(cal.get("today", []))
    n_cal_tomorrow = len(cal.get("tomorrow", []))
    print(f"   📅 Calendario: {n_cal_today} eventi oggi, {n_cal_tomorrow} domani")


if __name__ == "__main__":
    main()
