/**
 * Data, Multi-Language TCGdex Sync, Live Market Pricing, and Exports View.
 */

import { api } from "./api.js";
import { esc, showToast } from "./utils.js";

function renderJobLine(st, key) {
  const j = (st && st[key]) || {};
  if (j.running) {
    const pct = j.total > 0 ? Math.round((j.progress / j.total) * 100) : 0;
    return `
      <div>
        <div style="font-size:0.78rem; color:#fde68a; font-weight:700; margin-bottom:5px;">${esc(j.message)} (${pct}%)</div>
        <div class="progress-track"><div class="progress-fill" style="width:${pct}%;"></div></div>
      </div>`;
  }
  if (j.finished_at) {
    return `<div style="font-size:0.76rem; color:#6ee7b7;">Last run ${esc(j.finished_at)}: ${esc(j.message)}</div>`;
  }
  return `<div style="font-size:0.76rem; color:#64748b;">Ready to run</div>`;
}

export function updateSyncJobCards(syncState) {
  const st = syncState || {};
  const container = document.getElementById("view-sync");
  if (!container) return;
  for (const key of ["tcgdex", "prices", "cache_images", "pokecottage"]) {
    const slot = container.querySelector(`[data-job-slot="${key}"]`);
    if (slot) slot.innerHTML = renderJobLine(st, key);
  }
  const setDisabled = (sel, val) => {
    const el = container.querySelector(sel);
    if (el) el.disabled = Boolean(val);
  };
  setDisabled("#btn-sync-tcgdex", st.tcgdex?.running);
  setDisabled("#btn-price-unpriced", st.prices?.running);
  setDisabled("#btn-price-all", st.prices?.running);
  setDisabled("#btn-cache-imgs", st.cache_images?.running);
  setDisabled("#btn-sync-pc", st.pokecottage?.running);
}

