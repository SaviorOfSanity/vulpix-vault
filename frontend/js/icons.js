/**
 * Handcrafted inline SVG graphical variant/finish badges & language code badges.
 * Eliminates raw text variant notes and makes every print variation unmistakable at a glance.
 */

import { esc } from "./utils.js";

const LANG_CODES = {
  "English": "EN",
  "Japanese": "JA",
  "S. Chinese": "ZH-CN",
  "T. Chinese": "ZH-TW",
  "German": "DE",
  "French": "FR",
  "Italian": "IT",
  "Spanish": "ES",
  "Portuguese": "PT",
  "Dutch": "NL",
  "Korean": "KO",
  "Indonesian": "ID",
  "Thai": "TH",
  "Polish": "PL",
};

export function langCodePill(language) {
  const code = LANG_CODES[language] || String(language || "EN").slice(0, 2).toUpperCase();
  return `<span class="lang-code-pill" title="${esc(language)}">${esc(code)}</span>`;
}

const VARIANT_SVGS = {
  "1st_edition": `<svg viewBox="0 0 20 20" width="14" height="14" fill="none">
    <circle cx="10" cy="10" r="8.5" fill="rgba(245,158,11,0.25)" stroke="#fbbf24" stroke-width="1.6"/>
    <text x="10" y="13.8" text-anchor="middle" font-size="10.5" font-weight="900" fill="#fef08a" font-family="sans-serif">1</text>
  </svg>`,

  "shadowless": `<svg viewBox="0 0 20 20" width="14" height="14" fill="none">
    <rect x="3.5" y="2.5" width="13" height="15" rx="2" stroke="#d8b4fe" stroke-width="1.6" stroke-dasharray="2.5 2"/>
    <rect x="6" y="5" width="8" height="6" rx="1" fill="rgba(216,180,254,0.3)"/>
  </svg>`,

  "4th_print": `<svg viewBox="0 0 20 20" width="14" height="14" fill="none">
    <circle cx="10" cy="10" r="8" stroke="#5eead4" stroke-width="1.5"/>
    <text x="10" y="13" text-anchor="middle" font-size="7.5" font-weight="800" fill="#5eead4" font-family="sans-serif">99</text>
  </svg>`,

  "w_stamp": `<svg viewBox="0 0 20 20" width="14" height="14" fill="none">
    <polygon points="10,1.5 18,6 18,14 10,18.5 2,14 2,6" fill="rgba(245,158,11,0.3)" stroke="#fde047" stroke-width="1.5"/>
    <text x="10" y="13.4" text-anchor="middle" font-size="9.5" font-weight="900" fill="#fef08a" font-family="serif">W</text>
  </svg>`,

  "no_rarity": `<svg viewBox="0 0 20 20" width="14" height="14" fill="none">
    <circle cx="10" cy="10" r="7" stroke="#fb923c" stroke-width="1.7"/>
    <line x1="4.8" y1="15.2" x2="15.2" y2="4.8" stroke="#fb923c" stroke-width="1.8" stroke-linecap="round"/>
  </svg>`,

  "master_ball": `<svg viewBox="0 0 20 20" width="14" height="14" fill="none">
    <circle cx="10" cy="10" r="8" stroke="#e879f9" stroke-width="1.5"/>
    <path d="M2 10H18" stroke="#e879f9" stroke-width="1.5"/>
    <path d="M2.4 9.2A8 8 0 0 1 17.6 9.2Z" fill="rgba(192,132,252,0.5)"/>
    <circle cx="10" cy="10" r="2.4" fill="#131927" stroke="#f5d0fe" stroke-width="1.5"/>
    <text x="10" y="7.5" text-anchor="middle" font-size="6.5" font-weight="900" fill="#fdf4ff" font-family="sans-serif">M</text>
  </svg>`,

  "poke_ball": `<svg viewBox="0 0 20 20" width="14" height="14" fill="none">
    <circle cx="10" cy="10" r="8" stroke="#f87171" stroke-width="1.5"/>
    <path d="M2.4 9.2A8 8 0 0 1 17.6 9.2Z" fill="rgba(239,68,68,0.5)"/>
    <path d="M2 10H18" stroke="#f87171" stroke-width="1.5"/>
    <circle cx="10" cy="10" r="2.4" fill="#131927" stroke="#fecaca" stroke-width="1.5"/>
  </svg>`,

  "reverse_holo": `<svg viewBox="0 0 20 20" width="14" height="14" fill="none">
    <path d="M10 2L12.2 7.8L18 10L12.2 12.2L10 18L7.8 12.2L2 10L7.8 7.8L10 2Z" fill="rgba(56,189,248,0.35)" stroke="#38bdf8" stroke-width="1.4"/>
  </svg>`,

  "holo": `<svg viewBox="0 0 20 20" width="14" height="14" fill="none">
    <path d="M10 1.8L12.3 7.1L18 7.7L13.6 11.4L14.9 17.1L10 14.1L5.1 17.1L6.4 11.4L2 7.7L7.7 7.1L10 1.8Z" fill="rgba(250,204,21,0.35)" stroke="#fde047" stroke-width="1.4"/>
  </svg>`,

  "rainbow": `<svg viewBox="0 0 20 20" width="14" height="14" fill="none">
    <path d="M3 14A7 7 0 0 1 17 14" stroke="#ec4899" stroke-width="2" stroke-linecap="round"/>
    <path d="M5.5 14A4.5 4.5 0 0 1 14.5 14" stroke="#38bdf8" stroke-width="1.8" stroke-linecap="round"/>
    <path d="M8 14A2 2 0 0 1 12 14" stroke="#facc15" stroke-width="1.6" stroke-linecap="round"/>
  </svg>`,

  "art_rare": `<svg viewBox="0 0 20 20" width="14" height="14" fill="none">
    <rect x="2.5" y="2.5" width="15" height="15" rx="2.5" stroke="#c4b5fd" stroke-width="1.5"/>
    <path d="M5 14L8.5 9.5L11.2 12.5L13.5 10L16 14" stroke="#a78bfa" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
    <circle cx="13.2" cy="6.8" r="1.4" fill="#fde047"/>
  </svg>`,

  "error": `<svg viewBox="0 0 20 20" width="14" height="14" fill="none">
    <path d="M10 2.5L18.2 16.8H1.8L10 2.5Z" fill="rgba(239,68,68,0.28)" stroke="#f87171" stroke-width="1.6" stroke-linejoin="round"/>
    <line x1="10" y1="7.5" x2="10" y2="11.8" stroke="#fecaca" stroke-width="1.8" stroke-linecap="round"/>
    <circle cx="10" cy="14.3" r="1" fill="#fecaca"/>
  </svg>`,

  "promo": `<svg viewBox="0 0 20 20" width="14" height="14" fill="none">
    <circle cx="10" cy="10" r="7.5" fill="rgba(236,72,153,0.22)" stroke="#f472b6" stroke-width="1.5"/>
    <path d="M10 5.5L11.4 8.6L14.8 9L12.2 11.2L13 14.5L10 12.8L7 14.5L7.8 11.2L5.2 9L8.6 8.6L10 5.5Z" fill="#fbcfe8"/>
  </svg>`,

  "stamp": `<svg viewBox="0 0 20 20" width="14" height="14" fill="none">
    <rect x="3" y="4" width="14" height="12" rx="2.5" fill="rgba(14,165,233,0.2)" stroke="#38bdf8" stroke-width="1.5"/>
    <circle cx="10" cy="10" r="3" stroke="#7dd3fc" stroke-width="1.4"/>
  </svg>`,

  "playing_card": `<svg viewBox="0 0 20 20" width="14" height="14" fill="none">
    <path d="M10 2.5L16 10L10 17.5L4 10L10 2.5Z" fill="rgba(250,204,21,0.3)" stroke="#fde047" stroke-width="1.5"/>
  </svg>`,

  "unlimited": `<svg viewBox="0 0 20 20" width="14" height="14" fill="none">
    <rect x="4" y="2.5" width="12" height="15" rx="2" stroke="#94a3b8" stroke-width="1.5"/>
    <line x1="7" y1="13.5" x2="13" y2="13.5" stroke="#64748b" stroke-width="1.4" stroke-linecap="round"/>
  </svg>`,
};

export function variantBadgeHtml(variantKey, editionLabel) {
  const vk = VARIANT_SVGS[variantKey] ? variantKey : "unlimited";
  const svg = VARIANT_SVGS[vk];
  const label = editionLabel || "Unlimited";
  return `<span class="variant-badge vb-${vk}" title="${esc(label)}">${svg}<span>${esc(label)}</span></span>`;
}
