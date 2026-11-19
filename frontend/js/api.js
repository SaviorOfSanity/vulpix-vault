/** Typed API client for The Vulpix Vault v2 FastAPI backend. */

async function request(url, options = {}) {
  const opts = {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  };
  const resp = await fetch(url, opts);
  const text = await resp.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { detail: text };
  }
  if (!resp.ok) {
    throw new Error(data?.detail || `HTTP ${resp.status}`);
  }
  return data;
}

export const api = {
  getHealth: () => request("/api/health"),
  getCatalog: () => request("/api/catalog"),
  getVault: () => request("/api/vault"),

  addVaultItem: (payload) =>
    request("/api/vault", { method: "POST", body: JSON.stringify(payload) }),
  updateVaultItem: (id, payload) =>
    request(`/api/vault/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteVaultItem: (id) =>
    request(`/api/vault/${id}`, { method: "DELETE" }),

  refreshCardPrice: (catalogKey) =>
    request(`/api/catalog/${encodeURIComponent(catalogKey)}/refresh-price`, { method: "POST" }),
  overrideCardPrice: (catalogKey, payload) =>
    request(`/api/catalog/${encodeURIComponent(catalogKey)}/price`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  addCustomCard: (payload) =>
    request("/api/catalog/custom", { method: "POST", body: JSON.stringify(payload) }),

  getSyncStatus: () => request("/api/sync/status"),
  startTcgdexSync: (languages = null) =>
    request("/api/sync/tcgdex", { method: "POST", body: JSON.stringify({ languages }) }),
  startPriceSync: (onlyUnpriced = true, limit = null) =>
    request("/api/sync/prices", {
      method: "POST",
      body: JSON.stringify({ only_unpriced: onlyUnpriced, limit }),
    }),
  startImageCache: () => request("/api/sync/cache-images", { method: "POST" }),
  startPokecottageSync: () => request("/api/sync/pokecottage", { method: "POST" }),
};
