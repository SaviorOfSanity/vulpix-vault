/**
 * Phase 2: eBay Auction Radar & Sniper Alerts View.
 * Built for the last 10 minutes of an eBay auction:
 *  - Live 1s countdown timers sorted by Ending Soonest
 *  - Auto-matched against Missing & Upgradeable (<Grade 10) Master Set cards
 *  - Real Deal Score vs. Market Comp + 1-click "Verify Card & Bid" modal + "Won -> Vault"
 *  - Works immediately via "+ Track Auction URL" AND automatically via free official eBay Browse API
 */

import { api } from "./api.js";
import { langCodePill, variantBadgeHtml } from "./icons.js";
import { openCardModal } from "./modal.js";
import { esc, fmtCardNum, fmtUsd, showToast } from "./utils.js";

const radarState = {
  filter: "needed", // "needed" | "watched" | "deals" | "ending" | "all"
  buying: "ALL",    // "ALL" | "AUCTION" | "FIXED_PRICE"
  sort: "ending",   // "ending" | "deal_desc" | "price_asc"
  search: "",
  showTrackDrawer: false,
  showSetupDrawer: false,
  relinkItemId: null,
};

let countdownTimer = null;

function formatCountdown(endIso) {
  if (!endIso) return { text: "Buy It Now", urgent: false, ended: false };
  const ms = Date.parse(endIso) - Date.now();
  if (Number.isNaN(ms)) return { text: "Active", urgent: false, ended: false };
  if (ms <= 0) return { text: "ENDED", urgent: false, ended: true };

  const totalSec = Math.floor(ms / 1000);
  const days = Math.floor(totalSec / 86400);
  const hrs = Math.floor((totalSec % 86400) / 3600);
  const mins = Math.floor((totalSec % 3600) / 60);
  const secs = totalSec % 60;

  const urgent = totalSec <= 900; // <= 15 minutes!
  if (days > 0) return { text: `${days}d ${hrs}h left`, urgent: false, ended: false };
  if (hrs > 0) return { text: `${hrs}h ${String(mins).padStart(2, "0")}m left`, urgent: false, ended: false };
  return {
    text: `${String(mins).padStart(2, "0")}m ${String(secs).padStart(2, "0")}s LEFT`,
    urgent,
    ended: false,
  };
}

export function startRadarTicker() {
  stopRadarTicker();
  countdownTimer = setInterval(() => {
    document.querySelectorAll("[data-countdown-end]").forEach((el) => {
      const endIso = el.dataset.countdownEnd;
      if (!endIso) return;
      const cd = formatCountdown(endIso);
      el.textContent = cd.text;
      el.classList.toggle("urgent", cd.urgent);
    });
  }, 1000);
}

export function stopRadarTicker() {
  if (countdownTimer) {
    clearInterval(countdownTimer);
    countdownTimer = null;
  }
}

export function updateRadarScanStatus(scanState) {
  const slot = document.getElementById("radar-scan-slot");
  if (!slot || !scanState) return;
  if (scanState.running) {
    const pct = scanState.total > 0 ? Math.round((scanState.progress / scanState.total) * 100) : 10;
    slot.innerHTML = `
      <div style="margin-top:12px;">
        <div style="font-size:0.78rem; color:#fde68a; font-weight:700; margin-bottom:5px;">⚡ ${esc(scanState.message)} (${pct}%)</div>
        <div class="progress-track"><div class="progress-fill" style="width:${pct}%;"></div></div>
      </div>`;
  } else {
    slot.innerHTML = "";
  }
  const btn = document.getElementById("btn-radar-scan");
  if (btn) btn.disabled = Boolean(scanState.running);
}

function getFilteredListings(allListings) {
  const q = radarState.search.trim().toLowerCase();
  let list = allListings.filter((it) => {
    const isNeeded = it.ownership_status === "MISSING" || it.ownership_status === "UPGRADE";
    if (radarState.filter === "needed" && !isNeeded && !it.is_watched) return false;
    if (radarState.filter === "watched" && !it.is_watched) return false;
    if (radarState.filter === "deals" && !["SNIPE", "GOOD"].includes(it.deal_tier)) return false;
    if (radarState.filter === "ending") {
      if (!it.end_time) return false;
      const ms = Date.parse(it.end_time) - Date.now();
      if (Number.isNaN(ms) || ms <= 0 || ms > 3 * 3600 * 1000) return false;
    }

    if (radarState.buying === "AUCTION" && !it.buying_option.includes("AUCTION")) return false;
    if (radarState.buying === "FIXED_PRICE" && it.buying_option !== "FIXED_PRICE") return false;

    if (q) {
      const hay = `${it.title} ${it.matched_card_name} ${it.matched_set_name} ${it.matched_card_number} ${it.detected_grader} ${it.detected_grade_label} ${it.matched_language}`.toLowerCase();
      for (const tok of q.split(/\s+/).filter(Boolean)) {
        if (!hay.includes(tok)) return false;
      }
    }
    return true;
  });

  list = [...list];
  if (radarState.sort === "deal_desc") {
    list.sort((a, b) => (b.discount_pct ?? -999) - (a.discount_pct ?? -999) || a.total_cost - b.total_cost);
  } else if (radarState.sort === "price_asc") {
    list.sort((a, b) => a.total_cost - b.total_cost);
  } else {
    // Ending soonest (watched first if no end_time; auctions with soonest end_time on top)
    list.sort((a, b) => {
      const ta = a.end_time ? Date.parse(a.end_time) : Number.MAX_SAFE_INTEGER;
      const tb = b.end_time ? Date.parse(b.end_time) : Number.MAX_SAFE_INTEGER;
      return ta - tb || a.total_cost - b.total_cost;
    });
  }
  return list;
}

