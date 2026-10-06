> 🇬🇧 [English version](README.en.md)

# 🏡 Dashboard Familiare

Una dashboard familiare che si aggiorna automaticamente, pubblicata su GitHub Pages, con un bot Telegram per l'inserimento dei dati.

## Funzionalità

- **4 schede membro** (Maurizio, Alessandra, Flavio, Ada) ciascuna con avatar, bio, programma di oggi/domani, stato, umore, note personali
- **Sezioni condivise**: Meteo (Altopascio), Menu del Giorno (reset giornaliero), Promemoria, Note Familiari
- **4 temi visivi**: Caldo 🌅, Freddo 🌊, Natura 🌿, Scuro 🌙 (salvato per browser)
- **Aggiornamento automatico** tramite GitHub Actions: 2× al giorno (07:00 + 19:00 CET)
- **Bot Telegram** per tutti i membri della famiglia, per aggiornare i contenuti dal telefono
- **Meteo** tramite OpenWeatherMap (piano gratuito)
- **Zero backend** — sito statico puro + JSON + GitHub Actions

---

## Struttura delle Directory

```
family-dashboard/
├── index.html                    ← La dashboard (root di GitHub Pages)
├── data/
│   └── dashboard.json            ← Tutti i dati dei contenuti (aggiornati automaticamente)
├── assets/
│   └── images/                   ← Foto profilo (caricare qui)
│       ├── maurizio.jpg
│       ├── alessandra.jpg
│       ├── flavio.jpg
│       └── ada.jpg
├── bot/
│   ├── bot.py                    ← Bot Telegram (da eseguire su Raspberry Pi / VPS)
│   ├── fetch_weather.py          ← Raccolta dati meteo (usato da GitHub Actions)
│   └── requirements.txt
└── .github/
    └── workflows/
        └── update-dashboard.yml  ← Workflow di aggiornamento automatico
```

---

## Guida alla Configurazione

### 1. Creare il Repository GitHub

```bash
cd C:\Projects\Git-Personal\family-dashboard
git init
git add .
git commit -m "🏡 Initial family dashboard"
# Creare il repo su GitHub, poi:
git remote add origin https://github.com/YOURUSERNAME/family-dashboard.git
git push -u origin main
```

### 2. Abilitare GitHub Pages

- Andare nelle **Settings → Pages** del repo
- Source: **Deploy from a branch**
- Branch: `gh-pages` / `root`

> Il workflow usa `peaceiris/actions-gh-pages` che crea automaticamente il branch `gh-pages`.

### 3. Ottenere Chiavi API e Token

#### OpenWeatherMap (gratuito)
1. Registrarsi su https://openweathermap.org/api
2. Copiare la propria chiave API

#### Bot Telegram
1. Scrivere a `@BotFather` su Telegram
2. `/newbot` → scegliere nome e username
3. Copiare il token

#### GitHub Personal Access Token
1. GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens
2. Assegnare il permesso `Contents: Read and Write` sul repo della dashboard
3. Copiare il token

### 4. Aggiungere i Secrets su GitHub

Nel repo → **Settings → Secrets and variables → Actions**:

| Nome del secret | Valore                          |
|----------------|-------------------------------|
| `OWM_API_KEY`  | La propria chiave API OpenWeatherMap |
| `GITHUB_TOKEN` | (già fornito da Actions)       |

> Il bot necessita anche di `GITHUB_TOKEN` e `TELEGRAM_TOKEN` come variabili d'ambiente sulla macchina dove viene eseguito.

### 5. Aggiungere le Foto Profilo

Caricare le foto come:
- `assets/images/maurizio.jpg`
- `assets/images/alessandra.jpg`
- `assets/images/flavio.jpg`
- `assets/images/ada.jpg`

Consigliato: immagini quadrate, minimo 200×200px. La dashboard usa un'emoji come fallback se l'immagine è mancante.

### 6. Registrare i Membri della Famiglia nel Bot

1. Avviare il bot — ogni membro della famiglia gli scrive su Telegram
2. Ogni membro usa `/whoami` per ottenere il proprio ID Telegram
3. Modificare `bot/bot.py` → dizionario `FAMILY_MEMBERS`:

```python
FAMILY_MEMBERS = {
    123456789: "maurizio",    # ← sostituire con gli ID reali
    234567890: "alessandra",
    345678901: "flavio",
    456789012: "ada",
}
```

### 7. Eseguire il Bot Telegram

**Su Raspberry Pi o qualsiasi server Linux:**

```bash
cd bot/
pip install -r requirements.txt

# Impostare le variabili d'ambiente
export TELEGRAM_TOKEN="your_token"
export GITHUB_TOKEN="your_github_token"
export GITHUB_REPO="yourusername/family-dashboard"
export OWM_API_KEY="your_owm_key"

python bot.py
```

**Eseguire come servizio systemd (consigliato per Raspberry Pi):**

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

## Comandi del Bot Telegram

| Comando | Descrizione |
|---------|-------------|
| `/start` | Aprire il menu interattivo |
| `/whoami` | Mostrare il proprio ID Telegram |
| `/status 🏠 A casa` | Aggiornamento rapido del proprio stato |
| `/reminder <testo> [alta/media/bassa]` | Aggiungere un promemoria condiviso |
| `/menu pranzo: pasta \| cena: pollo` | Aggiornare il menu di oggi |
| `/clearreminders` | Cancellare tutti i promemoria (solo admin) |
| `/help` | Mostrare tutti i comandi |
| `/cancel` | Annullare l'operazione in corso |

**Menu interattivo** (tramite `/start`):
- Aggiornare il programma di oggi / domani
- Cambiare stato e umore
- Modificare note personali e bio
- Aggiungere promemoria
- Aggiornare menu e note familiari
- Aggiornare il meteo

---

## Personalizzare la Dashboard

### Cambiare nome della famiglia / località
Modificare `data/dashboard.json`:
```json
"config": {
  "family_name": "YourName",
  "location": { "city": "YourCity", "lat": 0.0, "lon": 0.0 }
}
```

### Aggiungere/rimuovere un membro
Aggiungere una nuova chiave sotto `members` in `dashboard.json` seguendo la struttura esistente.
Aggiungerlo anche in `MEMBER_ORDER` in `index.html` e in `FAMILY_MEMBERS` in `bot.py`.

### Cambiare la frequenza di aggiornamento
Modificare `.github/workflows/update-dashboard.yml` → le righe `cron`.

### Temi
Quattro temi integrati (Caldo, Freddo, Natura, Scuro) selezionabili dall'intestazione.
La scelta viene salvata nel `localStorage` per ogni browser.
Per aggiungere temi personalizzati, estendere le variabili CSS in `index.html`.

---

## Riepilogo del Formato Dati

`data/dashboard.json` è l'unica fonte di verità.

```
_meta          → timestamp last_updated, versione
config         → family_name, location (city, lat, lon)
shared
  ├── weather         → oggi + domani (temp, description, icon, humidity, wind)
  ├── menu_of_the_day → date, lunch, dinner, notes  [reset giornaliero automatico]
  ├── reminders[]     → id, text, priority, added_by, added_at
  └── notes           → testo libero
members
  └── <id>
       ├── display_name, emoji, color_theme (blue/rose/green/purple)
       ├── bio, avatar (path)
       ├── today   → date, schedule[], status, mood
       ├── tomorrow→ date, schedule[], status
       └── personal_notes
```

---

## Licenza

MIT — libero di usare e adattare per la propria famiglia!
