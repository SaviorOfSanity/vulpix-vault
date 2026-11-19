/**
 * Personal Vault & Portfolio View — Add/Edit/Delete slabs & raw singles cleanly.
 * Faithfully preserves grading company & grade labels when editing.
 */

import { api } from "./api.js";
import { langCodePill } from "./icons.js";
import { openCardModal } from "./modal.js";
import { esc, fmtCardNum, fmtUsd, showToast } from "./utils.js";

let vaultFilter = "all"; // "all" | "peak10" | "upgrade" | "graded" | "raw"
let vaultSearch = "";

export function initVaultModal() {
  const backdrop = document.getElementById("vault-modal-backdrop");
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) closeVaultModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !backdrop.classList.contains("hidden")) {
      closeVaultModal();
    }
  });
}

export function closeVaultModal() {
  document.getElementById("vault-modal-backdrop").classList.add("hidden");
  document.body.style.overflow = "";
}

export function renderVaultView(vaultData, catalogData, onChange) {
  const container = document.getElementById("view-vault");
  if (!vaultData) {
    container.innerHTML = `<div class="empty-state">Loading your Personal Vault...</div>`;
    return;
  }

  const m = vaultData.metrics || {};
  const allItems = vaultData.items || [];
  const q = vaultSearch.trim().toLowerCase();

  const items = allItems.filter((it) => {
    if (vaultFilter === "peak10" && !(!it.is_raw && it.grade >= 10)) return false;
    if (vaultFilter === "upgrade" && !it.needs_upgrade) return false;
    if (vaultFilter === "graded" && it.is_raw) return false;
    if (vaultFilter === "raw" && !it.is_raw) return false;
    if (q) {
      const hay = `${it.card_name} ${it.set_name} ${it.card_number} ${it.language} ${it.grading_company} ${it.grade_label} ${it.cert_number} ${it.notes}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  const gainColor = m.net_gain >= 0 ? "#34d399" : "#f87171";
  const gainSign = m.net_gain >= 0 ? "+" : "";

  const cardsHtml =
    items.length === 0
      ? `<div class="empty-state">No cards in your Vault match this filter. Click <strong>+ Add Card</strong> to log a card.</div>`
      : `<div class="vault-grid">
          ${items
            .map((it) => {
              const gradePill = it.is_raw
                ? `<span class="status-pill status-missing">RAW SINGLE</span>`
                : `<span class="status-pill ${it.grade >= 10 ? "status-owned" : "status-upgrade"}">${esc(it.grading_company)} ${it.grade === Math.floor(it.grade) ? it.grade : it.grade} • ${esc(it.grade_label)}</span>`;

              const marketLine =
                it.market_value != null
                  ? `<strong style="color:#fbbf24;">${fmtUsd(it.market_value)}</strong> <span style="font-size:0.7rem; color:#8b9bb4;">(${esc(it.market_source)})</span>`
                  : `<span style="color:#64748b; font-style:italic;">Unpriced (refresh in Binder)</span>`;

              const roiLine =
                it.unrealized_gain != null
                  ? `<span style="color:${it.unrealized_gain >= 0 ? "#34d399" : "#f87171"}; font-weight:700;">${it.unrealized_gain >= 0 ? "+" : ""}${fmtUsd(it.unrealized_gain)} (${it.unrealized_gain >= 0 ? "+" : ""}${it.roi_percent}%)</span>`
                  : `<span style="color:#64748b;">—</span>`;

              return `
                <article class="vault-card">
                  <div class="vault-card-img" data-inspect-key="${esc(it.catalog_key || "")}" title="${it.catalog_key ? "Click to open in Master Set" : ""}">
                    <img src="${esc(it.image_url || "/assets/card-placeholder.svg")}" onerror="this.onerror=null;this.src='/assets/card-placeholder.svg';" loading="lazy" alt="${esc(it.card_name)}" />
                  </div>
                  <div class="vault-card-body">
                    <div style="display:flex; justify-content:space-between; align-items:center; gap:6px; flex-wrap:wrap;">
                      ${gradePill}
                      <span>${langCodePill(it.language)}</span>
                    </div>

                    <div style="font-family:var(--font-serif); font-weight:700; font-size:1rem; color:#f8fafc; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
                      ${esc(it.card_name)}
                    </div>
                    <div style="font-size:0.76rem; color:#8b9bb4;">
                      ${esc(it.set_name)} • ${esc(fmtCardNum(it.card_number))} • ${esc(it.edition)}
                    </div>

                    <div style="background:rgba(0,0,0,0.3); border-radius:8px; padding:7px 9px; font-size:0.76rem; display:flex; flex-direction:column; gap:3px; margin-top:2px;">
                      <div style="display:flex; justify-content:space-between;">
                        <span style="color:#8b9bb4;">Paid:</span>
                        <span><strong>${fmtUsd(it.purchase_price)}</strong> <span style="color:#64748b;">${esc(it.purchase_date)}</span></span>
                      </div>
                      <div style="display:flex; justify-content:space-between;">
                        <span style="color:#8b9bb4;">Market:</span>
                        <span>${marketLine}</span>
                      </div>
                      <div style="display:flex; justify-content:space-between;">
                        <span style="color:#8b9bb4;">Gain / ROI:</span>
                        <span>${roiLine}</span>
                      </div>
                    </div>

                    ${
                      it.cert_number
                        ? `<div style="font-size:0.72rem; color:#94a3b8;">
                             Cert: ${it.cert_url ? `<a href="${esc(it.cert_url)}" target="_blank" rel="noopener" style="color:#38bdf8; text-decoration:none; font-weight:700;">#${esc(it.cert_number)} ↗</a>` : `#${esc(it.cert_number)}`}
                           </div>`
                        : ""
                    }

                    <div style="display:flex; gap:6px; margin-top:auto; padding-top:4px;">
                      <button class="btn btn-sm" data-edit-vault="${it.id}">✏️ Edit</button>
                      <button class="btn btn-danger btn-sm" data-del-vault="${it.id}">Delete</button>
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
          <span>My Personal Vault</span>
          <span class="hero-ratio-sub">${m.total_items} Items (${m.graded_count} Graded • ${m.raw_count} Raw)</span>
        </h1>
        <div style="display:flex; gap:8px; flex-wrap:wrap;">
          <a class="btn btn-sm" href="/api/export/vault.csv">Export Vault CSV</a>
          <button class="btn btn-primary btn-sm" id="btn-vault-add">+ Add Card to Vault</button>
        </div>
      </div>

      <div class="hero-kpis">
        <div class="kpi-tile highlight-gold">
          <div class="kpi-label">Portfolio Value</div>
          <div class="kpi-val" style="color:#fbbf24;">${fmtUsd(m.total_market_value)}</div>
          <div class="kpi-sub">${m.priced_items_count}/${m.total_items} with live market comp</div>
        </div>
        <div class="kpi-tile">
          <div class="kpi-label">Total Invested Basis</div>
          <div class="kpi-val">${fmtUsd(m.total_invested)}</div>
          <div class="kpi-sub">Recorded purchase prices</div>
        </div>
        <div class="kpi-tile highlight-emerald">
          <div class="kpi-label">Unrealized Gain / ROI</div>
          <div class="kpi-val" style="color:${gainColor};">${gainSign}${fmtUsd(m.net_gain)}</div>
          <div class="kpi-sub" style="color:${gainColor};">${gainSign}${m.roi_percent}% ROI</div>
        </div>
        <div class="kpi-tile">
          <div class="kpi-label">Peak 10s / Upgrades</div>
          <div class="kpi-val">${m.peak_10_count} <span style="font-size:0.9rem; color:#8b9bb4;">Grade 10s</span></div>
          <div class="kpi-sub">${m.upgrade_candidates} upgrade candidates (&lt;10)</div>
        </div>
      </div>
    </section>

    <div class="toolbar">
      <div class="segmented" id="vault-filter-seg">
        <button class="seg-btn ${vaultFilter === "all" ? "active" : ""}" data-vf="all">All (${allItems.length})</button>
        <button class="seg-btn ${vaultFilter === "peak10" ? "active" : ""}" data-vf="peak10">Peak 10s (${m.peak_10_count})</button>
        <button class="seg-btn ${vaultFilter === "upgrade" ? "active" : ""}" data-vf="upgrade">Upgradeable (${m.upgrade_candidates})</button>
        <button class="seg-btn ${vaultFilter === "graded" ? "active" : ""}" data-vf="graded">Graded (${m.graded_count})</button>
        <button class="seg-btn ${vaultFilter === "raw" ? "active" : ""}" data-vf="raw">Raw (${m.raw_count})</button>
      </div>
      <input id="vault-search-in" type="search" placeholder="Filter vault by card, set, cert..." value="${esc(vaultSearch)}"
             style="background:#0c101b; border:1px solid rgba(255,255,255,0.16); color:#f8fafc; border-radius:8px; padding:7px 11px; font-size:0.82rem; min-width:220px;" />
    </div>

    ${cardsHtml}
  `;

  container.querySelector("#btn-vault-add")?.addEventListener("click", () => {
    openVaultFormModal(null, catalogData?.cards || [], onChange);
  });

  container.querySelectorAll("#vault-filter-seg .seg-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      vaultFilter = btn.dataset.vf;
      renderVaultView(vaultData, catalogData, onChange);
    });
  });

  container.querySelector("#vault-search-in")?.addEventListener("input", (e) => {
    vaultSearch = e.target.value;
    const caret = e.target.selectionStart ?? vaultSearch.length;
    renderVaultView(vaultData, catalogData, onChange);
    const nextIn = container.querySelector("#vault-search-in");
    if (nextIn) {
      nextIn.focus();
      nextIn.setSelectionRange(caret, caret);
    }
  });

  container.querySelectorAll("[data-inspect-key]").forEach((el) => {
    const ck = el.dataset.inspectKey;
    if (!ck) return;
    el.addEventListener("click", () => openCardModal(ck, catalogData?.cards || []));
  });

  container.querySelectorAll("[data-edit-vault]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const item = allItems.find((x) => x.id === Number(btn.dataset.editVault));
      if (item) openVaultFormModal(item, catalogData?.cards || [], onChange);
    });
  });

  container.querySelectorAll("[data-del-vault]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = Number(btn.dataset.delVault);
      if (!confirm("Delete this card from your Personal Vault?")) return;
      try {
        await api.deleteVaultItem(id);
        showToast("Deleted card from Vault.", "ok");
        await onChange();
      } catch (err) {
        showToast(err.message, "err");
      }
    });
  });
}