export function renderSyncView(healthData, syncState, onTriggerJob, onDataRefresh) {
  const container = document.getElementById("view-sync");
  const st = syncState || {};
  const jobLine = (key) => `<div data-job-slot="${key}">${renderJobLine(st, key)}</div>`;

  container.innerHTML = `
    <section class="hero-strip">
      <div class="hero-top">
        <h1 class="hero-headline">
          <span>Data, Multi-Language Sync &amp; Real Pricing</span>
        </h1>
        <div style="display:flex; gap:8px; flex-wrap:wrap;">
          <a class="btn btn-sm" href="/api/export/wantlist.csv">Download Missing Wantlist CSV</a>
          <a class="btn btn-sm" href="/api/export/vault.csv">Download Vault Backup CSV</a>
        </div>
      </div>
      <div class="hero-kpis">
        <div class="kpi-tile">
          <div class="kpi-label">Catalog Variants</div>
          <div class="kpi-val">${healthData?.catalog_count ?? "—"}</div>
          <div class="kpi-sub">Deterministic keys (zero dupes)</div>
        </div>
        <div class="kpi-tile">
          <div class="kpi-label">Live Priced Cards</div>
          <div class="kpi-val" style="color:#fbbf24;">${healthData?.priced_count ?? "—"}</div>
          <div class="kpi-sub">PriceCharting + TCGPlayer + Cardmarket</div>
        </div>
        <div class="kpi-tile">
          <div class="kpi-label">Vault Records</div>
          <div class="kpi-val" style="color:#34d399;">${healthData?.vault_count ?? "—"}</div>
          <div class="kpi-sub">Preserved safely in SQLite</div>
        </div>
        <div class="kpi-tile">
          <div class="kpi-label">Database Health</div>
          <div class="kpi-val">${healthData?.db_size_kb ?? "—"} KB</div>
          <div class="kpi-sub">Schema v${healthData?.schema_version ?? 2} • WAL Mode</div>
        </div>
      </div>
    </section>

    <div class="sync-grid">
      <!-- 1. TCGdex All 14 Official Languages Sync -->
      <div class="sync-card">
        <h3>1. Sync All 14 Official Languages (TCGdex)</h3>
        <p>
          Queries the official open-source <strong>TCGdex API v2</strong> across all 14 official Pokémon TCG languages
          (EN, JA, FR, DE, IT, ES, PT, NL, KO, ZH-TW, ZH-CN, ID, TH, PL). Imports official foreign Vulpix &amp; Alolan Vulpix
          releases with their <strong>real localized card photos</strong> and embedded <strong>TCGPlayer (USD) &amp; Cardmarket (EUR)</strong> prices.
        </p>
        ${jobLine("tcgdex")}
        <div>
          <button class="btn btn-primary" id="btn-sync-tcgdex" ${st.tcgdex?.running ? "disabled" : ""}>
            ${st.tcgdex?.running ? "Syncing 14 Languages..." : "Sync All 14 Official Languages"}
          </button>
        </div>
      </div>

      <!-- 2. Real Market Pricing Refresh -->
      <div class="sync-card">
        <h3>2. Fetch Real Market Prices (PriceCharting + TCGdex)</h3>
        <p>
          Pulls real <strong>Raw / Ungraded</strong>, <strong>Grade 9</strong>, and <strong>PSA 10</strong> comps from PriceCharting
          and TCGdex with polite rate-limiting. Never overwrites your manually locked comps and never writes fake $2/$45 placeholders.
        </p>
        ${jobLine("prices")}
        <div style="display:flex; gap:8px; flex-wrap:wrap;">
          <button class="btn btn-primary" id="btn-price-unpriced" ${st.prices?.running ? "disabled" : ""}>
            Price Unpriced Cards
          </button>
          <button class="btn" id="btn-price-all" ${st.prices?.running ? "disabled" : ""}>
            Refresh All Prices
          </button>
        </div>
      </div>

      <!-- 3. Local Image Caching -->
      <div class="sync-card">
        <h3>3. Cache Card Photos Locally</h3>
        <p>
          Downloads remote card scans into <code>/data/cached_cards/</code> and links them in SQLite so your entire Master Set
          loads instantaneously from your local server with zero external CDN delay.
        </p>
        ${jobLine("cache_images")}
        <div>
          <button class="btn" id="btn-cache-imgs" ${st.cache_images?.running ? "disabled" : ""}>
            ${st.cache_images?.running ? "Caching Photos..." : "Cache All Scans Locally"}
          </button>
        </div>
      </div>

      <!-- 4. PokeCottage Remote Checklist Refresh -->
      <div class="sync-card">
        <h3>4. Refresh Official PokeCottage Dataset</h3>
        <p>
          Fetches the latest Vulpix checklist release data (new 2026+ sets, promos, and error scans) from PokeCottage CDN
          and merges deterministically without touching your Vault or manual prices.
        </p>
        ${jobLine("pokecottage")}
        <div>
          <button class="btn" id="btn-sync-pc" ${st.pokecottage?.running ? "disabled" : ""}>
            ${st.pokecottage?.running ? "Refreshing..." : "Refresh PokeCottage Data"}
          </button>
        </div>
      </div>
    </div>

    <!-- Custom Card Form -->
    <div class="sync-card" style="margin-top:16px;">
      <h3>Add Custom or Rare Specialty Vulpix Card to Master Set</h3>
      <p>Spotted an obscure promo, regional print, or newly discovered misprint? Add it directly to your canonical catalog.</p>
      <form id="custom-card-form">
        <div class="form-grid">
          <div class="field"><label>Card Name*</label><input name="card_name" required placeholder="e.g. Vulpix" /></div>
          <div class="field"><label>Set / Expansion*</label><input name="set_name" required placeholder="e.g. Base Set" /></div>
          <div class="field"><label>Card Number</label><input name="card_number" placeholder="e.g. 68/102" /></div>
          <div class="field"><label>Release Year</label><input name="release_year" type="number" value="2025" /></div>
          <div class="field"><label>Language</label><input name="language" value="English" /></div>
          <div class="field"><label>Edition / Variant</label><input name="edition" value="Unlimited" placeholder="1st Edition, Promo, Error..." /></div>
          <div class="field"><label>Illustrator</label><input name="artist" value="Ken Sugimori" /></div>
          <div class="field"><label>Image URL</label><input name="image_url" placeholder="https://..." /></div>
          <div class="field full">
            <label style="display:inline-flex; align-items:center; gap:8px; text-transform:none; letter-spacing:0; cursor:pointer;">
              <input type="checkbox" name="is_error" /> Mark as Documented Error Card
            </label>
          </div>
          <div class="field full"><label>Error Description / Verification Notes</label><input name="error_description" placeholder="What to look for on the card photo..." /></div>
        </div>
        <div style="margin-top:12px;">
          <button type="submit" class="btn btn-primary">Add to Master Set</button>
        </div>
      </form>
    </div>
  `;

  container.querySelector("#btn-sync-tcgdex")?.addEventListener("click", async () => {
    try {
      const r = await api.startTcgdexSync();
      showToast(r.message, "ok");
      onTriggerJob();
    } catch (e) { showToast(e.message, "err"); }
  });

  container.querySelector("#btn-price-unpriced")?.addEventListener("click", async () => {
    try {
      const r = await api.startPriceSync(true);
      showToast(r.message, "ok");
      onTriggerJob();
    } catch (e) { showToast(e.message, "err"); }
  });

  container.querySelector("#btn-price-all")?.addEventListener("click", async () => {
    try {
      const r = await api.startPriceSync(false);
      showToast(r.message, "ok");
      onTriggerJob();
    } catch (e) { showToast(e.message, "err"); }
  });

  container.querySelector("#btn-cache-imgs")?.addEventListener("click", async () => {
    try {
      const r = await api.startImageCache();
      showToast(r.message, "ok");
      onTriggerJob();
    } catch (e) { showToast(e.message, "err"); }
  });

  container.querySelector("#btn-sync-pc")?.addEventListener("click", async () => {
    try {
      const r = await api.startPokecottageSync();
      showToast(r.message, "ok");
      onTriggerJob();
    } catch (e) { showToast(e.message, "err"); }
  });

  container.querySelector("#custom-card-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      await api.addCustomCard({
        card_name: String(fd.get("card_name") || ""),
        set_name: String(fd.get("set_name") || ""),
        card_number: String(fd.get("card_number") || ""),
        release_year: Number(fd.get("release_year") || 2000),
        language: String(fd.get("language") || "English"),
        edition: String(fd.get("edition") || "Unlimited"),
        artist: String(fd.get("artist") || ""),
        image_url: String(fd.get("image_url") || ""),
        is_error: fd.get("is_error") === "on",
        error_description: String(fd.get("error_description") || ""),
        notes: String(fd.get("error_description") || ""),
      });
      e.target.reset();
      showToast("Added custom card to Master Set!", "ok");
      await onDataRefresh();
    } catch (err) {
      showToast(err.message, "err");
    }
  });
}
