#!/usr/bin/env python3
"""
Family Dashboard Telegram Bot
==============================
Allows family members to update the shared dashboard via Telegram commands.
Each member can update their own schedule, personal notes, status, and mood.
Shared fields (menu, reminders, notes) can be updated by any member.

Run locally or on a Raspberry Pi / VPS:
    pip install python-telegram-bot requests pytz
    python bot.py

Environment variables (or edit CONFIG below):
    TELEGRAM_TOKEN   — your BotFather token
    GITHUB_TOKEN     — personal access token with repo write permission
    GITHUB_REPO      — e.g. "yourusername/family-dashboard"
    OWM_API_KEY      — OpenWeatherMap API key (for weather refresh)
"""

import os
import json
import logging
import re
from datetime import datetime, date, timedelta
from typing import Optional

import pytz
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, ContextTypes, filters
)

# ===== CONFIG =====
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN_HERE")
GITHUB_TOKEN   = os.getenv("GITHUB_TOKEN", "YOUR_GITHUB_TOKEN_HERE")
GITHUB_REPO    = os.getenv("GITHUB_REPO", "yourusername/family-dashboard")
OWM_API_KEY    = os.getenv("OWM_API_KEY", "YOUR_OWM_KEY_HERE")
DATA_FILE_PATH = "data/dashboard.json"
TZ             = pytz.timezone("Europe/Rome")

# Map Telegram user IDs to family member keys.
# Fill these in after each person starts the bot (use /whoami to get their ID).
FAMILY_MEMBERS = {
    123456789: "maurizio",    # replace with real Telegram user IDs
    234567890: "alessandra",
    345678901: "flavio",
    456789012: "ada",
}

# Conversation states
(
    MAIN_MENU,
    WAITING_SCHEDULE_DAY,
    WAITING_SCHEDULE_INPUT,
    WAITING_STATUS,
    WAITING_MOOD,
    WAITING_PERSONAL_NOTE,
    WAITING_REMINDER,
    WAITING_MENU_LUNCH,
    WAITING_MENU_DINNER,
    WAITING_FAMILY_NOTES,
    WAITING_BIO,
) = range(11)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ===== GITHUB DATA ACCESS =====

def github_api(method: str, endpoint: str, **kwargs):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/{endpoint}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    return requests.request(method, url, headers=headers, **kwargs)


def load_dashboard() -> dict:
    """Load dashboard.json from GitHub."""
    r = github_api("GET", f"contents/{DATA_FILE_PATH}")
    if r.status_code == 200:
        import base64
        content = base64.b64decode(r.json()["content"]).decode("utf-8")
        data = json.loads(content)
        data["_sha"] = r.json()["sha"]  # needed for update
        return data
    raise RuntimeError(f"Failed to load data: {r.status_code} {r.text}")


def save_dashboard(data: dict, commit_message: str) -> bool:
    """Save dashboard.json back to GitHub."""
    import base64
    sha = data.pop("_sha", None)
    # Update meta timestamp
    data["_meta"]["last_updated"] = datetime.now(TZ).isoformat()
    payload = {
        "message": commit_message,
        "content": base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode()).decode(),
    }
    if sha:
        payload["sha"] = sha
    r = github_api("PUT", f"contents/{DATA_FILE_PATH}", json=payload)
    return r.status_code in (200, 201)


# ===== HELPERS =====

def get_member_id(user_id: int) -> Optional[str]:
    return FAMILY_MEMBERS.get(user_id)


def get_member_name(member_id: str, data: dict) -> str:
    return data["members"].get(member_id, {}).get("display_name", member_id)


def today_str() -> str:
    return date.today().isoformat()


def tomorrow_str() -> str:
    return (date.today() + timedelta(days=1)).isoformat()


def parse_schedule_text(text: str) -> list:
    """
    Parse schedule from text.
    Accepts formats like:
        09:00 Stand-up meeting
        11:00 - Review PR
        14:00 Chiamata cliente
    Returns list of {time, event} dicts.
    """
    entries = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"(\d{1,2}:\d{2})\s*[-–]?\s*(.+)", line)
        if m:
            entries.append({"time": m.group(1), "event": m.group(2).strip()})
    return entries