function openVaultFormModal(existingItem, catalogCards, onChange) {
  const modal = document.getElementById("vault-modal");
  const isEdit = Boolean(existingItem);
  const today = new Date().toISOString().slice(0, 10);

  const graders = ["RAW", "PSA", "CGC", "BGS", "ARS", "ACE", "SGC"];
  const labels = ["Raw Single", "Gem Mint 10", "Gem Mint", "Pristine 10", "Black Label 10", "Mint 9", "Near Mint 8", "EX-MT 6", "Ungraded"];

  const curGrader = isEdit ? (existingItem.is_raw ? "RAW" : existingItem.grading_company) : "CGC";
  const curLabel = isEdit ? existingItem.grade_label : "Gem Mint 10";
  const curLabelList = labels.includes(curLabel) ? labels : [curLabel, ...labels];

  const catOptions = catalogCards
    .map(
      (c) => `<option value="${esc(c.catalog_key)}" ${existingItem?.catalog_key === c.catalog_key ? "selected" : ""}>
                ${esc(c.release_year)} • ${esc(c.card_name)} — ${esc(c.set_name)} ${esc(fmtCardNum(c.card_number))} [${esc(c.language)} / ${esc(c.edition)}]
              </option>`
    )
    .join("");

  modal.innerHTML = `
    <div class="modal-header">
      <h2 class="modal-title" style="font-size:1.25rem;">${isEdit ? "Edit Vault Card" : "Add Card to Vault"}</h2>
      <button class="btn btn-sm" id="vm-close">✕</button>
    </div>
    <form id="vm-form" style="padding:20px 22px;">
      <div class="form-grid">
        <div class="field full">
          <label>Link to Master Set Card</label>
          <select name="catalog_key" id="vm-catalog-sel">
            <option value="">-- Custom / Manual Entry --</option>
            ${catOptions}
          </select>
        </div>
        <div class="field">
          <label>Card Name*</label>
          <input name="card_name" id="vm-name" required value="${esc(existingItem?.card_name || "Vulpix")}" />
        </div>
        <div class="field">
          <label>Set / Expansion*</label>
          <input name="set_name" id="vm-set" required value="${esc(existingItem?.set_name || "")}" />
        </div>
        <div class="field">
          <label>Card Number</label>
          <input name="card_number" id="vm-num" value="${esc(existingItem?.card_number || "")}" />
        </div>
        <div class="field">
          <label>Language</label>
          <input name="language" id="vm-lang" value="${esc(existingItem?.language || "English")}" />
        </div>
        <div class="field">
          <label>Edition / Variant</label>
          <input name="edition" id="vm-ed" value="${esc(existingItem?.edition || "Unlimited")}" />
        </div>
        <div class="field">
          <label>Grader</label>
          <select name="grading_company" id="vm-grader">
            ${graders.map((g) => `<option value="${g}" ${g === curGrader ? "selected" : ""}>${g === "RAW" ? "RAW (Ungraded)" : g}</option>`).join("")}
          </select>
        </div>
        <div class="field">
          <label>Numerical Grade</label>
          <input name="grade" id="vm-grade" type="number" min="0" max="10" step="0.5" value="${isEdit ? existingItem.grade : 10}" />
        </div>
        <div class="field">
          <label>Grade Label</label>
          <select name="grade_label" id="vm-label">
            ${curLabelList.map((l) => `<option value="${esc(l)}" ${l === curLabel ? "selected" : ""}>${esc(l)}</option>`).join("")}
          </select>
        </div>
        <div class="field">
          <label>Purchase Price ($)</label>
          <input name="purchase_price" type="number" min="0" step="0.01" value="${isEdit ? existingItem.purchase_price : 0}" />
        </div>
        <div class="field">
          <label>Purchase Date</label>
          <input name="purchase_date" type="date" value="${esc(existingItem?.purchase_date || today)}" />
        </div>
        <div class="field">
          <label>Cert #</label>
          <input name="cert_number" value="${esc(existingItem?.cert_number || "")}" placeholder="e.g. 84729103" />
        </div>
        <div class="field">
          <label>Image URL</label>
          <input name="image_url" id="vm-img" value="${esc(existingItem?.image_url || "")}" />
        </div>
        <div class="field full">
          <label>Notes</label>
          <textarea name="notes" rows="2">${esc(existingItem?.notes || "")}</textarea>
        </div>
      </div>

      <div style="display:flex; justify-content:flex-end; gap:8px; margin-top:16px;">
        <button type="button" class="btn" id="vm-cancel">Cancel</button>
        <button type="submit" class="btn btn-primary">${isEdit ? "Save Changes" : "Add to Vault"}</button>
      </div>
    </form>
  `;

  modal.querySelector("#vm-close").addEventListener("click", closeVaultModal);
  modal.querySelector("#vm-cancel").addEventListener("click", closeVaultModal);

  // Autocomplete fields when picking a catalog card
  modal.querySelector("#vm-catalog-sel").addEventListener("change", (e) => {
    const picked = catalogCards.find((c) => c.catalog_key === e.target.value);
    if (!picked) return;
    modal.querySelector("#vm-name").value = picked.card_name;
    modal.querySelector("#vm-set").value = picked.set_name;
    modal.querySelector("#vm-num").value = picked.card_number;
    modal.querySelector("#vm-lang").value = picked.language;
    modal.querySelector("#vm-ed").value = picked.edition;
    modal.querySelector("#vm-img").value = picked.image_url;
  });

  modal.querySelector("#vm-grader").addEventListener("change", (e) => {
    if (e.target.value === "RAW") {
      modal.querySelector("#vm-grade").value = "0";
      modal.querySelector("#vm-label").value = "Raw Single";
    }
  });

  modal.querySelector("#vm-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const grader = String(fd.get("grading_company") || "RAW");
    const isRaw = grader === "RAW";
    const payload = {
      catalog_key: String(fd.get("catalog_key") || "") || null,
      card_name: String(fd.get("card_name") || "Vulpix"),
      set_name: String(fd.get("set_name") || ""),
      card_number: String(fd.get("card_number") || ""),
      language: String(fd.get("language") || "English"),
      edition: String(fd.get("edition") || "Unlimited"),
      is_raw: isRaw,
      grading_company: grader,
      grade: isRaw ? 0 : Number(fd.get("grade") || 0),
      grade_label: isRaw ? "Raw Single" : String(fd.get("grade_label") || "Gem Mint"),
      cert_number: String(fd.get("cert_number") || ""),
      purchase_price: Number(fd.get("purchase_price") || 0),
      purchase_date: String(fd.get("purchase_date") || today),
      image_url: String(fd.get("image_url") || ""),
      notes: String(fd.get("notes") || ""),
    };
    try {
      if (isEdit) {
        await api.updateVaultItem(existingItem.id, payload);
        showToast("Vault card updated!", "ok");
      } else {
        await api.addVaultItem(payload);
        showToast("Card added to Vault!", "ok");
      }
      closeVaultModal();
      await onChange();
    } catch (err) {
      showToast(err.message, "err");
    }
  });

  document.getElementById("vault-modal-backdrop").classList.remove("hidden");
  document.body.style.overflow = "hidden";
}
