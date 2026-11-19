/**
 * Card Inspection & "Last 10 Minutes of an eBay Auction" Command Center Modal.
 * Answers in <5 seconds:
 *   1. Do I already own this exact card/variant (and do I need a Grade 10 upgrade)?
 *   2. What should I bid right now (real market comps + net-of-shipping bid calculator)?
 *   3. Is the eBay listing accurate (photo error/stamp overlays + variant SVG + specs)?
 */

import { api } from "./api.js";
import { langCodePill, variantBadgeHtml } from "./icons.js";
import { computeBidTargets, esc, fmtCardNum, fmtUsd, showToast } from "./utils.js";

let currentList = [];
let currentIdx = -1;
let showCallouts = true;
let bidTier = "psa10"; // "raw" | "g9" | "psa10" | "pristine10"
let bidShipping = 4.99;
let customMarketInput = "";
let quickAddOpen = false;
let priceEditOpen = false;
let onDataMutated = () => {};

export function initModal({ onChange }) {
  onDataMutated = onChange;

  const backdrop = document.getElementById("card-modal-backdrop");
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) closeCardModal();
  });

  document.addEventListener("keydown", (e) => {
    if (backdrop.classList.contains("hidden")) return;
    if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) return;
    if (e.key === "Escape") closeCardModal();
    if (e.key === "ArrowLeft" && currentIdx > 0) {
      currentIdx -= 1;
      resetTransientState();
      renderModal();
    }
    if (e.key === "ArrowRight" && currentIdx < currentList.length - 1) {
      currentIdx += 1;
      resetTransientState();
      renderModal();
    }
  });
}

function resetTransientState() {
  const card = currentList[currentIdx];
  showCallouts = Boolean(card && (card.is_error || (card.visual_callouts && card.visual_callouts.length > 0)));
  quickAddOpen = false;
  priceEditOpen = false;
  customMarketInput = "";
  // Auto-select the best priced tier for the bid calculator
  if (card) {
    if (card.price_grade10 != null) bidTier = "psa10";
    else if (card.price_raw != null) bidTier = "raw";
    else if (card.price_grade9 != null) bidTier = "g9";
    else bidTier = "psa10";
  }
}

export function openCardModal(cardKey, filteredCards) {
  currentList = filteredCards || [];
  currentIdx = currentList.findIndex((c) => c.catalog_key === cardKey);
  if (currentIdx === -1) return;

  resetTransientState();
  renderModal();
  document.getElementById("card-modal-backdrop").classList.remove("hidden");
  document.body.style.overflow = "hidden";
}

export function updateModalList(updatedCards) {
  const backdrop = document.getElementById("card-modal-backdrop");
  if (backdrop.classList.contains("hidden") || currentIdx < 0) return;
  const activeKey = currentList[currentIdx]?.catalog_key;
  if (!activeKey) return;
  const fresh = updatedCards.find((c) => c.catalog_key === activeKey);
  if (fresh) {
    currentList[currentIdx] = fresh;
    renderModal();
  }
}

export function closeCardModal() {
  document.getElementById("card-modal-backdrop").classList.add("hidden");
  document.body.style.overflow = "";
}

function getSelectedMarketValue(card) {
  if (customMarketInput !== "" && !Number.isNaN(Number(customMarketInput)) && Number(customMarketInput) > 0) {
    return Number(customMarketInput);
  }
  if (bidTier === "raw") return card.price_raw;
  if (bidTier === "g9") return card.price_grade9;
  if (bidTier === "psa10") return card.price_grade10;
  if (bidTier === "pristine10") {
    return card.price_grade10 != null ? Math.round(card.price_grade10 * 1.35 * 100) / 100 : null;
  }
  return null;
}

