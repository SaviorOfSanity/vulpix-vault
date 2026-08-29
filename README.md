# 🦊 The Vulpix Vault

> **Self-hosted Pokémon card market tracking application containerized with Docker Compose for Proxmox and Linux servers.**
> Tracks your personal graded Vulpix slab collection, scrapes eBay for new listings, appraises deals with Google Gemini AI, and sends push notifications to your devices via Gotify.

---

## 🌟 Key Features

* **🏆 Graded Slabs Collection Tracker:** Manage your personal slab vault (PSA, CGC, BGS, ARS, ACE). Tracks cost basis, acquisition dates, cert numbers, and computes real-time unrealized gains and ROI %.
* **🤖 AI Market Appraisal (Google Gemini):** Automatically analyzes newly scraped eBay listings against recent comparable sales using `gemini-2.5-flash` to identify true market deals (`amazing_deal`, `good_deal`, `avoid_price`).
* **🔔 Gotify Push Notifications:** Instant Priority 8 alerts pushed to your phone or desktop with direct eBay listing links whenever an amazing deal is discovered.
* **📈 Interactive Market Analytics:** Multi-series Plotly price trend charts filtering historical sales by variant, grading company, and grade.
* **🐳 Docker Compose Architecture:** Multi-container setup with independent Streamlit UI, background Python APScheduler daemon, and local Gotify server with persistent SQLite storage in WAL mode.

---

## 🏗️ Architecture & Services

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Compose Network                  │
│                                                             │
│  ┌──────────────────────┐        ┌───────────────────────┐  │
│  │   vulpix-dashboard   │        │     vulpix-scraper    │  │
│  │  (Streamlit UI :8501)│        │ (APScheduler + Gemini)│  │
│  └──────────┬───────────┘        └───────────┬───────────┘  │
│             │                                │              │
│             │    ┌──────────────────────┐    │              │
│             └───►│   SQLite WAL Mode    │◄───┘              │
│                  │ (/data/vulpix_vault) │                   │
│                  └──────────────────────┘                   │
│                                      │ (Alerts on Deals)    │
│                                      ▼                      │
│                          ┌───────────────────────┐          │
│                          │     gotify/server     │          │
│                          │   (Push Service :8070)│          │
│                          └───────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start & Deployment

### 1. Clone or Copy the Repository
```bash
git clone <your-repo-url> "Vulpix Card Value"
cd "Vulpix Card Value"
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` with your API keys:
```env
# Google Gemini API key
GEMINI_API_KEY=AIzaSy...

# Gotify Application Token (generated in Gotify UI)
GOTIFY_APP_TOKEN=your_gotify_token_here

# Gotify URL inside Docker network
GOTIFY_URL=http://gotify:80

# SQLite Database Location
DB_PATH=/data/vulpix_vault.db

# Scrape Interval (Hours)
SCRAPE_INTERVAL_HOURS=24
```

### 3. Launch Services
```bash
docker compose up -d --build
```

---

## 📱 Setting Up Push Notifications (Gotify)

1. Open Gotify in your browser: `http://<your-proxmox-or-server-ip>:8070`
2. Log in with the default credentials:
   - **Username:** `admin`
   - **Password:** `admin` *(change this under User settings immediately)*
3. Click on **Apps** in the top navigation $\rightarrow$ Click **Create Application**.
4. Name it `Vulpix Vault Radar` and click **Create**.
5. Copy the generated **Token** and paste it into your `.env` file as `GOTIFY_APP_TOKEN`.
6. Restart the scraper: `docker compose restart vulpix-scraper`.
7. Install the Gotify app on your Android/iOS phone or desktop to receive push alerts with click-through links!

---

## 🖥️ Accessing the Dashboard

Open your web browser and navigate to:
```
http://<your-proxmox-or-server-ip>:8501
```

* **🦊 My Graded Vault:** View your slab collection, monitor portfolio gains, and add new slabs.
* **📈 Market Price Trends:** Explore historical sales charts and filter by card variant and grade.
* **🎯 AI Deal Radar:** See live undervalued listings flagged by Google Gemini.
* **⚙️ System & Controls:** Trigger immediate on-demand scrapes and test Gotify push notifications.

---

## 📁 Project Structure

```
├── docker-compose.yml       # Orchestrates Streamlit, Scraper, and Gotify
├── .env.example             # Environment variables template
├── .env                     # Local environment configuration
├── .gitignore               # Excludes secrets, databases, and caches
├── README.md                # Documentation & deployment guide
├── data/                    # Persistent storage volume for SQLite DB
│   └── .gitkeep
├── dashboard/               # Streamlit Frontend Service
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app.py               # 4-tab responsive web interface
│   ├── db_utils.py          # Cached data access & portfolio analytics
│   └── styles.py            # Dark theme CSS & grading badge styling
└── scraper/                 # Background Automation Service
    ├── Dockerfile
    ├── requirements.txt
    ├── cron_scraper.py      # APScheduler entrypoint & workflow coordinator
    ├── db.py                # SQLite WAL schema & query utilities
    ├── ebay.py              # eBay listing parser & regex slab extractor
    ├── appraiser.py         # Google Gemini AI pricing appraisal
    ├── notifier.py          # Gotify push alert dispatcher
    └── seed_data.py         # Starter collection & market sales generator
```

---

## 🛠️ Management & Useful Commands

* **View live scraper logs:**
  ```bash
  docker compose logs -f vulpix-scraper
  ```
* **View dashboard logs:**
  ```bash
  docker compose logs -f vulpix-dashboard
  ```
* **Restart the stack:**
  ```bash
  docker compose restart
  ```
* **Stop all containers:**
  ```bash
  docker compose down
  ```
