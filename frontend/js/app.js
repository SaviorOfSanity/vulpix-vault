/**
 * Application entrypoint — state store, tab navigation, instant '/' auction search, and live sync polling.
 */

import { api } from "./api.js";
import { binderFilters, renderBinderView } from "./binder.js";
import { initModal, updateModalList } from "./modal.js";
import { renderSyncView, updateSyncJobCards } from "./sync.js";
import { esc, showToast } from "./utils.js";
import { initVaultModal, renderVaultView } from "./vault.js";

const state = {
  activeTab: "binder",
  catalog: null,
  vault: null,
  health: null,
  syncState: null,
  pollTimer: null,
};

function switchTab(tab) {
  state.activeTab = tab;
  document.querySelectorAll(".nav-tab").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });
  document.querySelectorAll(".view-section").forEach((sec) => {
    sec.classList.toggle("active", sec.id === `view-${tab}`);
  });
  renderActiveView();
}

function updateTopBadges() {
  const s = state.catalog?.summary;
  const vm = state.vault?.metrics;
  const ownedPill = document.getElementById("nav-owned-pill");
  const vaultPill = document.getElementById("nav-vault-pill");
  if (ownedPill && s) ownedPill.textContent = `${s.unique_owned}/${s.unique_total}`;
  if (vaultPill && vm) vaultPill.textContent = String(vm.total_items);
}

function renderActiveView() {
  updateTopBadges();
  if (state.activeTab === "binder") {
    renderBinderView(state.catalog, renderActiveView);
  } else if (state.activeTab === "vault") {
    renderVaultView(state.vault, state.catalog, refreshAllData);
  } else if (state.activeTab === "sync") {
    renderSyncView(state.health, state.syncState, startSyncPolling, refreshAllData);
  }
}

async function refreshAllData() {
  try {
    const [catalog, vault, health, syncState] = await Promise.all([
      api.getCatalog(),
      api.getVault(),
      api.getHealth(),
      api.getSyncStatus(),
    ]);
    state.catalog = catalog;
    state.vault = vault;
    state.health = health;
    state.syncState = syncState;
    renderActiveView();
    updateModalList(catalog.cards || []);
    updateSyncBanner();
  } catch (err) {
    showToast(`Failed to load data: ${err.message}`, "err");
  }
}

function updateSyncBanner() {
  const banner = document.getElementById("sync-banner");
  const activeJob = Object.values(state.syncState || {}).find((j) => j.running);
  if (activeJob) {
    const pct = activeJob.total > 0 ? Math.round((activeJob.progress / activeJob.total) * 100) : 0;
    banner.innerHTML = `<span>⚡ <strong>Background Sync Active:</strong> ${esc(activeJob.message)} (${pct}%)</span>`;
    banner.classList.remove("hidden");
  } else {
    banner.classList.add("hidden");
  }
}

function startSyncPolling() {
  if (state.pollTimer) clearInterval(state.pollTimer);
  const tick = async () => {
    try {
      const prevRunning = Object.values(state.syncState || {}).some((j) => j.running);
      state.syncState = await api.getSyncStatus();
      const nowRunning = Object.values(state.syncState || {}).some((j) => j.running);
      updateSyncBanner();
      if (state.activeTab === "sync") {
        updateSyncJobCards(state.syncState);
      }
      if (prevRunning && !nowRunning) {
        clearInterval(state.pollTimer);
        state.pollTimer = null;
        await refreshAllData();
        showToast("Sync job finished and catalog updated!", "ok");
      } else if (!nowRunning) {
        clearInterval(state.pollTimer);
        state.pollTimer = null;
      }
    } catch {
      clearInterval(state.pollTimer);
      state.pollTimer = null;
    }
  };
  tick();
  state.pollTimer = setInterval(tick, 1800);
}

// Boot
document.addEventListener("DOMContentLoaded", async () => {
  initModal({ onChange: refreshAllData });
  initVaultModal();

  document.getElementById("brand-home")?.addEventListener("click", () => switchTab("binder"));
  document.querySelectorAll(".nav-tab").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  // Global instant auction search bar
  const searchIn = document.getElementById("global-search");
  searchIn?.addEventListener("input", (e) => {
    binderFilters.search = e.target.value;
    binderFilters.page = 1;
    if (state.activeTab !== "binder") {
      switchTab("binder");
    } else {
      renderActiveView();
    }
  });

  // "/" shortcut focuses instant auction search immediately
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) {
      e.preventDefault();
      searchIn?.focus();
      searchIn?.select();
    }
  });

  await refreshAllData();
  if (Object.values(state.syncState || {}).some((j) => j.running)) {
    startSyncPolling();
  }
});
