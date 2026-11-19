/**
 * Master Set Binder View — 4x4 Collector Grid, Compact 5x, and Checklist Table.
 * - Clickable card photos open the Auction Command Center modal immediately.
 * - All critical info (Language, Year, Owned/Grade status, Graphical SVG Variant, Honest Price) visible right on every tile.
 */

import { langCodePill, variantBadgeHtml } from "./icons.js";
import { openCardModal } from "./modal.js";
import { esc, fmtCardNum, fmtUsd } from "./utils.js";

export const binderFilters = {
  search: "",
  status: "all", // "all" | "missing" | "owned" | "upgrade" | "errors"
  language: "ALL",
  variant: "ALL",
  sort: "chronological",
  layout: "grid4", // "grid4" | "grid5" | "table"
  page: 1,
  perPage: 16,
};

export function getFilteredCards(allCards) {
  const q = binderFilters.search.trim().toLowerCase();
  let list = allCards.filter((c) => {
    if (binderFilters.status === "missing" && c.is_owned) return false;
    if (binderFilters.status === "owned" && !c.is_owned) return false;
    if (binderFilters.status === "upgrade" && !(c.is_owned && c.needs_upgrade)) return false;
    if (binderFilters.status === "errors" && !c.is_error) return false;
    if (binderFilters.language !== "ALL" && c.language !== binderFilters.language) return false;
    if (binderFilters.variant !== "ALL" && c.variant_key !== binderFilters.variant) return false;

    if (q) {
      const hay = `${c.card_name} ${c.native_name || ""} ${c.set_name} ${c.native_set_name || ""} ${c.card_number} ${c.language} ${c.edition} ${c.artist} ${c.error_description} ${c.release_year}`.toLowerCase();
      // Multi-term AND search ("gym challenge 37" matches all 3 tokens!)
      const tokens = q.split(/\s+/).filter(Boolean);
      for (const tok of tokens) {
        if (!hay.includes(tok)) return false;
      }
    }
    return true;
  });

  list = [...list];
  if (binderFilters.sort === "newest") {
    list.sort((a, b) => b.release_year - a.release_year || a.set_name.localeCompare(b.set_name));
  } else if (binderFilters.sort === "price_g10_desc") {
    list.sort((a, b) => (b.price_grade10 ?? -1) - (a.price_grade10 ?? -1) || (b.price_raw ?? -1) - (a.price_raw ?? -1));
  } else if (binderFilters.sort === "set_name") {
    list.sort((a, b) => a.set_name.localeCompare(b.set_name) || a.release_year - b.release_year);
  } else if (binderFilters.sort === "missing_first") {
    list.sort((a, b) => Number(a.is_owned) - Number(b.is_owned) || a.release_year - b.release_year);
  } else {
    // Chronological
    list.sort((a, b) => a.release_year - b.release_year || a.set_name.localeCompare(b.set_name) || a.language.localeCompare(b.language));
  }
  return list;
}