function dealBadgeHtml(item) {
  if (item.deal_tier === "SNIPE") {
    return `<span class="deal-badge deal-snipe">🔥 SNIPE -${Math.round(item.discount_pct)}%</span>`;
  }
  if (item.deal_tier === "GOOD") {
    return `<span class="deal-badge deal-good">✅ GOOD DEAL -${Math.round(item.discount_pct)}%</span>`;
  }
  if (item.deal_tier === "FAIR") {
    return `<span class="deal-badge deal-fair">⚖️ FAIR (-${Math.round(item.discount_pct)}%)</span>`;
  }
  if (item.deal_tier === "OVERPRICED") {
    return `<span class="deal-badge deal-overpriced">⚠️ +${Math.abs(Math.round(item.discount_pct))}% OVER</span>`;
  }
  return `<span class="deal-badge deal-unpriced">UNPRICED COMP</span>`;
}

function ownershipBadgeHtml(item) {
  if (item.ownership_status === "MISSING") {
    return `<span class="status-pill status-missing">NEEDED — MISSING</span>`;
  }
  if (item.ownership_status === "UPGRADE") {
    return `<span class="status-pill status-upgrade">UPGRADE (Own ${esc(item.best_owned_badge)})</span>`;
  }
  if (item.ownership_status === "OWNED_10") {
    return `<span class="status-pill status-owned">OWNED • ${esc(item.best_owned_badge)}</span>`;
  }
  return `<span class="status-pill" style="background:rgba(148,163,184,0.14); color:#cbd5e1; border-color:rgba(148,163,184,0.35);">UNMATCHED</span>`;
}