function renderModal() {
  const modal = document.getElementById("card-modal");
  const card = currentList[currentIdx];
  if (!card) return;

  const callouts = card.visual_callouts || [];
  const hasCallouts = callouts.length > 0;
  const mv = getSelectedMarketValue(card);
  const targets = computeBidTargets(mv, bidShipping);

  const overlayHtml =
    hasCallouts && showCallouts
      ? `<div class="callout-overlay">
          ${callouts
            .map(
              (co, i) => `
              <div class="callout-box sev-${esc(co.severity || "verify")}"
                   style="left:${co.x}%; top:${co.y}%; width:${co.w}%; height:${co.h}%;">
                <span class="callout-num">${i + 1}</span>
              </div>`
            )
            .join("")}
        </div>`
      : "";

  const legendHtml = hasCallouts
    ? `<div class="callout-legend">
        ${callouts
          .map(
            (co, i) => `
            <div class="callout-legend-item sev-${esc(co.severity || "verify")}">
              <span class="legend-badge-num">${i + 1}</span>
              <div>
                <div style="font-weight:800; color:#f8fafc;">${esc(co.label)}</div>
                <div style="color:#cbd5e1; margin-top:2px; line-height:1.4;">${esc(co.detail)}</div>
              </div>
            </div>`
          )
          .join("")}
      </div>`
    : "";

  // Ownership section HTML
  let ownershipHtml = "";
  if (card.is_owned) {
    const copiesHtml = card.owned_items
      .map(
        (it) => `
        <div style="display:flex; justify-content:space-between; align-items:center; gap:10px; background:rgba(0,0,0,0.28); padding:8px 11px; border-radius:8px; margin-top:6px; font-size:0.82rem;">
          <div>
            <strong style="color:#6ee7b7;">${esc(it.is_raw ? "Raw Single" : `${it.grading_company} ${it.grade} (${it.grade_label})`)}</strong>
            ${it.cert_number ? `<span style="color:#94a3b8; margin-left:6px;">Cert #${esc(it.cert_number)}</span>` : ""}
            <div style="color:#94a3b8; font-size:0.75rem; margin-top:2px;">Paid ${fmtUsd(it.purchase_price)} ${it.purchase_date ? `on ${esc(it.purchase_date)}` : ""}</div>
          </div>
          <button class="btn btn-danger btn-sm" data-del-vault="${it.id}">Remove</button>
        </div>`
      )
      .join("");

    const upgradeNote = card.needs_upgrade
      ? `<div style="margin-top:8px; padding:7px 10px; border-radius:8px; background:rgba(245,158,11,0.14); border:1px solid rgba(245,158,11,0.45); color:#fde68a; font-size:0.78rem; font-weight:700;">
           Upgrade Candidate — Highest copy owned is ${esc(card.best_owned_badge)}. Bid if upgrading to PSA 10 / CGC Pristine 10!
         </div>`
      : `<div style="margin-top:8px; color:#6ee7b7; font-size:0.78rem; font-weight:700;">
           Peak Grade 10 achieved in your Vault (${esc(card.best_owned_badge)}).
         </div>`;

    ownershipHtml = `
      <div class="decision-card owned-panel">
        <div class="decision-card-head">
          <div>
            <div class="decision-step-label" style="color:#6ee7b7;">1. Ownership Status</div>
            <div style="font-size:1.05rem; font-weight:800; color:#f8fafc;">In Your Vault (${card.owned_count} ${card.owned_count === 1 ? "copy" : "copies"})</div>
          </div>
          <button class="btn btn-emerald btn-sm" id="btn-toggle-quick-add">+ Add Another Copy</button>
        </div>
        ${copiesHtml}
        ${upgradeNote}
        <div id="quick-add-slot"></div>
      </div>`;
  } else {
    ownershipHtml = `
      <div class="decision-card">
        <div class="decision-card-head">
          <div>
            <div class="decision-step-label">1. Ownership Status</div>
            <div style="font-size:1.05rem; font-weight:800; color:#fbbf24;">Missing — Needed for Master Set</div>
          </div>
          <button class="btn btn-primary btn-sm" id="btn-toggle-quick-add">+ Mark Owned / Add to Vault</button>
        </div>
        <div style="font-size:0.8rem; color:#94a3b8;">You do not own this exact variant yet. Add it directly after winning an auction.</div>
        <div id="quick-add-slot"></div>
      </div>`;
  }

  // Price source subtitle
  const priceMeta = card.price_source
    ? `Source: <strong style="color:#cbd5e1;">${esc(card.price_source)}</strong>${card.price_updated_at ? ` • Updated ${esc(card.price_updated_at)}` : ""}${card.price_manual_lock ? " (Locked)" : ""}`
    : `<span style="color:#f59e0b;">No verified live comp fetched yet — click Refresh Live Price or enter a custom comp below.</span>`;

  modal.innerHTML = `
    <div class="modal-header">
      <div class="modal-nav-group">
        <button class="btn btn-sm" id="modal-prev" ${currentIdx <= 0 ? "disabled" : ""}>← Prev</button>
        <button class="btn btn-sm" id="modal-next" ${currentIdx >= currentList.length - 1 ? "disabled" : ""}>Next →</button>
      </div>
      <div class="modal-title-block">
        <h2 class="modal-title">${esc(card.card_name)}</h2>
        <div class="modal-subtitle">
          ${esc(card.set_name)} • ${esc(fmtCardNum(card.card_number))} • ${esc(card.language)} • (${currentIdx + 1} / ${currentList.length})
        </div>
      </div>
      <button class="btn btn-sm" id="modal-close">✕ Close</button>
    </div>

    <div class="modal-body-split">
      <!-- Left: Card Photo + Interactive Error/Verification Overlays -->
      <div class="inspect-stage">
        <div class="card-photo-wrap">
          <img src="${esc(card.image_url || "/assets/card-placeholder.svg")}" onerror="this.onerror=null;this.src='/assets/card-placeholder.svg';" alt="${esc(card.card_name)} ${esc(card.set_name)}" />
          ${overlayHtml}
        </div>

        ${
          !card.image_is_localized
            ? `<div style="width:100%; font-size:0.75rem; color:#fcd34d; background:rgba(245,158,11,0.1); border:1px solid rgba(245,158,11,0.35); padding:7px 10px; border-radius:8px;">
                 Reference artwork shown — run <strong>Sync 14 Languages (TCGdex)</strong> to pull the localized ${esc(card.language)} scan when available.
               </div>`
            : ""
        }

        ${
          hasCallouts
            ? `<div class="overlay-toggle-row">
                 <label style="display:inline-flex; align-items:center; gap:7px; cursor:pointer; font-weight:700;">
                   <input type="checkbox" id="chk-toggle-callouts" ${showCallouts ? "checked" : ""} />
                   Show Visual Verification Overlay (${callouts.length})
                 </label>
                 <span style="color:#64748b; font-size:0.72rem;">Compare vs seller photos</span>
               </div>`
            : ""
        }

        ${legendHtml}
      </div>

      <!-- Right: 3 Instant Auction Decision Panels -->
      <div class="decision-stack">
        ${ownershipHtml}

        <!-- Panel 2: Real Market Pricing & Bid Calculator -->
        <div class="decision-card">
          <div class="decision-card-head">
            <div>
              <div class="decision-step-label">2. Market Pricing &amp; Max Bid Calculator</div>
              <div style="font-size:0.76rem; color:#94a3b8; margin-top:2px;">${priceMeta}</div>
            </div>
            <div style="display:flex; gap:6px;">
              <button class="btn btn-sm" id="btn-refresh-price">↻ Refresh Live Price</button>
              <button class="btn btn-sm" id="btn-edit-price">✏️ Set Comp</button>
            </div>
          </div>

          <div class="price-grid-3">
            <div class="price-box">
              <div class="price-box-lbl">Raw / Ungraded</div>
              <div class="price-box-val ${card.price_raw == null ? "na" : ""}">${card.price_raw != null ? fmtUsd(card.price_raw) : "Unpriced"}</div>
            </div>
            <div class="price-box">
              <div class="price-box-lbl">Grade 9 Mint</div>
              <div class="price-box-val ${card.price_grade9 == null ? "na" : ""}">${card.price_grade9 != null ? fmtUsd(card.price_grade9) : "Unpriced"}</div>
            </div>
            <div class="price-box">
              <div class="price-box-lbl">PSA 10 Gem Mint</div>
              <div class="price-box-val ${card.price_grade10 == null ? "na" : ""}">${card.price_grade10 != null ? fmtUsd(card.price_grade10) : "Unpriced"}</div>
            </div>
          </div>

          <div id="price-edit-slot"></div>

          <div class="bid-calc-bar">
            <div class="segmented" id="bid-tier-seg">
              <button class="seg-btn ${bidTier === "raw" ? "active" : ""}" data-tier="raw">Raw</button>
              <button class="seg-btn ${bidTier === "g9" ? "active" : ""}" data-tier="g9">Grade 9</button>
              <button class="seg-btn ${bidTier === "psa10" ? "active" : ""}" data-tier="psa10">PSA 10</button>
              <button class="seg-btn ${bidTier === "pristine10" ? "active" : ""}" data-tier="pristine10">Pristine 10</button>
            </div>
            <label style="display:inline-flex; align-items:center; gap:6px; font-size:0.76rem; color:#94a3b8; font-weight:700;">
              Ship $
              <input id="bid-ship-in" type="number" min="0" step="0.50" value="${bidShipping}"
                     style="width:72px; background:#0c101b; border:1px solid rgba(255,255,255,0.16); color:#f8fafc; border-radius:6px; padding:4px 7px; font-size:0.8rem;" />
            </label>
            <label style="display:inline-flex; align-items:center; gap:6px; font-size:0.76rem; color:#94a3b8; font-weight:700;">
              Override MV $
              <input id="bid-mv-in" type="number" min="0" step="1" placeholder="Auto" value="${esc(customMarketInput)}"
                     style="width:82px; background:#0c101b; border:1px solid rgba(255,255,255,0.16); color:#f8fafc; border-radius:6px; padding:4px 7px; font-size:0.8rem;" />
            </label>
          </div>

          <div class="bid-targets">
            <div class="bid-target bid-snipe">
              <div class="bid-target-lbl">Snipe Max (-30%)</div>
              <div class="bid-target-num">${targets.snipe != null ? fmtUsd(targets.snipe) : "—"}</div>
            </div>
            <div class="bid-target bid-good">
              <div class="bid-target-lbl">Good Deal (-15%)</div>
              <div class="bid-target-num">${targets.good != null ? fmtUsd(targets.good) : "—"}</div>
            </div>
            <div class="bid-target bid-fair">
              <div class="bid-target-lbl">Fair Market Cap</div>
              <div class="bid-target-num">${targets.fair != null ? fmtUsd(targets.fair) : "—"}</div>
            </div>
          </div>
        </div>

        <!-- Panel 3: Listing Accuracy Checklist & External Comps -->
        <div class="decision-card">
          <div class="decision-card-head">
            <div class="decision-step-label">3. Listing Verification &amp; Card Specs</div>
            <div>${variantBadgeHtml(card.variant_key, card.edition)}</div>
          </div>

          <div class="spec-grid">
            <div class="spec-item"><div class="spec-k">Card Number</div><div class="spec-v">${esc(fmtCardNum(card.card_number))}</div></div>
            <div class="spec-item"><div class="spec-k">Release Year</div><div class="spec-v">${esc(card.release_year)}</div></div>
            <div class="spec-item"><div class="spec-k">Language</div><div class="spec-v">${langCodePill(card.language)} ${esc(card.language)}</div></div>
            <div class="spec-item"><div class="spec-k">Set / Expansion</div><div class="spec-v">${esc(card.set_name)}</div></div>
            <div class="spec-item"><div class="spec-k">Illustrator</div><div class="spec-v">${esc(card.artist || "Unknown")}</div></div>
            <div class="spec-item"><div class="spec-k">Rarity</div><div class="spec-v">${esc(card.rarity)}</div></div>
          </div>

          ${
            card.notes
              ? `<div style="font-size:0.82rem; color:#cbd5e1; background:rgba(9,12,20,0.55); border:1px solid rgba(255,255,255,0.07); border-radius:8px; padding:10px 12px; margin-bottom:12px; line-height:1.45;">
                   ${esc(card.notes)}
                 </div>`
              : ""
          }

          <div class="ext-links-row">
            <a class="btn btn-sm" href="${esc(card.ebay_sold_url)}" target="_blank" rel="noopener">eBay Sold Comps ↗</a>
            <a class="btn btn-sm" href="${esc(card.ebay_active_url)}" target="_blank" rel="noopener">eBay Ending Soon ↗</a>
            <a class="btn btn-sm" href="${esc(card.pricecharting_url)}" target="_blank" rel="noopener">PriceCharting ↗</a>
            <a class="btn btn-sm" href="${esc(card.tcgplayer_url)}" target="_blank" rel="noopener">TCGPlayer ↗</a>
          </div>
        </div>
      </div>
    </div>
  `;

  // Render inline Quick-Add drawer if open
  if (quickAddOpen) {
    renderQuickAddForm(card);
  }
  if (priceEditOpen) {
    renderPriceEditForm(card);
  }

  // Bind navigation & actions
  modal.querySelector("#modal-close")?.addEventListener("click", closeCardModal);
  modal.querySelector("#modal-prev")?.addEventListener("click", () => {
    if (currentIdx > 0) {
      currentIdx -= 1;
      resetTransientState();
      renderModal();
    }
  });
  modal.querySelector("#modal-next")?.addEventListener("click", () => {
    if (currentIdx < currentList.length - 1) {
      currentIdx += 1;
      resetTransientState();
      renderModal();
    }
  });

  modal.querySelector("#chk-toggle-callouts")?.addEventListener("change", (e) => {
    showCallouts = e.target.checked;
    renderModal();
  });

  modal.querySelector("#btn-toggle-quick-add")?.addEventListener("click", () => {
    quickAddOpen = !quickAddOpen;
    renderModal();
  });

  modal.querySelector("#btn-edit-price")?.addEventListener("click", () => {
    priceEditOpen = !priceEditOpen;
    renderModal();
  });

  modal.querySelector("#btn-refresh-price")?.addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    btn.disabled = true;
    btn.textContent = "Fetching...";
    try {
      const res = await api.refreshCardPrice(card.catalog_key);
      if (res.updated) {
        showToast(`Updated live price from ${res.price_source}!`, "ok");
        await onDataMutated();
      } else {
        showToast(res.message || "No live price found — you can set a manual comp.", "info");
      }
    } catch (err) {
      showToast(`Live price lookup failed: ${err.message}`, "err");
    } finally {
      btn.disabled = false;
      btn.textContent = "↻ Refresh Live Price";
    }
  });

  modal.querySelectorAll("[data-del-vault]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const vid = Number(btn.dataset.delVault);
      if (!confirm("Remove this copy from your Vault?")) return;
      try {
        await api.deleteVaultItem(vid);
        showToast("Removed copy from Vault.", "ok");
        await onDataMutated();
      } catch (err) {
        showToast(err.message, "err");
      }
    });
  });

  modal.querySelectorAll("#bid-tier-seg .seg-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      bidTier = btn.dataset.tier;
      customMarketInput = "";
      renderModal();
    });
  });

  modal.querySelector("#bid-ship-in")?.addEventListener("input", (e) => {
    bidShipping = Number(e.target.value || 0);
    updateBidNumbersOnly(card);
  });

  modal.querySelector("#bid-mv-in")?.addEventListener("input", (e) => {
    customMarketInput = e.target.value;
    updateBidNumbersOnly(card);
  });
}

function updateBidNumbersOnly(card) {
  const mv = getSelectedMarketValue(card);
  const t = computeBidTargets(mv, bidShipping);
  const modal = document.getElementById("card-modal");
  const snipeEl = modal.querySelector(".bid-snipe .bid-target-num");
  const goodEl = modal.querySelector(".bid-good .bid-target-num");
  const fairEl = modal.querySelector(".bid-fair .bid-target-num");
  if (snipeEl) snipeEl.textContent = t.snipe != null ? fmtUsd(t.snipe) : "—";
  if (goodEl) goodEl.textContent = t.good != null ? fmtUsd(t.good) : "—";
  if (fairEl) fairEl.textContent = t.fair != null ? fmtUsd(t.fair) : "—";
}

function renderQuickAddForm(card) {
  const slot = document.getElementById("quick-add-slot");
  if (!slot) return;
  const today = new Date().toISOString().slice(0, 10);
  slot.innerHTML = `
    <form id="quick-add-form" style="margin-top:12px; padding-top:12px; border-top:1px solid rgba(255,255,255,0.08);">
      <div class="form-grid">
        <div class="field">
          <label>Format / Grader</label>
          <select name="grading_company" id="qa-grader">
            <option value="RAW">Raw Single</option>
            <option value="PSA">PSA Slab</option>
            <option value="CGC" selected>CGC Slab</option>
            <option value="BGS">BGS / Beckett</option>
            <option value="ARS">ARS</option>
            <option value="ACE">ACE</option>
          </select>
        </div>
        <div class="field">
          <label>Grade</label>
          <input name="grade" id="qa-grade" type="number" min="0" max="10" step="0.5" value="10" />
        </div>
        <div class="field">
          <label>Grade Label</label>
          <select name="grade_label" id="qa-label">
            <option value="Gem Mint 10">Gem Mint 10</option>
            <option value="Pristine 10">Pristine 10</option>
            <option value="Black Label 10">Black Label 10</option>
            <option value="Mint 9">Mint 9</option>
            <option value="Near Mint 8">Near Mint 8</option>
            <option value="Raw Single">Raw Single</option>
          </select>
        </div>
        <div class="field">
          <label>Price Paid ($)</label>
          <input name="purchase_price" type="number" min="0" step="0.01" value="${card.price_grade10 ?? card.price_raw ?? 0}" />
        </div>
        <div class="field">
          <label>Cert # (Optional)</label>
          <input name="cert_number" type="text" placeholder="e.g. 84729103" />
        </div>
        <div class="field">
          <label>Purchase Date</label>
          <input name="purchase_date" type="date" value="${today}" />
        </div>
        <div class="field full">
          <label>Notes</label>
          <input name="notes" type="text" placeholder="eBay order #, condition notes..." />
        </div>
      </div>
      <div style="display:flex; gap:8px; margin-top:12px; justify-content:flex-end;">
        <button type="button" class="btn btn-sm" id="qa-cancel">Cancel</button>
        <button type="submit" class="btn btn-primary btn-sm">Save to Vault</button>
      </div>
    </form>
  `;

  const graderSel = slot.querySelector("#qa-grader");
  const gradeIn = slot.querySelector("#qa-grade");
  const labelSel = slot.querySelector("#qa-label");
  graderSel.addEventListener("change", () => {
    if (graderSel.value === "RAW") {
      gradeIn.value = "0";
      labelSel.value = "Raw Single";
    } else if (gradeIn.value === "0") {
      gradeIn.value = "10";
      labelSel.value = "Gem Mint 10";
    }
  });

  slot.querySelector("#qa-cancel").addEventListener("click", () => {
    quickAddOpen = false;
    renderModal();
  });

  slot.querySelector("#quick-add-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const grader = String(fd.get("grading_company") || "RAW");
    const isRaw = grader === "RAW";
    try {
      await api.addVaultItem({
        catalog_key: card.catalog_key,
        card_name: card.card_name,
        set_name: card.set_name,
        card_number: card.card_number,
        language: card.language,
        edition: card.edition,
        is_raw: isRaw,
        grading_company: grader,
        grade: isRaw ? 0 : Number(fd.get("grade") || 0),
        grade_label: isRaw ? "Raw Single" : String(fd.get("grade_label") || "Gem Mint"),
        cert_number: String(fd.get("cert_number") || ""),
        purchase_price: Number(fd.get("purchase_price") || 0),
        purchase_date: String(fd.get("purchase_date") || today),
        image_url: card.image_url,
        notes: String(fd.get("notes") || ""),
      });
      quickAddOpen = false;
      showToast(`Added ${card.card_name} (${card.edition}) to your Vault!`, "ok");
      await onDataMutated();
    } catch (err) {
      showToast(err.message, "err");
    }
  });
}

function renderPriceEditForm(card) {
  const slot = document.getElementById("price-edit-slot");
  if (!slot) return;
  slot.innerHTML = `
    <form id="price-edit-form" style="background:rgba(0,0,0,0.3); border:1px solid rgba(245,158,11,0.35); border-radius:10px; padding:12px; margin-bottom:12px;">
      <div class="form-grid">
        <div class="field">
          <label>Raw Price ($)</label>
          <input name="price_raw" type="number" step="0.01" min="0" value="${card.price_raw ?? ""}" placeholder="e.g. 8.50" />
        </div>
        <div class="field">
          <label>Grade 9 Price ($)</label>
          <input name="price_grade9" type="number" step="0.01" min="0" value="${card.price_grade9 ?? ""}" placeholder="e.g. 32.00" />
        </div>
        <div class="field">
          <label>PSA 10 Price ($)</label>
          <input name="price_grade10" type="number" step="0.01" min="0" value="${card.price_grade10 ?? ""}" placeholder="e.g. 145.00" />
        </div>
        <div class="field">
          <label>PriceCharting Direct URL (Optional)</label>
          <input name="pricecharting_url" type="url" value="${esc((card.pricecharting_url || "").includes("/game/") ? card.pricecharting_url : "")}" placeholder="https://www.pricecharting.com/game/..." />
        </div>
      </div>
      <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px; gap:8px;">
        ${card.price_manual_lock ? `<button type="button" class="btn btn-sm" id="btn-unlock-price">Unlock Auto Pricing</button>` : `<span></span>`}
        <div style="display:flex; gap:6px;">
          <button type="button" class="btn btn-sm" id="pe-cancel">Cancel</button>
          <button type="submit" class="btn btn-primary btn-sm">Save Comp</button>
        </div>
      </div>
    </form>
  `;

  slot.querySelector("#pe-cancel").addEventListener("click", () => {
    priceEditOpen = false;
    renderModal();
  });

  slot.querySelector("#btn-unlock-price")?.addEventListener("click", async () => {
    try {
      await api.overrideCardPrice(card.catalog_key, { unlock_auto_pricing: true });
      priceEditOpen = false;
      showToast("Unlocked auto-pricing for this card.", "ok");
      await onDataMutated();
    } catch (err) {
      showToast(err.message, "err");
    }
  });

  slot.querySelector("#price-edit-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const numOrNull = (v) => (v !== null && String(v).trim() !== "" ? Number(v) : null);
    try {
      await api.overrideCardPrice(card.catalog_key, {
        price_raw: numOrNull(fd.get("price_raw")),
        price_grade9: numOrNull(fd.get("price_grade9")),
        price_grade10: numOrNull(fd.get("price_grade10")),
        pricecharting_url: String(fd.get("pricecharting_url") || ""),
      });
      priceEditOpen = false;
      showToast("Saved manual market comp!", "ok");
      await onDataMutated();
    } catch (err) {
      showToast(err.message, "err");
    }
  });
}
