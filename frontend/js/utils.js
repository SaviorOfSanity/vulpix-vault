/** Safe escaping, currency formatting, and auction bid calculator helpers. */

export function esc(val) {
  return String(val ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function fmtUsd(val, fallback = "—") {
  if (val === null || val === undefined || Number.isNaN(Number(val))) return fallback;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number(val));
}

export function fmtCardNum(num) {
  const s = String(num || "").trim();
  if (!s || s.toLowerCase() === "no number") return "Unnumbered";
  if (s.startsWith("#") || s.startsWith("No.")) return s;
  return `#${s}`;
}

/**
 * Computes net max-bid targets for an eBay auction after subtracting shipping.
 */
export function computeBidTargets(marketValue, shipping = 0) {
  const mv = Number(marketValue || 0);
  const ship = Math.max(0, Number(shipping || 0));
  if (mv <= 0) {
    return { snipe: null, good: null, fair: null };
  }
  return {
    snipe: Math.max(0.99, Math.round((mv * 0.70 - ship) * 100) / 100),
    good: Math.max(0.99, Math.round((mv * 0.85 - ship) * 100) / 100),
    fair: Math.max(0.99, Math.round((mv - ship) * 100) / 100),
  };
}

export function showToast(message, type = "info") {
  const root = document.getElementById("toast-root");
  if (!root) return;
  const el = document.createElement("div");
  el.className = `toast ${type === "ok" ? "toast-ok" : type === "err" ? "toast-err" : ""}`;
  el.textContent = message;
  root.appendChild(el);
  setTimeout(() => {
    el.style.opacity = "0";
    el.style.transition = "opacity 0.25s";
    setTimeout(() => el.remove(), 260);
  }, 3600);
}
