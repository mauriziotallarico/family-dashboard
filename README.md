> 🇬🇧 [English version](README.en.md)

# 🏡 Dashboard Familiare

Una dashboard familiare che si aggiorna automaticamente, pubblicata su GitHub Pages, con un bot Telegram per l'inserimento dei dati.

## Funzionalità

- **4 schede membro** (Maurizio, Alessandra, Flavio, Ada) ciascuna con avatar, bio, programma di oggi/domani, stato, umore, note personali
- **Sezioni condivise**: Meteo (Altopascio), Menu del Giorno (reset giornaliero), Promemoria, Note Familiari
- **🌡️ Sensori Casa (Domoticz)**: temperatura, umidità e livello batteria per ogni stanza, con card colorate e icone dedicate, alert visivo batteria scarica
- **📚 Registro Elettronico Flavio (Argo Didup)**: compiti della settimana, promemoria, integrati automaticamente nelle note personali e nei promemoria condivisi
- **🎨 Registro Elettronico Ada (ClasseViva)**: lezioni di oggi/domani con argomenti, compiti, voti, bacheca, note disciplinari, assenze — tutto visualizzato nella scheda di Ada
- **📅 Google Calendar (Famiglia)**: eventi dal calendario condiviso distribuiti automaticamente nelle schede dei membri
- **🚏 Trasporti Flavio**: tabella raccomandazioni treni Lucca → Altopascio con evidenziazione del giorno corrente
- **4 temi visivi**: Caldo 🌅, Freddo 🌊, Natura 🌿, Scuro 🌙 (salvato per browser)
- **Layout full-width**: tutte le card dei membri alla stessa larghezza, link utili in barra orizzontale in basso
- **🔗 Link Utili**: accesso rapido a ClasseViva, Argo, Google Calendar, Gmail, GitHub, Autolinee Toscane, Trenitalia — disposti in griglia orizzontale sotto le card
- **Aggiornamento automatico**: 2× al giorno (07:30 + 15:00) tramite PicoClaw 🦞 su Raspberry Pi
- **Bot Telegram** per tutti i membri della famiglia, per aggiornare i contenuti dal telefono
- **Meteo** tramite Open-Meteo (gratuito, senza API key)
- **Zero backend** — sito statico puro + JSON + script di aggiornamento locale

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
├── scripts/
│   ├── update-dashboard.py       ← Script principale di aggiornamento dati
│   └── github-push.py            ← Push automatico su GitHub
├── bot/
│   ├── bot.py                    ← Bot Telegram (da eseguire su Raspberry Pi / VPS)
│   ├── fetch_weather.py          ← Raccolta dati meteo
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

## Layout della Dashboard

La pagina è organizzata in sezioni verticali a larghezza piena:

1. **Header** — Nome famiglia, data/ora, selettore tema
2. **Sezione condivisa** — Griglia 4 colonne: Meteo, Menu, Promemoria, Note
3. **Sensori Casa** — Card Domoticz a larghezza piena (temperatura, umidità, batteria)
4. **Card Membri** — Griglia responsive: Maurizio, Alessandra, Flavio, Ada — tutte allo stesso livello
5. **Trasporti Flavio** — Tabella raccomandazioni treni (visibile solo se ci sono dati)
6. **Link Utili** — Barra orizzontale con link rapidi (registri, calendario, mail, trasporti)
7. **Footer**

> Le card dei membri occupano tutta la larghezza disponibile (no sidebar laterale), così anche la card di Ada con i dati ClasseViva ha lo stesso spazio delle altre.

---

## Integrazioni Dati

### 🌡️ Domoticz (Sensori Casa)

La dashboard legge i sensori di temperatura e umidità da un'istanza [Domoticz](https://www.domoticz.com/) locale.

**Configurazione:**
1. Creare il file `.domoticz-credentials` nella root del workspace PicoClaw:
```
DOMOTICZ_URL=http://localhost:9090
DOMOTICZ_USER=admin
DOMOTICZ_PASS=your_password
```
2. I sensori Temp+Humidity vengono rilevati automaticamente
3. Le card mostrano: temperatura (con barra colorata in base al range), umidità, livello batteria con alert visivo

**Soglie batteria:**
- 🔋 > 30% → normale (grigio)
- 🔋 15–30% → bassa (arancione)
- 🪫 < 15% → critica (rosso lampeggiante)

### 📚 Argo Didup (Registro Flavio)

Integrazione con il registro elettronico Argo Didup Famiglia per il Liceo Passaglia.
- **Compiti della settimana** → note personali di Flavio
- **Promemoria** → sezione promemoria condivisa (con filtro date passate)

Credenziali salvate in `.argo-credentials`.

### 🎨 ClasseViva (Registro Ada)

Integrazione con il registro elettronico ClasseViva (Spaggiari) per la scuola primaria.
- **Lezioni di oggi/domani** con argomenti e docenti
- **Compiti e impegni** (agenda 14 giorni)
- **Voti** con colore indicativo
- **Bacheca** comunicazioni scuola
- **Note disciplinari** e **assenze**

Credenziali salvate in `.classeviva-credentials`.

### 📅 Google Calendar

Eventi dal calendario famiglia Google, distribuiti automaticamente nelle schede dei membri.
- I genitori (Maurizio, Alessandra) vedono **tutti** gli eventi
- I figli vedono solo gli eventi che li riguardano (match per nome)
- Service Account configurato con accesso al calendario condiviso

### 🌤️ Meteo (Open-Meteo)

Previsioni meteo gratuite tramite [Open-Meteo](https://open-meteo.com/), senza API key.
- Oggi e domani: temperatura min/max, umidità, vento, precipitazioni
- Icone OpenWeatherMap per compatibilità visiva

### 🚏 Trasporti Flavio

Tabella raccomandazioni treni Lucca → Altopascio per ogni giorno della settimana.
- Evidenziazione automatica del giorno corrente
- Orari uscita, mezzo consigliato, note e alternative

---

## Riepilogo del Formato Dati

`data/dashboard.json` è l'unica fonte di verità.

```
_meta          → timestamp last_updated, versione
config         → family_name, location (city, lat, lon)
shared
  ├── weather           → oggi + domani (temp, description, icon, humidity, wind, precipitation)
  ├── sensors[]         → Domoticz: id, name, icon, temp, humidity, battery, last_update, battery_warning
  ├── menu_of_the_day   → date, lunch, dinner, notes  [reset giornaliero automatico]
  ├── reminders[]       → id, text, priority, added_by, added_at
  ├── calendar_events   → today[], tomorrow[] (time, event, all_day, summary)
  └── notes             → testo libero
members
  └── <id>
       ├── display_name, emoji, color_theme (blue/rose/green/purple)
       ├── bio, avatar (path)
       ├── today       → date, schedule[], status, mood
       ├── tomorrow    → date, schedule[], status
       ├── transport[] → [solo Flavio] day, exit_time, mode, departure, arrival, notes
       ├── school_data → [solo Ada] lezioni_oggi[], lezioni_domani[], agenda[], voti[], bacheca[], note[], assenze_count
       └── personal_notes
```

---

## Licenza

MIT — libero di usare e adattare per la propria famiglia!
