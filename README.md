# The Vulpix Vault v2

A clean, fast, self-hosted **Vulpix Master Set Binder, Personal Vault & Auction Command Center** built with **FastAPI + Vanilla ES2022 + SQLite**.

Designed around the **last 10 minutes of an eBay auction**: open the app, type a set/number/language/error (`/`), and know in under 5 seconds:
1. **Do I already own this exact card/variant** (and is my copy Grade 10 or upgradeable)?
2. **What should I bid** (live market prices + shipping-adjusted max bid targets)?
3. **Is the seller's listing accurate** (interactive visual error/stamp callout overlays directly on the card photo + graphical SVG variant badges + verification specs)?

---

## Core Features (Phase 1 + Phase 2)

- **Canonical Multi-Language Master Set (with English Translations):** Deterministically compiled from PokeCottage's official 251-variant Vulpix dataset, curated Vulpix-themed promos (Poncho-wearing Pikachu `#037/SM-P` & `#038/SM-P`), documented error variants, authentic Playing Cards, and **all 14 official Pokémon TCG languages** via **TCGdex API v2**. Foreign card titles and set names are automatically translated to English with original native text preserved alongside. Background cameos are excluded.
- **Pixel-Calibrated Visual Error & Stamp Overlays:** Click any card tile directly to open the Auction Command modal. Error cards and key print marks (Base Set `"HP 50"` typo vs 4th Print `"50 HP"`, Blue Dot Error, Water Symbol Error, Ink Error, 1996 Japanese No Rarity Symbol, Gym Heroes Grey Stamp Error, Gym Challenge Gold `"W"` Stamp, Master Ball vs Poké Ball holo) render numbered highlight overlays directly on top of the exact location on the card photo.
- **Phase 2 — eBay Auction Radar & Sniper Alerts:**
  - Powered by the official free **eBay Browse API** (OAuth2 Client Credentials — zero fragile HTML scraping) plus instant **+ Track Auction URL** manual tracking even before connecting API keys.
  - Auto-matches active auctions & Buy It Now listings against your **Missing** and **Upgradeable (<Grade 10)** cards with live ticking countdown timers, real Deal Badges (`SNIPE`, `GOOD DEAL`, `FAIR`, `OVERPRICED`), 1-click **Verify Card & Bid** modal launch, and 1-click **Won → Vault**.
  - Optional push alerts via **Gotify**, **Discord Webhook**, or **ntfy** (configured in the UI or via `.env`).
- **Honest Live Market Pricing:** Fetches real Raw, Grade 9, and PSA 10 comps from **PriceCharting** and **TCGdex (TCGPlayer USD & Cardmarket EUR)** with transparent source & timestamp badges, manual comp locking, and zero fake placeholders.
- **Personal Vault & Portfolio:** Track graded slabs and raw singles with exact grader, grade label, cert lookup links, purchase basis, live market value, ROI, and upgrade-candidate tracking.
- **Zero-Build Single Container:** Lean `python:3.11-slim` Docker image running FastAPI + static ES module SPA on port `8501`.

---

## Quick Start (Docker)

```bash
git pull origin main
docker compose up -d --build --remove-orphans
```

Open `http://<your-server>:8501` in your browser.

### First-Time Sync Steps (Optional, Recommended)
In the **Sync & Pricing** tab:
1. Click **Sync All 14 Official Languages** to pull localized scans and live TCGPlayer/Cardmarket prices across all 14 official TCG languages.
2. Click **Price Unpriced Cards** to populate live Raw / Grade 9 / PSA 10 comps from PriceCharting.
3. Click **Cache All Scans Locally** to store scans in `/data/cached_cards/` for instant offline browsing.