export function renderBinderView(catalogData, onFilterChange) {
  const container = document.getElementById("view-binder");
  if (!catalogData) {
    container.innerHTML = `<div class="empty-state">Loading Vulpix Master Set...</div>`;
    return;
  }

  const allCards = catalogData.cards || [];
  const s = catalogData.summary || {};
  const filtered = getFilteredCards(allCards);

  const totalPages = Math.max(1, Math.ceil(filtered.length / binderFilters.perPage));
  if (binderFilters.page > totalPages) binderFilters.page = totalPages;
  const start = (binderFilters.page - 1) * binderFilters.perPage;
  const pageCards = binderFilters.layout === "table" ? filtered : filtered.slice(start, start + binderFilters.perPage);

  // Build language chips sorted by count desc
  const langEntries = Object.entries(s.by_language || {}).sort((a, b) => b[1].total - a[1].total);
  const langChipsHtml = [
    `<button class="lang-chip ${binderFilters.language === "ALL" ? "active" : ""}" data-lang="ALL">
       All Languages <span class="chip-count">${s.variants_owned}/${s.variants_total}</span>
     </button>`,
    ...langEntries.map(
      ([lang, st]) => `
      <button class="lang-chip ${binderFilters.language === lang ? "active" : ""}" data-lang="${esc(lang)}">
        ${langCodePill(lang)} ${esc(lang)} <span class="chip-count">${st.owned}/${st.total}</span>
      </button>`
    ),
  ].join("");

  const variantLabels = {
    "1st_edition": "1st Edition",
    "shadowless": "Shadowless",
    "4th_print": "4th Print (©1999-2000)",
    "w_stamp": "W-Stamp Promo",
    "no_rarity": "No Rarity Symbol",
    "master_ball": "Master Ball Holo",
    "poke_ball": "Poké Ball Holo",
    "reverse_holo": "Reverse Holo",
    "holo": "Holofoil",
    "rainbow": "Rainbow Rare",
    "art_rare": "Illustration / Art Rare",
    "error": "Error Cards",
    "promo": "Promos",
    "stamp": "Stamped Variants",
    "playing_card": "Playing Cards",
    "unlimited": "Unlimited / Standard",
  };
  const variantOptionsHtml = Object.keys(s.by_variant || {})
    .sort()
    .map(
      (vk) => `<option value="${esc(vk)}" ${binderFilters.variant === vk ? "selected" : ""}>${esc(variantLabels[vk] || vk)} (${s.by_variant[vk]})</option>`
    )
    .join("");

  const costRawText = s.priced_missing_raw > 0 ? fmtUsd(s.cost_to_complete_raw) : "Run Price Sync";
  const costG10Text = s.priced_missing_g10 > 0 ? fmtUsd(s.cost_to_complete_g10) : "Run Price Sync";

  let bodyHtml = "";
  if (filtered.length === 0) {
    bodyHtml = `
      <div class="empty-state">
        <div style="font-size:1.05rem; font-weight:700; color:#f8fafc; margin-bottom:6px;">No Vulpix cards match your current filters</div>
        <div>Try clearing the search query or switching language/status filters above.</div>
      </div>`;
  } else if (binderFilters.layout === "table") {
    bodyHtml = `
      <div class="data-table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>Card</th>
              <th>Status</th>
              <th>Set &amp; #</th>
              <th>Year</th>
              <th>Lang</th>
              <th>Variant / Finish</th>
              <th>Raw</th>
              <th>PSA 10</th>
            </tr>
          </thead>
          <tbody>
            ${pageCards
              .map(
                (c) => `
              <tr data-open-card="${esc(c.catalog_key)}">
                <td>
                  <div style="display:flex; align-items:center; gap:10px;">
                    <img class="table-thumb" src="${esc(c.image_url || "/assets/card-placeholder.svg")}" onerror="this.onerror=null;this.src='/assets/card-placeholder.svg';" loading="lazy" alt="" />
                    <div>
                      <div style="font-weight:700; color:#f8fafc;">
                        ${esc(c.card_name)}${c.native_name ? `<span class="tile-native">(${esc(c.native_name)})</span>` : ""}
                      </div>
                      ${c.is_error ? `<div style="font-size:0.7rem; color:#fca5a5;">⚠️ Error Card</div>` : ""}
                    </div>
                  </div>
                </td>
                <td>${renderStatusPill(c)}</td>
                <td><strong>${esc(c.set_name)}</strong> <span style="color:#8b9bb4;">• ${esc(fmtCardNum(c.card_number))}</span></td>
                <td>${c.release_year}</td>
                <td>${langCodePill(c.language)} ${esc(c.language)}</td>
                <td>${variantBadgeHtml(c.variant_key, c.edition)}</td>
                <td style="color:#fbbf24; font-weight:700;">${c.price_raw != null ? fmtUsd(c.price_raw) : '<span style="color:#64748b;">—</span>'}</td>
                <td style="color:#f59e0b; font-weight:700;">${c.price_grade10 != null ? fmtUsd(c.price_grade10) : '<span style="color:#64748b;">—</span>'}</td>
              </tr>`
              )
              .join("")}
          </tbody>
        </table>
      </div>`;
  } else {
    const gridCls = binderFilters.layout === "grid5" ? "binder-grid compact" : "binder-grid";
    bodyHtml = `
      <div class="${gridCls}">
        ${pageCards
          .map((c) => {
            const tileCls = `card-tile ${c.is_owned ? "owned" : ""} ${c.is_error ? "is-error" : ""}`;
            const priceBar =
              c.price_raw != null || c.price_grade10 != null
                ? `<span>Raw: <strong class="raw-p">${c.price_raw != null ? fmtUsd(c.price_raw) : "—"}</strong></span>
                   <span>PSA 10: <strong class="g10-p">${c.price_grade10 != null ? fmtUsd(c.price_grade10) : "—"}</strong></span>`
                : `<span class="unpriced-lbl">Unpriced — click card to fetch live comp</span>`;

            return `
              <article class="${tileCls}" data-open-card="${esc(c.catalog_key)}" tabindex="0">
                <div class="tile-top">
                  <span class="tile-lang-year">${langCodePill(c.language)} ${c.release_year}</span>
                  ${renderStatusPill(c)}
                </div>

                <div class="tile-img-frame">
                  <img src="${esc(c.image_url || "/assets/card-placeholder.svg")}" onerror="this.onerror=null;this.src='/assets/card-placeholder.svg';" loading="lazy" decoding="async" alt="${esc(c.card_name)} ${esc(c.set_name)}" />
                  ${c.is_error ? `<span class="tile-img-tag err-tag">ERROR — CLICK TO VIEW</span>` : ""}
                  ${!c.image_is_localized ? `<span class="tile-img-tag ref-tag">Ref. Art</span>` : ""}
                </div>

                <div class="tile-title" title="${esc(c.card_name)}${c.native_name ? ` (${esc(c.native_name)})` : ""}">
                  ${esc(c.card_name)}${c.native_name ? `<span class="tile-native">${esc(c.native_name)}</span>` : ""}
                </div>
                <div class="tile-set" title="${esc(c.set_name)}${c.native_set_name ? ` (${esc(c.native_set_name)})` : ""} • ${esc(fmtCardNum(c.card_number))}">
                  ${esc(c.set_name)} • ${esc(fmtCardNum(c.card_number))}
                </div>

                <div>${variantBadgeHtml(c.variant_key, c.edition)}</div>

                <div class="tile-price-bar">${priceBar}</div>
              </article>`;
          })
          .join("")}
      </div>`;
  }

  const paginationHtml =
    binderFilters.layout !== "table" && totalPages > 1
      ? `<div class="pagination-bar">
           <button class="btn btn-sm" id="pg-prev" ${binderFilters.page <= 1 ? "disabled" : ""}>← Prev Page</button>
           <span style="font-size:0.82rem; color:#cbd5e1; font-weight:700; padding:0 10px;">Page ${binderFilters.page} of ${totalPages}</span>
           <button class="btn btn-sm" id="pg-next" ${binderFilters.page >= totalPages ? "disabled" : ""}>Next Page →</button>
         </div>`
      : "";

  container.innerHTML = `
    <section class="hero-strip">
      <div class="hero-top">
        <h1 class="hero-headline">
          <span>Vulpix Master Set</span>
          <span class="hero-ratio">${s.unique_owned} / ${s.unique_total} Cards</span>
          <span class="hero-ratio-sub">(${s.unique_pct}% unique • ${s.variants_owned} / ${s.variants_total} all variants)</span>
        </h1>
        <div style="font-size:0.78rem; color:#94a3b8;">
          Click any card image to verify errors, check ownership &amp; calculate max eBay bid
        </div>
      </div>

      <div class="progress-track">
        <div class="progress-fill" style="width:${Math.min(100, s.unique_pct)}%;"></div>
      </div>

      <div class="hero-kpis">
        <div class="kpi-tile highlight-emerald">
          <div class="kpi-label">Owned / Needed</div>
          <div class="kpi-val" style="color:#34d399;">${s.variants_owned} <span style="font-size:0.95rem; color:#8b9bb4;">/ ${s.variants_missing} missing</span></div>
          <div class="kpi-sub">${s.upgradeable_owned} owned below Grade 10</div>
        </div>
        <div class="kpi-tile highlight-gold">
          <div class="kpi-label">Est. Cost to Finish (Raw)</div>
          <div class="kpi-val" style="color:#fbbf24;">${costRawText}</div>
          <div class="kpi-sub">${s.priced_missing_raw} of ${s.variants_missing} missing priced</div>
        </div>
        <div class="kpi-tile highlight-gold">
          <div class="kpi-label">Est. Cost to Finish (PSA 10)</div>
          <div class="kpi-val" style="color:#f59e0b;">${costG10Text}</div>
          <div class="kpi-sub">${s.priced_missing_g10} of ${s.variants_missing} missing priced</div>
        </div>
        <div class="kpi-tile">
          <div class="kpi-label">Live Price Coverage</div>
          <div class="kpi-val">${s.priced_total} / ${s.variants_total}</div>
          <div class="kpi-sub">Zero fake placeholders</div>
        </div>
      </div>

      <div class="lang-strip">${langChipsHtml}</div>
    </section>

    <div class="toolbar">
      <div class="segmented" id="status-seg">
        <button class="seg-btn ${binderFilters.status === "all" ? "active" : ""}" data-status="all">All</button>
        <button class="seg-btn ${binderFilters.status === "missing" ? "active" : ""}" data-status="missing">Missing</button>
        <button class="seg-btn ${binderFilters.status === "owned" ? "active" : ""}" data-status="owned">Owned</button>
        <button class="seg-btn ${binderFilters.status === "upgrade" ? "active" : ""}" data-status="upgrade">Upgradeable</button>
        <button class="seg-btn ${binderFilters.status === "errors" ? "active" : ""}" data-status="errors">Errors</button>
      </div>

      <div class="toolbar-controls">
        <select class="ctrl-select" id="sel-variant" aria-label="Filter by variant">
          <option value="ALL">All Variants</option>
          ${variantOptionsHtml}
        </select>

        <select class="ctrl-select" id="sel-sort" aria-label="Sort cards">
          <option value="chronological" ${binderFilters.sort === "chronological" ? "selected" : ""}>Chronological (1996→2026)</option>
          <option value="newest" ${binderFilters.sort === "newest" ? "selected" : ""}>Newest First</option>
          <option value="missing_first" ${binderFilters.sort === "missing_first" ? "selected" : ""}>Missing First</option>
          <option value="price_g10_desc" ${binderFilters.sort === "price_g10_desc" ? "selected" : ""}>Highest PSA 10 Value</option>
          <option value="set_name" ${binderFilters.sort === "set_name" ? "selected" : ""}>Set Name (A→Z)</option>
        </select>

        <div class="segmented" id="layout-seg">
          <button class="seg-btn ${binderFilters.layout === "grid4" ? "active" : ""}" data-layout="grid4" title="4x4 Collector Binder">4×4</button>
          <button class="seg-btn ${binderFilters.layout === "grid5" ? "active" : ""}" data-layout="grid5" title="Compact 5-Column">5×</button>
          <button class="seg-btn ${binderFilters.layout === "table" ? "active" : ""}" data-layout="table" title="Checklist Table">List</button>
        </div>
      </div>
    </div>

    <div class="results-meta">
      <div>Showing <strong>${pageCards.length}</strong> of <strong>${filtered.length}</strong> matching cards ${binderFilters.search ? `for "<em>${esc(binderFilters.search)}</em>"` : ""}</div>
      ${
        binderFilters.layout !== "table"
          ? `<label style="display:inline-flex; align-items:center; gap:6px;">
               Per page:
               <select class="ctrl-select" id="sel-per-page" style="padding:4px 8px;">
                 ${[16, 32, 64, 128].map((n) => `<option value="${n}" ${binderFilters.perPage === n ? "selected" : ""}>${n}</option>`).join("")}
               </select>
             </label>`
          : ""
      }
    </div>

    ${bodyHtml}
    ${paginationHtml}
  `;

  // Wire up interactive listeners
  container.querySelectorAll(".lang-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      binderFilters.language = btn.dataset.lang;
      binderFilters.page = 1;
      onFilterChange();
    });
  });

  container.querySelectorAll("#status-seg .seg-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      binderFilters.status = btn.dataset.status;
      binderFilters.page = 1;
      onFilterChange();
    });
  });

  container.querySelectorAll("#layout-seg .seg-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      binderFilters.layout = btn.dataset.layout;
      binderFilters.page = 1;
      onFilterChange();
    });
  });

  container.querySelector("#sel-variant")?.addEventListener("change", (e) => {
    binderFilters.variant = e.target.value;
    binderFilters.page = 1;
    onFilterChange();
  });

  container.querySelector("#sel-sort")?.addEventListener("change", (e) => {
    binderFilters.sort = e.target.value;
    binderFilters.page = 1;
    onFilterChange();
  });

  container.querySelector("#sel-per-page")?.addEventListener("change", (e) => {
    binderFilters.perPage = Number(e.target.value);
    binderFilters.page = 1;
    onFilterChange();
  });

  container.querySelector("#pg-prev")?.addEventListener("click", () => {
    if (binderFilters.page > 1) {
      binderFilters.page -= 1;
      onFilterChange();
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  });

  container.querySelector("#pg-next")?.addEventListener("click", () => {
    if (binderFilters.page < totalPages) {
      binderFilters.page += 1;
      onFilterChange();
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  });

  // Clicking ANY card tile or table row opens the Auction Command Center modal!
  container.querySelectorAll("[data-open-card]").forEach((el) => {
    const open = () => openCardModal(el.dataset.openCard, filtered);
    el.addEventListener("click", open);
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        open();
      }
    });
  });
}

function renderStatusPill(card) {
  if (!card.is_owned) {
    return `<span class="status-pill status-missing">NEEDED</span>`;
  }
  if (card.needs_upgrade) {
    return `<span class="status-pill status-upgrade" title="Owned below Grade 10 — upgrade candidate">OWNED • ${esc(card.best_owned_badge)}</span>`;
  }
  return `<span class="status-pill status-owned">OWNED • ${esc(card.best_owned_badge)}</span>`;
}
