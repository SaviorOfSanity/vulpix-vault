# 🦊 The Vulpix Vault

> **Self-hosted Pokémon card market tracking application containerized with Docker Compose for Proxmox and Linux servers.**
> Tracks your personal Vulpix collection, monitors Master Set completion, analyzes market sales trends, and sends real-time deal alerts via Gotify.

---

## 🌟 Key Features

* **🏆 Personal Vault Tracker:** Manage your personal slab and raw collection (PSA, CGC, BGS, ARS, ACE, Raw singles). Tracks acquisition dates, cert numbers, and computes real-time unrealized gains and ROI %.
* **📜 Master Set Completion Catalog:** Complete checklist for 240+ Vulpix cards with official card artwork scans, 1st Edition badges, variant indicators, and error tracking.
* **🤖 Market Deal Radar:** Evaluates live eBay listings against comparable sales to identify high-conviction deals.
* **🔔 Push Notifications:** Push alerts delivered directly to your phone or desktop with direct eBay links when deals are discovered.
* **📈 Market Sales Explorer:** Interactive price history charts filtering historical sales by variant, grading company, and grade.
* **🐳 Docker Compose Architecture:** Multi-container setup with independent Streamlit UI, background automated daemon, and persistent SQLite storage in WAL mode.

---

## 🏗️ Architecture & Services

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Compose Network                  │
│                                                             │
│  ┌──────────────────────┐        ┌───────────────────────┐  │
│  │   vulpix-dashboard   │        │     vulpix-scraper    │  │
│  │  (Streamlit UI :8501)│        │   (Automation Daemon) │  │
│  └──────────┬───────────┘        └───────────┬───────────┘  │
│             │                                │              │
│             │    ┌──────────────────────┐    │              │
│             └───►│   SQLite WAL Mode    │◄───┘              │
│                  │ (/data/vulpix_vault) │                   │
│                  └──────────────────────┘                   │
│                                      │                      │
│                                      ▼                      │
│                          ┌───────────────────────┐          │
│                          │     gotify/server     │          │
│                          │   (Push Service :8070)│          │
│                          └───────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start & Deployment

### 1. Clone the Repository
```bash
git clone https://github.com/SaviorOfSanity/vulpix-vault.git
cd vulpix-vault
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Review `.env` to configure your environment settings:
```env
# Gotify Server URL (Inside Docker: http://gotify:80 | Host: http://10.0.0.48:8070)
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

## 📱 Push Notifications Setup (Gotify)

1. Open Gotify in your browser: `http://<your-server-ip>:8070`
2. Log in with your admin credentials.
3. Navigate to **Apps** $\rightarrow$ Click **Create Application**.
4. Name your application (e.g. `Vulpix Vault Radar`) and click **Create**.
5. Copy the generated application token and save it directly in the dashboard under **Tab 6 (System Controls & Gotify Sync)** or in your `.env` file.
6. Click **Save & Test Connection** in Tab 6 to verify live push delivery.

---

## 🖥️ Accessing the Dashboard

Open your web browser and navigate to:
```
http://<your-server-ip>:8501
```

* **💼 My Vault & Portfolio:** View your owned cards, track portfolio ROI, and manage your slabs.
* **📜 Master Set Checklist:** Browse the 240+ card catalog with high-res scans, 1st Edition badges, and price benchmarks.
* **🎯 eBay Sniper Watchlist:** Monitor active auctions and set target auto-bid caps.
* **🔥 AI Deal Radar:** Discover live discounted listings.
* **⚙️ System Controls & Gotify Sync:** Manage database records, test push notifications, and configure settings.

---

## 🛠️ Management Commands

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
