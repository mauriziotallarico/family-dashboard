#!/usr/bin/env python3
"""
Standalone weather fetcher — called by GitHub Actions workflow.
Updates data/dashboard.json with current weather from OpenWeatherMap.
Reads the file from disk (not GitHub API) since Actions has it checked out.
"""

import json
import os
import sys
from datetime import date, datetime, timedelta

import pytz
import requests

OWM_API_KEY = os.getenv("OWM_API_KEY", "")
LAT = float(os.getenv("LAT", "43.8135"))
LON = float(os.getenv("LON", "10.6773"))
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "dashboard.json")
TZ = pytz.timezone("Europe/Rome")


def fetch_weather():
    if not OWM_API_KEY:
        print("⚠️  OWM_API_KEY not set, skipping weather update.")
        return None

    r = requests.get(
        "https://api.openweathermap.org/data/2.5/forecast",
        params={
            "lat": LAT, "lon": LON,
            "appid": OWM_API_KEY,
            "units": "metric",
            "lang": "it",
            "cnt": 16,
        },
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["list"]


def day_summary(forecasts, target_date_str):
    items = [f for f in forecasts if f["dt_txt"].startswith(target_date_str)]
    if not items:
        return None
    temps = [f["main"]["temp"] for f in items]
    mid = items[len(items) // 2]
    return {
        "date": target_date_str,
        "description": mid["weather"][0]["description"].capitalize(),
        "temp_min": round(min(temps)),
        "temp_max": round(max(temps)),
        "icon": mid["weather"][0]["icon"],
        "humidity": mid["main"]["humidity"],
        "wind_speed": round(mid["wind"]["speed"] * 3.6),
        "precipitation_mm": round(
            sum(f.get("rain", {}).get("3h", 0) for f in items), 1
        ),
    }


def main():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    forecasts = fetch_weather()
    if not forecasts:
        print("No forecast data returned.")
        sys.exit(0)

    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    weather = {
        "today": day_summary(forecasts, today),
        "tomorrow": day_summary(forecasts, tomorrow),
    }

    # Remove None entries
    weather = {k: v for k, v in weather.items() if v is not None}

    data.setdefault("shared", {})["weather"] = weather
    data.setdefault("_meta", {})["last_updated"] = datetime.now(TZ).isoformat()

    # Reset menu if date changed
    menu = data.get("shared", {}).get("menu_of_the_day", {})
    if menu.get("date") and menu["date"] != today:
        data["shared"]["menu_of_the_day"] = {
            "date": today,
            "lunch": "",
            "dinner": "",
            "notes": "",
        }
        print(f"📋 Menu reset for new day: {today}")

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ Weather updated for {today} / {tomorrow}")
    if "today" in weather:
        w = weather["today"]
        print(f"   Today: {w['description']}, {w['temp_min']}°–{w['temp_max']}°C")


if __name__ == "__main__":
    main()