def keyboard_main(member_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Aggiorna programma oggi",    callback_data="sched_today")],
        [InlineKeyboardButton("📆 Aggiorna programma domani",  callback_data="sched_tomorrow")],
        [InlineKeyboardButton("💬 Cambia stato",               callback_data="status")],
        [InlineKeyboardButton("😊 Cambia mood",                callback_data="mood")],
        [InlineKeyboardButton("📌 Note personali",             callback_data="personal_note")],
        [InlineKeyboardButton("✏️ Bio",                        callback_data="bio")],
        [InlineKeyboardButton("── Condivisi ──",               callback_data="noop")],
        [InlineKeyboardButton("🔔 Aggiungi promemoria",        callback_data="add_reminder")],
        [InlineKeyboardButton("🍽️ Menu del giorno",           callback_data="menu")],
        [InlineKeyboardButton("📝 Note famiglia",              callback_data="family_notes")],
        [InlineKeyboardButton("🌤️ Aggiorna meteo",            callback_data="refresh_weather")],
    ])


# ===== COMMAND HANDLERS =====

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    member_id = get_member_id(user_id)
    if not member_id:
        await update.message.reply_text(
            f"👋 Ciao! Il tuo Telegram ID è `{user_id}`.\n"
            "Non sei ancora registrato. Chiedi a Maurizio di aggiungere il tuo ID nel bot!",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    try:
        data = load_dashboard()
    except Exception as e:
        await update.message.reply_text(f"❌ Errore nel caricamento dati: {e}")
        return ConversationHandler.END

    name = get_member_name(member_id, data)
    ctx.user_data["member_id"] = member_id
    ctx.user_data["data"] = data

    await update.message.reply_text(
        f"🏡 *Family Dashboard Bot*\n\nCiao {name}! Cosa vuoi aggiornare?",
        parse_mode="Markdown",
        reply_markup=keyboard_main(member_id)
    )
    return MAIN_MENU


async def cmd_whoami(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👤 Il tuo nome: *{user.full_name}*\n"
        f"🆔 Il tuo Telegram ID: `{user.id}`",
        parse_mode="Markdown"
    )


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Quick status: /status Lavoro da casa"""
    user_id = update.effective_user.id
    member_id = get_member_id(user_id)
    if not member_id:
        await update.message.reply_text("❌ Non sei registrato.")
        return
    args = ctx.args
    if not args:
        await update.message.reply_text("Uso: /status <testo>  Es: /status 🏠 A casa")
        return
    status_text = " ".join(args)
    try:
        data = load_dashboard()
        data["members"][member_id].setdefault("today", {})["status"] = status_text
        data["members"][member_id]["today"]["date"] = today_str()
        save_dashboard(data, f"✏️ {member_id}: status updated")
        await update.message.reply_text(f"✅ Stato aggiornato: {status_text}")
    except Exception as e:
        await update.message.reply_text(f"❌ Errore: {e}")


async def cmd_reminder(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Quick add reminder: /reminder <text>"""
    user_id = update.effective_user.id
    member_id = get_member_id(user_id)
    if not member_id:
        await update.message.reply_text("❌ Non sei registrato.")
        return
    args = ctx.args
    if not args:
        await update.message.reply_text("Uso: /reminder <testo>  Es: /reminder Portare Ada dal dottore domani")
        return
    text = " ".join(args)
    try:
        data = load_dashboard()
        import uuid, random
        reminder = {
            "id": f"r{random.randint(1000,9999)}",
            "text": text,
            "priority": "medium",
            "added_by": member_id,
            "added_at": datetime.now(TZ).isoformat(),
        }
        data["shared"].setdefault("reminders", []).append(reminder)
        save_dashboard(data, f"🔔 {member_id}: reminder added")
        await update.message.reply_text(f"✅ Promemoria aggiunto:\n_{text}_", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Errore: {e}")


async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Quick menu: /menu pranzo: pasta | cena: pollo"""
    user_id = update.effective_user.id
    if not get_member_id(user_id):
        await update.message.reply_text("❌ Non sei registrato.")
        return
    if not ctx.args:
        await update.message.reply_text("Uso: /menu pranzo: <testo> | cena: <testo>")
        return
    text = " ".join(ctx.args)
    lunch = dinner = None
    lunch_m = re.search(r"pranzo[:\s]+([^|]+)", text, re.I)
    dinner_m = re.search(r"cena[:\s]+([^|]+)", text, re.I)
    if lunch_m: lunch = lunch_m.group(1).strip()
    if dinner_m: dinner = dinner_m.group(1).strip()
    try:
        data = load_dashboard()
        menu = data["shared"].setdefault("menu_of_the_day", {})
        menu["date"] = today_str()
        if lunch: menu["lunch"] = lunch
        if dinner: menu["dinner"] = dinner
        save_dashboard(data, "🍽️ Menu updated")
        await update.message.reply_text(
            f"✅ Menu aggiornato!\n🌞 Pranzo: {lunch or '—'}\n🌙 Cena: {dinner or '—'}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Errore: {e}")


async def cmd_clear_reminders(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Clear all reminders (admin only)."""
    user_id = update.effective_user.id
    member_id = get_member_id(user_id)
    if member_id != "maurizio":  # only admin
        await update.message.reply_text("❌ Solo l'admin può farlo.")
        return
    try:
        data = load_dashboard()
        data["shared"]["reminders"] = []
        save_dashboard(data, "🧹 Reminders cleared")
        await update.message.reply_text("✅ Promemoria svuotati.")
    except Exception as e:
        await update.message.reply_text(f"❌ Errore: {e}")


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    help_text = """
🏡 *Family Dashboard Bot — Comandi*

*Aggiornamento rapido:*
/status <testo> — Aggiorna il tuo stato di oggi
/reminder <testo> — Aggiungi un promemoria condiviso
/menu pranzo: X | cena: Y — Aggiorna il menu del giorno

*Interattivo:*
/start — Apri il menu principale

*Info:*
/whoami — Mostra il tuo Telegram ID
/help — Questo messaggio

*Solo admin:*
/clearreminders — Svuota i promemoria
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")


# ===== CALLBACK QUERY HANDLERS (Interactive Menu) =====

async def cb_main(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data

    if action == "noop":
        return MAIN_MENU

    member_id = ctx.user_data.get("member_id")
    if not member_id:
        await query.edit_message_text("❌ Sessione scaduta. Usa /start")
        return ConversationHandler.END

    # Re-load fresh data on each action
    try:
        ctx.user_data["data"] = load_dashboard()
    except Exception as e:
        await query.edit_message_text(f"❌ Errore: {e}")
        return ConversationHandler.END

    if action == "sched_today":
        ctx.user_data["sched_day"] = "today"
        await query.edit_message_text(
            "📅 *Programma di oggi*\n\nInvia gli impegni, uno per riga:\n`HH:MM Descrizione evento`\n\nEs:\n`09:00 Stand-up meeting\n14:00 Chiamata cliente`",
            parse_mode="Markdown"
        )
        return WAITING_SCHEDULE_INPUT

    elif action == "sched_tomorrow":
        ctx.user_data["sched_day"] = "tomorrow"
        await query.edit_message_text(
            "📆 *Programma di domani*\n\nInvia gli impegni, uno per riga:\n`HH:MM Descrizione evento`",
            parse_mode="Markdown"
        )
        return WAITING_SCHEDULE_INPUT

    elif action == "status":
        await query.edit_message_text(
            "💬 *Cambia stato*\n\nInvia il tuo stato attuale (es: `🏠 A casa`, `💼 In ufficio`)",
            parse_mode="Markdown"
        )
        return WAITING_STATUS

    elif action == "mood":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("😊 Felice", callback_data="mood_😊"),
             InlineKeyboardButton("😌 Rilassato", callback_data="mood_😌")],
            [InlineKeyboardButton("😄 Entusiasta", callback_data="mood_😄"),
             InlineKeyboardButton("🎯 Concentrato", callback_data="mood_🎯")],
            [InlineKeyboardButton("😴 Stanco", callback_data="mood_😴"),
             InlineKeyboardButton("😤 Stressato", callback_data="mood_😤")],
        ])
        await query.edit_message_text("😊 *Come ti senti oggi?*", parse_mode="Markdown", reply_markup=keyboard)
        return WAITING_MOOD

    elif action == "personal_note":
        await query.edit_message_text(
            "📌 *Note personali*\n\nInvia la tua nota (sostituirà quella precedente):",
            parse_mode="Markdown"
        )
        return WAITING_PERSONAL_NOTE

    elif action == "bio":
        await query.edit_message_text(
            "✏️ *Bio*\n\nInvia la tua breve bio (max 120 caratteri):",
            parse_mode="Markdown"
        )
        return WAITING_BIO

    elif action == "add_reminder":
        await query.edit_message_text(
            "🔔 *Aggiungi Promemoria*\n\nInvia il testo del promemoria.\nPuoi aggiungere la priorità: `[alta]`, `[media]`, `[bassa]`\n\nEs: `Visita medica Ada giovedì [alta]`",
            parse_mode="Markdown"
        )
        return WAITING_REMINDER

    elif action == "menu":
        await query.edit_message_text(
            "🍽️ *Menu del giorno — Pranzo*\n\nCosa c'è a pranzo oggi? (Scrivi 'salta' per non cambiarlo)",
            parse_mode="Markdown"
        )
        return WAITING_MENU_LUNCH

    elif action == "family_notes":
        await query.edit_message_text(
            "📝 *Note della Famiglia*\n\nInvia le note condivise (sovrascriverà le precedenti):",
            parse_mode="Markdown"
        )
        return WAITING_FAMILY_NOTES

    elif action == "refresh_weather":
        await query.edit_message_text("🌤️ Aggiornamento meteo in corso...")
        try:
            update_weather_in_data(ctx.user_data["data"])
            save_dashboard(ctx.user_data["data"], "🌤️ Weather refreshed")
            await query.edit_message_text("✅ Meteo aggiornato!")
        except Exception as e:
            await query.edit_message_text(f"❌ Errore meteo: {e}")
        return ConversationHandler.END

    return MAIN_MENU


async def cb_mood(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mood_emoji = query.data.replace("mood_", "")
    member_id = ctx.user_data.get("member_id")
    data = ctx.user_data.get("data")
    if not member_id or not data:
        await query.edit_message_text("❌ Sessione scaduta.")
        return ConversationHandler.END
    data["members"][member_id].setdefault("today", {})["mood"] = mood_emoji
    data["members"][member_id]["today"]["date"] = today_str()
    save_dashboard(data, f"😊 {member_id}: mood updated")
    await query.edit_message_text(f"✅ Mood aggiornato: {mood_emoji}")
    return ConversationHandler.END


async def recv_schedule(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    member_id = ctx.user_data.get("member_id")
    data = ctx.user_data.get("data")
    sched_day = ctx.user_data.get("sched_day", "today")
    entries = parse_schedule_text(update.message.text)
    if not entries:
        await update.message.reply_text("❌ Formato non riconosciuto. Usa:\n`09:00 Descrizione`", parse_mode="Markdown")
        return WAITING_SCHEDULE_INPUT
    target_date = today_str() if sched_day == "today" else tomorrow_str()
    data["members"][member_id].setdefault(sched_day, {})
    data["members"][member_id][sched_day]["schedule"] = entries
    data["members"][member_id][sched_day]["date"] = target_date
    save_dashboard(data, f"📅 {member_id}: schedule {sched_day} updated")
    day_label = "oggi" if sched_day == "today" else "domani"
    lines = "\n".join(f"• {e['time']} — {e['event']}" for e in entries)
    await update.message.reply_text(f"✅ Programma di *{day_label}* aggiornato:\n\n{lines}", parse_mode="Markdown")
    return ConversationHandler.END


async def recv_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    member_id = ctx.user_data.get("member_id")
    data = ctx.user_data.get("data")
    text = update.message.text.strip()
    data["members"][member_id].setdefault("today", {})["status"] = text
    data["members"][member_id]["today"]["date"] = today_str()
    save_dashboard(data, f"💬 {member_id}: status updated")
    await update.message.reply_text(f"✅ Stato aggiornato: {text}")
    return ConversationHandler.END


async def recv_personal_note(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    member_id = ctx.user_data.get("member_id")
    data = ctx.user_data.get("data")
    data["members"][member_id]["personal_notes"] = update.message.text.strip()
    save_dashboard(data, f"📌 {member_id}: personal note updated")
    await update.message.reply_text("✅ Nota personale aggiornata!")
    return ConversationHandler.END


async def recv_bio(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    member_id = ctx.user_data.get("member_id")
    data = ctx.user_data.get("data")
    bio = update.message.text.strip()[:150]
    data["members"][member_id]["bio"] = bio
    save_dashboard(data, f"✏️ {member_id}: bio updated")
    await update.message.reply_text(f"✅ Bio aggiornata:\n_{bio}_", parse_mode="Markdown")
    return ConversationHandler.END


async def recv_reminder(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    member_id = ctx.user_data.get("member_id")
    data = ctx.user_data.get("data")
    text = update.message.text.strip()
    priority = "medium"
    if "[alta]" in text.lower():  priority = "high";   text = re.sub(r"\[alta\]", "", text, flags=re.I).strip()
    if "[media]" in text.lower(): priority = "medium"; text = re.sub(r"\[media\]", "", text, flags=re.I).strip()
    if "[bassa]" in text.lower(): priority = "low";    text = re.sub(r"\[bassa\]", "", text, flags=re.I).strip()
    import random
    reminder = {
        "id": f"r{random.randint(1000,9999)}",
        "text": text,
        "priority": priority,
        "added_by": member_id,
        "added_at": datetime.now(TZ).isoformat(),
    }
    data["shared"].setdefault("reminders", []).append(reminder)
    save_dashboard(data, f"🔔 {member_id}: reminder added")
    await update.message.reply_text(f"✅ Promemoria aggiunto [{priority}]:\n_{text}_", parse_mode="Markdown")
    return ConversationHandler.END


async def recv_menu_lunch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["menu_lunch"] = update.message.text.strip()
    await update.message.reply_text("🌙 E a cena? (Scrivi 'salta' per non cambiarlo)")
    return WAITING_MENU_DINNER


async def recv_menu_dinner(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = ctx.user_data.get("data")
    lunch = ctx.user_data.get("menu_lunch", "")
    dinner = update.message.text.strip()
    menu = data["shared"].setdefault("menu_of_the_day", {})
    menu["date"] = today_str()
    if lunch.lower() != "salta": menu["lunch"] = lunch
    if dinner.lower() != "salta": menu["dinner"] = dinner
    save_dashboard(data, "🍽️ Menu updated")
    await update.message.reply_text(
        f"✅ Menu aggiornato!\n🌞 Pranzo: {menu.get('lunch','—')}\n🌙 Cena: {menu.get('dinner','—')}"
    )
    return ConversationHandler.END


async def recv_family_notes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = ctx.user_data.get("data")
    data["shared"]["notes"] = update.message.text.strip()
    save_dashboard(data, "📝 Family notes updated")
    await update.message.reply_text("✅ Note della famiglia aggiornate!")
    return ConversationHandler.END


async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operazione annullata.")
    return ConversationHandler.END


# ===== WEATHER FETCH =====

def update_weather_in_data(data: dict):
    """Fetch weather from OpenWeatherMap and update data in place."""
    loc = data.get("config", {}).get("location", {})
    lat = loc.get("lat", 43.8135)
    lon = loc.get("lon", 10.6773)
    r = requests.get(
        "https://api.openweathermap.org/data/2.5/forecast",
        params={"lat": lat, "lon": lon, "appid": OWM_API_KEY, "units": "metric", "lang": "it", "cnt": 16}
    )
    r.raise_for_status()
    forecasts = r.json()["list"]

    def get_day_summary(target_date_str):
        day_items = [f for f in forecasts if f["dt_txt"].startswith(target_date_str)]
        if not day_items:
            return None
        temps = [f["main"]["temp"] for f in day_items]
        mid = day_items[len(day_items)//2]
        return {
            "date": target_date_str,
            "description": mid["weather"][0]["description"].capitalize(),
            "temp_min": round(min(temps)),
            "temp_max": round(max(temps)),
            "icon": mid["weather"][0]["icon"],
            "humidity": mid["main"]["humidity"],
            "wind_speed": round(mid["wind"]["speed"] * 3.6),
            "precipitation_mm": round(sum(f.get("rain", {}).get("3h", 0) for f in day_items), 1)
        }

    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    data.setdefault("shared", {})["weather"] = {
        "today": get_day_summary(today) or {},
        "tomorrow": get_day_summary(tomorrow) or {},
    }


# ===== MAIN =====

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Conversation handler for interactive menu
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            MAIN_MENU: [CallbackQueryHandler(cb_main), CallbackQueryHandler(cb_mood, pattern=r"^mood_")],
            WAITING_SCHEDULE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_schedule)],
            WAITING_STATUS:         [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_status)],
            WAITING_MOOD:           [CallbackQueryHandler(cb_mood, pattern=r"^mood_")],
            WAITING_PERSONAL_NOTE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_personal_note)],
            WAITING_BIO:            [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_bio)],
            WAITING_REMINDER:       [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_reminder)],
            WAITING_MENU_LUNCH:     [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_menu_lunch)],
            WAITING_MENU_DINNER:    [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_menu_dinner)],
            WAITING_FAMILY_NOTES:   [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_family_notes)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("whoami",          cmd_whoami))
    app.add_handler(CommandHandler("status",          cmd_status))
    app.add_handler(CommandHandler("reminder",        cmd_reminder))
    app.add_handler(CommandHandler("menu",            cmd_menu))
    app.add_handler(CommandHandler("clearreminders",  cmd_clear_reminders))
    app.add_handler(CommandHandler("help",            cmd_help))

    logger.info("Bot avviato. In ascolto...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