export function renderRadarView(radarData, catalogData, onTriggerPoll, onRefresh) {
  const container = document.getElementById("view-radar");
  if (!radarData) {
    container.innerHTML = `<div class="empty-state">Loading eBay Auction Radar...</div>`;
    return;
  }

  const s = radarData.summary || {};
  const cfg = radarData.config || {};
  const queries = radarData.queries || [];
  const allListings = radarData.listings || [];
  const catalogCards = catalogData?.cards || [];
  const filtered = getFilteredListings(allListings);

  const apiPill = cfg.ebay_configured
    ? `<span class="status-pill status-owned">eBay API Connected</span>`
    : `<span class="status-pill status-upgrade">Manual Mode — Connect Free eBay API for Auto-Scan</span>`;

  const trackDrawerHtml = radarState.showTrackDrawer
    ? `
      <div class="radar-drawer">
        <div style="display:flex; justify-content:space-between; align-items:center; gap:10px; margin-bottom:10px;">
          <div>
            <h3>+ Track Any eBay Auction or Buy It Now</h3>
            <div style="font-size:0.8rem; color:#94a3b8;">
              ${
                cfg.ebay_configured
                  ? "Paste any eBay listing URL — live title, photo, current bid, shipping, and exact countdown are fetched automatically!"
                  : "Paste an eBay listing URL + title/price/minutes left to watch it with live countdowns & instant deal scoring (connect eBay API in Setup for 1-paste auto-fill)."
              }
            </div>
          </div>
          <button class="btn btn-sm" id="btn-close-track">✕ Close</button>
        </div>
        <form id="track-auction-form">
          <div class="form-grid">
            <div class="field full">
              <label>eBay Listing URL or Item ID*</label>
              <input name="url" required placeholder="https://www.ebay.com/itm/123456789012" />
            </div>
            <div class="field full">
              <label>Listing Title ${cfg.ebay_configured ? "(Optional — auto-fetched from eBay API)" : "*"}</label>
              <input name="title" ${cfg.ebay_configured ? "" : "required"} placeholder="e.g. 1999 Pokemon Base Set Vulpix 1st Edition Shadowless #68/102 PSA 10" />
            </div>
            <div class="field">
              <label>Current Bid / Price ($)</label>
              <input name="current_price" type="number" min="0" step="0.01" placeholder="e.g. 145.00" />
            </div>
            <div class="field">
              <label>Shipping ($)</label>
              <input name="shipping_cost" type="number" min="0" step="0.01" value="4.99" />
            </div>
            <div class="field">
              <label>Minutes Remaining (for Auction Countdown)</label>
              <input name="minutes_remaining" type="number" min="1" step="1" placeholder="e.g. 45" />
            </div>
            <div class="field">
              <label>Listing Type</label>
              <select name="buying_option">
                <option value="AUCTION">Auction</option>
                <option value="FIXED_PRICE">Buy It Now</option>
              </select>
            </div>
          </div>
          <div style="display:flex; justify-content:flex-end; gap:8px; margin-top:12px;">
            <button type="submit" class="btn btn-primary">★ Add to Auction Watchlist</button>
          </div>
        </form>
      </div>`
    : "";

  const setupDrawerHtml = radarState.showSetupDrawer
    ? `
      <div class="radar-drawer">
        <div style="display:flex; justify-content:space-between; align-items:center; gap:10px; margin-bottom:8px;">
          <div>
            <h3>⚙ eBay Browse API, Push Alerts &amp; Search Queries</h3>
            <div style="font-size:0.8rem; color:#94a3b8;">
              Uses the official free eBay Developer API (5,000 calls/day, zero scraping/CAPTCHA blocks).
              <a href="https://developer.ebay.com/my/keys" target="_blank" rel="noopener" style="color:#fbbf24; font-weight:700;">Get free eBay keys ↗</a>
            </div>
          </div>
          <button class="btn btn-sm" id="btn-close-setup">✕ Close</button>
        </div>

        <form id="radar-settings-form">
          <div class="radar-setup-grid">
            <div>
              <div style="font-size:0.74rem; font-weight:800; color:#fbbf24; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:10px;">
                1. Official eBay Browse API Credentials
              </div>
              <div class="form-grid">
                <div class="field full">
                  <label>eBay Client ID (App ID)</label>
                  <input name="ebay_client_id" value="${esc(cfg.ebay_client_id || "")}" placeholder="YourApp-VulpixVa-PRD-..." />
                </div>
                <div class="field full">
                  <label>eBay Client Secret (Cert ID) ${cfg.ebay_client_secret_set ? '<span style="color:#34d399;">(Saved)</span>' : ""}</label>
                  <input name="ebay_client_secret" type="password" placeholder="${cfg.ebay_client_secret_set ? "Leave blank to keep existing secret" : "PRD-..."}" />
                </div>
                <div class="field">
                  <label>Marketplace</label>
                  <select name="ebay_marketplace">
                    ${["EBAY_US", "EBAY_GB", "EBAY_DE", "EBAY_CA", "EBAY_AU", "EBAY_FR", "EBAY_IT", "EBAY_ES", "EBAY_JP"]
                      .map((m) => `<option value="${m}" ${cfg.ebay_marketplace === m ? "selected" : ""}>${m}</option>`)
                      .join("")}
                  </select>
                </div>
                <div class="field">
                  <label>Auto-Scan Interval</label>
                  <select name="auto_scan_interval_min">
                    ${[10, 15, 30, 60]
                      .map((m) => `<option value="${m}" ${Number(cfg.auto_scan_interval_min) === m ? "selected" : ""}>Every ${m} min</option>`)
                      .join("")}
                  </select>
                </div>
                <div class="field full">
                  <label style="display:inline-flex; align-items:center; gap:8px; text-transform:none; letter-spacing:0; cursor:pointer;">
                    <input type="checkbox" name="auto_scan_enabled" ${cfg.auto_scan_enabled ? "checked" : ""} />
                    Enable automatic background eBay scanning
                  </label>
                </div>
              </div>
            </div>

            <div>
              <div style="font-size:0.74rem; font-weight:800; color:#34d399; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:10px;">
                2. Push Alerts (Gotify / Discord / ntfy)
              </div>
              <div class="form-grid">
                <div class="field">
                  <label>Gotify Server URL</label>
                  <input name="gotify_url" value="${esc(cfg.gotify_url || "")}" placeholder="http://10.0.0.48:8070" />
                </div>
                <div class="field">
                  <label>Gotify App Token ${cfg.gotify_token_set ? '<span style="color:#34d399;">(Saved)</span>' : ""}</label>
                  <input name="gotify_token" type="password" placeholder="${cfg.gotify_token_set ? "Leave blank to keep saved" : "A..."}" />
                </div>
                <div class="field full">
                  <label>Discord Webhook URL ${cfg.discord_webhook_set ? '<span style="color:#34d399;">(Saved)</span>' : ""}</label>
                  <input name="discord_webhook_url" value="${esc(cfg.discord_webhook_url || "")}" placeholder="https://discord.com/api/webhooks/..." />
                </div>
                <div class="field full">
                  <label>ntfy Topic URL (Optional)</label>
                  <input name="ntfy_url" value="${esc(cfg.ntfy_url || "")}" placeholder="https://ntfy.sh/vulpix-snipes" />
                </div>
                <div class="field">
                  <label>Alert Min Deal (% Below Comp)</label>
                  <input name="alert_min_discount_pct" type="number" min="0" max="80" value="${cfg.alert_min_discount_pct ?? 15}" />
                </div>
                <div class="field">
                  <label>Watched Ending Alert (Min Left)</label>
                  <input name="alert_ending_soon_min" type="number" min="5" max="120" value="${cfg.alert_ending_soon_min ?? 20}" />
                </div>
                <div class="field full">
                  <label style="display:inline-flex; align-items:center; gap:8px; text-transform:none; letter-spacing:0; cursor:pointer;">
                    <input type="checkbox" name="alert_needed_only" ${cfg.alert_needed_only ? "checked" : ""} />
                    Only alert for Missing / Upgradeable (&lt;Grade 10) or Watched cards
                  </label>
                </div>
              </div>
            </div>
          </div>

          <div style="display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap; margin-top:14px; padding-top:12px; border-top:1px solid rgba(255,255,255,0.08);">
            <button type="button" class="btn btn-sm" id="btn-test-alert">🔔 Send Test Alert</button>
            <button type="submit" class="btn btn-primary btn-sm">Save Radar &amp; Alert Settings</button>
          </div>
        </form>

        <div style="margin-top:18px; padding-top:14px; border-top:1px solid rgba(255,255,255,0.08);">
          <div style="font-size:0.74rem; font-weight:800; color:#cbd5e1; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:8px;">
            3. Monitored eBay Search Queries (${queries.filter((q) => q.enabled).length} Active)
          </div>
          <div class="query-list">
            ${queries
              .map(
                (q) => `
                <div class="query-row">
                  <label style="display:inline-flex; align-items:center; gap:9px; cursor:pointer; flex:1;">
                    <input type="checkbox" data-toggle-query="${q.id}" ${q.enabled ? "checked" : ""} />
                    <strong style="color:#f8fafc;">${esc(q.label || q.query)}</strong>
                    <code style="font-size:0.74rem; color:#94a3b8;">${esc(q.query)}</code>
                    <span class="lang-code-pill">${esc(q.buying_filter)}</span>
                  </label>
                  <button class="btn btn-danger btn-sm" data-del-query="${q.id}">✕</button>
                </div>`
              )
              .join("")}
          </div>
          <form id="add-query-form" style="display:flex; gap:8px; flex-wrap:wrap; margin-top:10px;">
            <input name="label" placeholder="Short label (e.g. Base 4th Print)" style="flex:1; min-width:160px; background:#0c101b; border:1px solid rgba(255,255,255,0.16); color:#f8fafc; border-radius:8px; padding:7px 10px; font-size:0.82rem;" />
            <input name="query" required placeholder="eBay search query (e.g. Vulpix 1999-2000 50 HP)" style="flex:2; min-width:220px; background:#0c101b; border:1px solid rgba(255,255,255,0.16); color:#f8fafc; border-radius:8px; padding:7px 10px; font-size:0.82rem;" />
            <select name="buying_filter" class="ctrl-select">
              <option value="ALL">All Formats</option>
              <option value="AUCTION">Auctions Only</option>
              <option value="FIXED_PRICE">Buy It Now</option>
            </select>
            <button type="submit" class="btn btn-sm btn-primary">+ Add Query</button>
          </form>
        </div>
      </div>`
    : "";

  const listingsHtml =
    filtered.length === 0
      ? `
        <div class="empty-state">
          <div style="font-size:1.05rem; font-weight:700; color:#f8fafc; margin-bottom:6px;">
            ${allListings.length === 0 ? "No active eBay listings tracked yet" : "No listings match your current filter"}
          </div>
          <div style="max-width:560px; margin:0 auto; line-height:1.5;">
            ${
              allListings.length === 0
                ? "Click <strong>+ Track Auction URL</strong> above to watch any eBay listing right now, or open <strong>⚙ Setup &amp; Alerts</strong> to plug in your free eBay Developer API keys for automatic 15-minute scanning."
                : "Switch to <strong>All Active</strong> or adjust your search/format filters above."
            }
          </div>
        </div>`
      : `
        <div class="radar-grid">
          ${filtered
            .map((it) => {
              const cd = formatCountdown(it.end_time);
              const isAuction = it.buying_option.includes("AUCTION");
              const gradePill =
                it.detected_grader === "RAW"
                  ? `<span class="lang-code-pill">RAW</span>`
                  : `<span class="status-pill ${it.detected_grade >= 10 ? "status-owned" : "status-upgrade"}">${esc(it.detected_grader)} ${it.detected_grade === Math.floor(it.detected_grade) ? it.detected_grade : it.detected_grade}${it.detected_grade_label.includes("Pristine") ? " Pristine" : ""}</span>`;

              const cardCls = `radar-card ${it.deal_tier === "SNIPE" ? "tier-snipe" : it.deal_tier === "GOOD" ? "tier-good" : ""} ${it.is_watched ? "is-watched" : ""}`;

              const matchBlock = it.catalog_key
                ? `
                  <div class="radar-match-strip">
                    <div style="display:flex; justify-content:space-between; align-items:center; gap:6px; flex-wrap:wrap;">
                      <span style="font-weight:700; color:#f8fafc;">
                        ${langCodePill(it.matched_language)} ${esc(it.matched_card_name)} — ${esc(it.matched_set_name)} ${esc(fmtCardNum(it.matched_card_number))}
                      </span>
                      <span style="font-size:0.68rem; color:#64748b;">${it.match_confidence}% match</span>
                    </div>
                    <div style="display:flex; align-items:center; justify-content:space-between; gap:8px; flex-wrap:wrap;">
                      ${variantBadgeHtml(it.matched_variant_key, it.matched_edition)}
                      <button class="btn btn-sm" style="padding:2px 7px; font-size:0.68rem;" data-open-relink="${esc(it.ebay_item_id)}">Change Match</button>
                    </div>
                  </div>`
                : `
                  <div class="radar-match-strip">
                    <div style="display:flex; justify-content:space-between; align-items:center; gap:8px;">
                      <span style="color:#94a3b8;">Not auto-matched to a specific Master Set variant yet.</span>
                      <button class="btn btn-sm" style="padding:3px 8px; font-size:0.7rem;" data-open-relink="${esc(it.ebay_item_id)}">Link to Card</button>
                    </div>
                  </div>`;

              const relinkHtml =
                radarState.relinkItemId === it.ebay_item_id
                  ? `
                    <div style="display:flex; gap:6px; align-items:center; margin-top:4px;">
                      <select class="ctrl-select" style="flex:1; font-size:0.74rem;" data-relink-select="${esc(it.ebay_item_id)}">
                        <option value="">-- Unlinked --</option>
                        ${catalogCards
                          .map(
                            (c) => `<option value="${esc(c.catalog_key)}" ${it.catalog_key === c.catalog_key ? "selected" : ""}>
                                      ${c.release_year} • ${esc(c.card_name)} — ${esc(c.set_name)} ${esc(fmtCardNum(c.card_number))} [${esc(c.language)} / ${esc(c.edition)}]
                                    </option>`
                          )
                          .join("")}
                      </select>
                      <button class="btn btn-primary btn-sm" data-save-relink="${esc(it.ebay_item_id)}">Save</button>
                    </div>`
                  : "";

              return `
                <article class="${cardCls}">
                  <div class="radar-thumb-col">
                    <img src="${esc(it.image_url || "/assets/card-placeholder.svg")}" onerror="this.onerror=null;this.src='/assets/card-placeholder.svg';" loading="lazy" alt="" />
                    <div class="countdown-pill ${cd.urgent ? "urgent" : ""}" data-countdown-end="${esc(it.end_time)}">
                      ${esc(cd.text)}
                    </div>
                    <div style="font-size:0.7rem; color:#94a3b8; text-align:center;">
                      ${isAuction ? `Auction • ${it.bid_count} bid${it.bid_count === 1 ? "" : "s"}` : "Buy It Now"}
                      ${it.seller_feedback_pct != null ? `<br/>Seller ${it.seller_feedback_pct}%` : ""}
                    </div>
                  </div>

                  <div class="radar-body">
                    <div class="radar-meta-row">
                      <div style="display:flex; gap:6px; align-items:center; flex-wrap:wrap;">
                        ${ownershipBadgeHtml(it)}
                        ${gradePill}
                      </div>
                      ${dealBadgeHtml(it)}
                    </div>

                    <div class="radar-title" title="${esc(it.title)}">${esc(it.title)}</div>

                    ${matchBlock}
                    ${relinkHtml}

                    <div class="radar-price-strip">
                      <div>
                        <div style="font-size:0.68rem; color:#94a3b8; text-transform:uppercase; font-weight:700;">Total w/ Shipping</div>
                        <div style="font-size:1.1rem; font-weight:800; color:#fbbf24;">
                          ${fmtUsd(it.total_cost)}
                          <span style="font-size:0.72rem; font-weight:600; color:#94a3b8;">(${fmtUsd(it.current_price)} + ${fmtUsd(it.shipping_cost)} ship)</span>
                        </div>
                      </div>
                      <div style="text-align:right;">
                        <div style="font-size:0.68rem; color:#94a3b8; text-transform:uppercase; font-weight:700;">Real Market Comp</div>
                        <div style="font-size:0.95rem; font-weight:700; color:${it.market_comp != null ? "#e2e8f0" : "#64748b"};">
                          ${it.market_comp != null ? fmtUsd(it.market_comp) : "Unpriced"}
                        </div>
                      </div>
                    </div>

                    <div class="radar-actions">
                      ${
                        it.catalog_key
                          ? `<button class="btn btn-primary btn-sm" data-verify-card="${esc(it.catalog_key)}">🔍 Verify Card &amp; Bid</button>`
                          : ""
                      }
                      <button class="btn btn-sm ${it.is_watched ? "btn-emerald" : ""}" data-toggle-watch="${esc(it.ebay_item_id)}" data-watched="${it.is_watched ? "1" : "0"}">
                        ${it.is_watched ? "★ Watching" : "☆ Watch"}
                      </button>
                      <button class="btn btn-emerald btn-sm" data-mark-won="${esc(it.ebay_item_id)}">🏆 Won → Vault</button>
                      <a class="btn btn-sm" href="${esc(it.url)}" target="_blank" rel="noopener">eBay ↗</a>
                      <button class="btn btn-sm" style="margin-left:auto; color:#94a3b8;" data-dismiss-item="${esc(it.ebay_item_id)}" title="Hide listing">✕</button>
                    </div>
                  </div>
                </article>`;
            })
            .join("")}
        </div>`;

  container.innerHTML = `
    <section class="hero-strip">
      <div class="hero-top">
        <h1 class="hero-headline">
          <span>eBay Auction Radar</span>
          ${apiPill}
        </h1>
        <div style="display:flex; gap:8px; flex-wrap:wrap;">
          <button class="btn btn-primary btn-sm" id="btn-radar-scan" ${radarData.scan_state?.running ? "disabled" : ""}>
            ${radarData.scan_state?.running ? "Scanning eBay..." : "⚡ Scan eBay Now"}
          </button>
          <button class="btn btn-sm" id="btn-toggle-track">+ Track Auction URL</button>
          <button class="btn btn-sm" id="btn-toggle-setup">⚙ Setup &amp; Alerts</button>
        </div>
      </div>

      ${
        cfg.last_scan_at
          ? `<div style="font-size:0.76rem; color:#94a3b8; margin-top:4px;">Last scan ${esc(cfg.last_scan_at)} — ${esc(cfg.last_scan_summary)}</div>`
          : ""
      }
      <div id="radar-scan-slot"></div>

      <div class="hero-kpis">
        <div class="kpi-tile highlight-emerald">
          <div class="kpi-label">Needed Matches</div>
          <div class="kpi-val" style="color:#34d399;">${s.needed_matches ?? 0}</div>
          <div class="kpi-sub">Missing or &lt;Grade 10 upgrades</div>
        </div>
        <div class="kpi-tile highlight-gold">
          <div class="kpi-label">Hot Deals (≥15% Off)</div>
          <div class="kpi-val" style="color:#fbbf24;">${s.hot_deals ?? 0}</div>
          <div class="kpi-sub">Priced below real market comp</div>
        </div>
        <div class="kpi-tile">
          <div class="kpi-label">Ending &lt; 1 Hour</div>
          <div class="kpi-val" style="color:${(s.ending_under_1h ?? 0) > 0 ? "#f87171" : "#f8fafc"};">${s.ending_under_1h ?? 0}</div>
          <div class="kpi-sub">${s.auctions_count ?? 0} Auctions • ${s.bin_count ?? 0} BIN</div>
        </div>
        <div class="kpi-tile">
          <div class="kpi-label">Watched Auctions</div>
          <div class="kpi-val">${s.watched_count ?? 0}</div>
          <div class="kpi-sub">Alerted in final ${cfg.alert_ending_soon_min ?? 20} min</div>
        </div>
      </div>
    </section>

    ${trackDrawerHtml}
    ${setupDrawerHtml}

    <div class="toolbar">
      <div class="segmented" id="radar-filter-seg">
        <button class="seg-btn ${radarState.filter === "needed" ? "active" : ""}" data-rf="needed">Needed &amp; Watched</button>
        <button class="seg-btn ${radarState.filter === "watched" ? "active" : ""}" data-rf="watched">Watched ★ (${s.watched_count ?? 0})</button>
        <button class="seg-btn ${radarState.filter === "deals" ? "active" : ""}" data-rf="deals">Hot Deals (${s.hot_deals ?? 0})</button>
        <button class="seg-btn ${radarState.filter === "ending" ? "active" : ""}" data-rf="ending">Ending &lt;3h</button>
        <button class="seg-btn ${radarState.filter === "all" ? "active" : ""}" data-rf="all">All Active (${s.total_active ?? 0})</button>
      </div>

      <div class="toolbar-controls">
        <input id="radar-search-in" type="search" placeholder="Filter listings..." value="${esc(radarState.search)}"
               style="background:#0c101b; border:1px solid rgba(255,255,255,0.16); color:#f8fafc; border-radius:8px; padding:6px 10px; font-size:0.8rem; width:175px;" />

        <select class="ctrl-select" id="radar-buying-sel">
          <option value="ALL" ${radarState.buying === "ALL" ? "selected" : ""}>All Formats</option>
          <option value="AUCTION" ${radarState.buying === "AUCTION" ? "selected" : ""}>Auctions Only</option>
          <option value="FIXED_PRICE" ${radarState.buying === "FIXED_PRICE" ? "selected" : ""}>Buy It Now</option>
        </select>

        <select class="ctrl-select" id="radar-sort-sel">
          <option value="ending" ${radarState.sort === "ending" ? "selected" : ""}>Ending Soonest</option>
          <option value="deal_desc" ${radarState.sort === "deal_desc" ? "selected" : ""}>Best Deal % Off</option>
          <option value="price_asc" ${radarState.sort === "price_asc" ? "selected" : ""}>Lowest Total Cost</option>
        </select>
      </div>
    </div>

    ${listingsHtml}
  `;

  updateRadarScanStatus(radarData.scan_state);

  // Wire top action buttons
  container.querySelector("#btn-radar-scan")?.addEventListener("click", async () => {
    try {
      const r = await api.startRadarScan();
      showToast(r.message, "ok");
      onTriggerPoll();
    } catch (err) {
      showToast(err.message, "err");
      if (String(err.message).includes("Client ID")) {
        radarState.showSetupDrawer = true;
        renderRadarView(radarData, catalogData, onTriggerPoll, onRefresh);
      }
    }
  });

  container.querySelector("#btn-toggle-track")?.addEventListener("click", () => {
    radarState.showTrackDrawer = !radarState.showTrackDrawer;
    if (radarState.showTrackDrawer) radarState.showSetupDrawer = false;
    renderRadarView(radarData, catalogData, onTriggerPoll, onRefresh);
  });

  container.querySelector("#btn-close-track")?.addEventListener("click", () => {
    radarState.showTrackDrawer = false;
    renderRadarView(radarData, catalogData, onTriggerPoll, onRefresh);
  });

  container.querySelector("#btn-toggle-setup")?.addEventListener("click", () => {
    radarState.showSetupDrawer = !radarState.showSetupDrawer;
    if (radarState.showSetupDrawer) radarState.showTrackDrawer = false;
    renderRadarView(radarData, catalogData, onTriggerPoll, onRefresh);
  });

  container.querySelector("#btn-close-setup")?.addEventListener("click", () => {
    radarState.showSetupDrawer = false;
    renderRadarView(radarData, catalogData, onTriggerPoll, onRefresh);
  });

  // Track single auction form
  container.querySelector("#track-auction-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const numOrNull = (v) => (v !== null && String(v).trim() !== "" ? Number(v) : null);
    try {
      await api.trackAuction({
        url: String(fd.get("url") || ""),
        title: String(fd.get("title") || ""),
        current_price: numOrNull(fd.get("current_price")),
        shipping_cost: numOrNull(fd.get("shipping_cost")),
        minutes_remaining: numOrNull(fd.get("minutes_remaining")),
        buying_option: String(fd.get("buying_option") || "AUCTION"),
      });
      radarState.showTrackDrawer = false;
      radarState.filter = "watched";
      showToast("Auction added to your Watchlist!", "ok");
      await onRefresh();
    } catch (err) {
      showToast(err.message, "err");
    }
  });

  // Radar & Alerts Settings form
  container.querySelector("#radar-settings-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      await api.updateRadarSettings({
        ebay_client_id: String(fd.get("ebay_client_id") || ""),
        ebay_client_secret: String(fd.get("ebay_client_secret") || ""),
        ebay_marketplace: String(fd.get("ebay_marketplace") || "EBAY_US"),
        auto_scan_interval_min: Number(fd.get("auto_scan_interval_min") || 15),
        auto_scan_enabled: fd.get("auto_scan_enabled") === "on",
        gotify_url: String(fd.get("gotify_url") || ""),
        gotify_token: String(fd.get("gotify_token") || ""),
        discord_webhook_url: String(fd.get("discord_webhook_url") || ""),
        ntfy_url: String(fd.get("ntfy_url") || ""),
        alert_min_discount_pct: Number(fd.get("alert_min_discount_pct") || 15),
        alert_ending_soon_min: Number(fd.get("alert_ending_soon_min") || 20),
        alert_needed_only: fd.get("alert_needed_only") === "on",
      });
      showToast("Saved Radar & Alert settings!", "ok");
      await onRefresh();
    } catch (err) {
      showToast(err.message, "err");
    }
  });

  container.querySelector("#btn-test-alert")?.addEventListener("click", async () => {
    try {
      const r = await api.testRadarAlert();
      showToast(r.message || (r.sent ? "Test alert delivered!" : "Alert failed"), r.sent ? "ok" : "err");
    } catch (err) {
      showToast(err.message, "err");
    }
  });

  // Search query controls
  container.querySelectorAll("[data-toggle-query]").forEach((chk) => {
    chk.addEventListener("change", async () => {
      try {
        await api.toggleRadarQuery(Number(chk.dataset.toggleQuery), chk.checked);
        await onRefresh();
      } catch (err) { showToast(err.message, "err"); }
    });
  });

  container.querySelectorAll("[data-del-query]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await api.deleteRadarQuery(Number(btn.dataset.delQuery));
        await onRefresh();
      } catch (err) { showToast(err.message, "err"); }
    });
  });

  container.querySelector("#add-query-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      await api.addRadarQuery({
        label: String(fd.get("label") || ""),
        query: String(fd.get("query") || ""),
        buying_filter: String(fd.get("buying_filter") || "ALL"),
      });
      showToast("Added custom eBay search query!", "ok");
      await onRefresh();
    } catch (err) { showToast(err.message, "err"); }
  });

  // Filters & sort
  container.querySelectorAll("#radar-filter-seg .seg-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      radarState.filter = btn.dataset.rf;
      renderRadarView(radarData, catalogData, onTriggerPoll, onRefresh);
    });
  });

  container.querySelector("#radar-buying-sel")?.addEventListener("change", (e) => {
    radarState.buying = e.target.value;
    renderRadarView(radarData, catalogData, onTriggerPoll, onRefresh);
  });

  container.querySelector("#radar-sort-sel")?.addEventListener("change", (e) => {
    radarState.sort = e.target.value;
    renderRadarView(radarData, catalogData, onTriggerPoll, onRefresh);
  });

  container.querySelector("#radar-search-in")?.addEventListener("input", (e) => {
    radarState.search = e.target.value;
    const caret = e.target.selectionStart ?? radarState.search.length;
    renderRadarView(radarData, catalogData, onTriggerPoll, onRefresh);
    const nextIn = container.querySelector("#radar-search-in");
    if (nextIn) {
      nextIn.focus();
      nextIn.setSelectionRange(caret, caret);
    }
  });

  // Per-card actions
  container.querySelectorAll("[data-verify-card]").forEach((btn) => {
    btn.addEventListener("click", () => {
      openCardModal(btn.dataset.verifyCard, catalogCards);
    });
  });

  container.querySelectorAll("[data-toggle-watch]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.toggleWatch;
      const next = btn.dataset.watched !== "1";
      try {
        await api.updateRadarListing(id, { is_watched: next });
        showToast(next ? "Added to Watched Auctions!" : "Removed from Watchlist.", "ok");
        await onRefresh();
      } catch (err) { showToast(err.message, "err"); }
    });
  });

  container.querySelectorAll("[data-mark-won]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.markWon;
      if (!confirm("Congrats! Move this won listing directly into your Personal Vault?")) return;
      try {
        await api.markListingWon(id, {});
        showToast("Moved won card straight into your Personal Vault!", "ok");
        await onRefresh();
      } catch (err) { showToast(err.message, "err"); }
    });
  });

  container.querySelectorAll("[data-dismiss-item]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await api.updateRadarListing(btn.dataset.dismissItem, { is_dismissed: true });
        await onRefresh();
      } catch (err) { showToast(err.message, "err"); }
    });
  });

  container.querySelectorAll("[data-open-relink]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.openRelink;
      radarState.relinkItemId = radarState.relinkItemId === id ? null : id;
      renderRadarView(radarData, catalogData, onTriggerPoll, onRefresh);
    });
  });

  container.querySelectorAll("[data-save-relink]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.saveRelink;
      const sel = container.querySelector(`[data-relink-select="${CSS.escape(id)}"]`);
      try {
        await api.updateRadarListing(id, { catalog_key: sel ? sel.value || null : null });
        radarState.relinkItemId = null;
        showToast("Updated Master Set card link!", "ok");
        await onRefresh();
      } catch (err) { showToast(err.message, "err"); }
    });
  });
}
