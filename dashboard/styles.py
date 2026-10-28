"""
Custom CSS styling and HTML components for The Vulpix Vault Streamlit Dashboard.
Implements the Sleek Obsidian & Gold Luxury Collector aesthetic:
Obsidian charcoal surfaces, crisp platinum white typography, amber gold accents,
4x4 binder sheet grids, and sleek card inspection modals.
"""

from typing import Any, Optional
import textwrap
import streamlit as st


def clean_html(html_str: str) -> str:
    """Strips all leading and trailing whitespace from each line and joins into a single continuous HTML string with zero newlines, preventing any Markdown code block interpretations."""
    lines = [line.strip() for line in html_str.splitlines() if line.strip()]
    return "".join(lines)


def apply_custom_styles():
    """Injects custom CSS for the modern obsidian slate & championship gold collector interface."""
    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Caveat:wght@500;700&family=Fraunces:ital,opsz,wght@0,9..144,400..800;1,9..144,400..800&family=Playfair+Display:ital,wght@0,500..800;1,500..800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700;800&display=swap');

    /* Root Colors & Theme */
    :root {
        --bg-deep: #0a0d14;
        --bg-surface: #121622;
        --bg-surface-elevated: #181d2c;
        --bg-card: #151a27;
        --bg-card-hover: #1e2538;
        --border-subtle: rgba(255, 255, 255, 0.08);
        --border-dark: #22293a;
        --border-gold: rgba(245, 158, 11, 0.4);
        --text-white: #f8fafc;
        --text-silver: #e2e8f0;
        --text-slate: #94a3b8;
        --text-muted: #64748b;
        --accent-gold: #f59e0b;
        --accent-amber: #fbbf24;
        --accent-emerald: #10b981;
        --accent-emerald-subtle: rgba(16, 185, 129, 0.15);
        --accent-rose: #ef4444;
        --accent-cyan: #38bdf8;
        --accent-purple: #a855f7;
    }

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        color: var(--text-white);
    }

    /* Streamlit Main App & Sidebar Backgrounds */
    .stApp {
        background-color: var(--bg-deep) !important;
        color: var(--text-white) !important;
    }
    section[data-testid="stSidebar"] {
        background-color: #07090e !important;
        border-right: 1px solid var(--border-dark) !important;
    }
    section[data-testid="stSidebar"] [class*="st-"] {
        color: var(--text-silver);
    }

    /* Hero Banner */
    .vault-header {
        background: linear-gradient(135deg, #111522 0%, #171d2e 60%, #1c2338 100%);
        border: 1px solid rgba(245, 158, 11, 0.35);
        border-radius: 16px;
        padding: 22px 28px;
        margin-bottom: 22px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .vault-title {
        font-family: 'Fraunces', 'Plus Jakarta Sans', Georgia, serif;
        font-size: 2.2rem;
        font-weight: 700;
        color: var(--text-white);
        margin: 0;
        letter-spacing: -0.5px;
    }
    .vault-subtitle {
        color: var(--text-slate);
        font-size: 0.92rem;
        margin-top: 4px;
    }

    /* =========================================================
       Master Set Collection Banner (Obsidian & Gold)
       ========================================================= */
    .cottage-hero {
        background: linear-gradient(180deg, #131724 0%, #0f131f 100%);
        border: 1px solid #232a3d;
        border-radius: 18px;
        padding: 28px 32px 24px 32px;
        margin-bottom: 24px;
        box-shadow: 0 14px 40px rgba(0, 0, 0, 0.5);
        text-align: center;
    }
    .cottage-hero-title {
        font-family: 'Fraunces', 'Plus Jakarta Sans', Georgia, serif;
        font-size: 2.4rem;
        font-weight: 700;
        color: var(--text-white);
        margin: 0 0 22px 0;
        letter-spacing: -0.5px;
    }
    .cottage-stats-grid {
        display: grid;
        grid-template-columns: repeat(6, 1fr);
        gap: 14px;
        margin-bottom: 22px;
        padding-bottom: 20px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }
    @media (max-width: 900px) {
        .cottage-stats-grid {
            grid-template-columns: repeat(3, 1fr);
        }
    }
    .cottage-stat-item {
        text-align: center;
    }
    .cottage-stat-label {
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 1.2px;
        text-transform: uppercase;
        color: #94a3b8;
        margin-bottom: 4px;
    }
    .cottage-stat-val {
        font-family: 'Fraunces', 'Plus Jakarta Sans', Georgia, serif;
        font-size: 1.15rem;
        font-weight: 600;
        color: var(--text-white);
    }
    .cottage-oval-banner {
        font-family: 'Fraunces', 'Plus Jakarta Sans', Georgia, serif;
        font-size: 1.35rem;
        color: var(--text-white);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 14px;
        margin-top: 6px;
        flex-wrap: wrap;
    }
    .cottage-oval-pill {
        border: 2px solid #f59e0b;
        border-radius: 9999px;
        padding: 5px 22px;
        color: #fbbf24;
        font-weight: 700;
        font-style: italic;
        display: inline-block;
        background: rgba(245, 158, 11, 0.12);
        box-shadow: 0 0 16px rgba(245, 158, 11, 0.25);
    }

    /* Metric Cards */
    .kpi-card {
        background: var(--bg-surface);
        border: 1px solid var(--border-dark);
        border-radius: 14px;
        padding: 16px 18px;
        box-shadow: 0 6px 18px rgba(0,0,0,0.3);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        border-color: var(--accent-gold);
    }
    .kpi-label {
        color: var(--text-slate);
        font-size: 0.76rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }
    .kpi-value {
        font-family: 'Fraunces', 'Plus Jakarta Sans', Georgia, serif;
        font-size: 1.7rem;
        font-weight: 700;
        color: var(--text-white);
        margin: 4px 0;
    }
    .kpi-delta-pos {
        color: #34d399;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .kpi-delta-neg {
        color: #f87171;
        font-size: 0.85rem;
        font-weight: 600;
    }

    /* Master Set Progress Box */
    .master-box {
        background: var(--bg-surface);
        border: 1px solid var(--border-dark);
        border-radius: 14px;
        padding: 20px 24px;
        margin-bottom: 22px;
        box-shadow: 0 6px 20px rgba(0,0,0,0.3);
    }
    .progress-bar-bg {
        background: #1a202f;
        border-radius: 10px;
        height: 14px;
        width: 100%;
        overflow: hidden;
        margin: 12px 0;
        border: 1px solid rgba(255, 255, 255, 0.05);
    }
    .progress-bar-fill {
        background: linear-gradient(90deg, #10b981 0%, #34d399 50%, #f59e0b 100%);
        height: 100%;
        border-radius: 10px;
        transition: width 0.6s ease;
        box-shadow: 0 0 12px rgba(16, 185, 129, 0.4);
    }

    /* =========================================================
       4x4 Binder Sheet & Card Frame
       ========================================================= */
    .binder-page-container {
        background: #0f121a;
        border: 1px solid #1f2637;
        border-radius: 20px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: inset 0 2px 14px rgba(0,0,0,0.5), 0 16px 40px rgba(0,0,0,0.55);
    }
    .binder-card-sleeve {
        background: #151924;
        border: 1px solid #232a3d;
        border-radius: 14px;
        padding: 14px;
        text-align: center;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.4);
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .binder-card-sleeve:hover {
        transform: translateY(-4px) scale(1.02);
        border-color: #f59e0b;
        box-shadow: 0 12px 30px rgba(0, 0, 0, 0.6), 0 0 16px rgba(245, 158, 11, 0.3);
    }
    .binder-card-sleeve.owned-card {
        border-color: rgba(16, 185, 129, 0.5);
        background: linear-gradient(180deg, #151b27 0%, #131924 100%);
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.4), 0 0 12px rgba(16, 185, 129, 0.15);
    }
    .binder-card-img {
        width: 100%;
        aspect-ratio: 2.5 / 3.5;
        object-fit: contain;
        border-radius: 8px;
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.5);
        transition: transform 0.2s ease;
        cursor: pointer;
        display: block;
        margin: 0 auto;
    }
    .binder-card-img:hover {
        transform: scale(1.03);
    }

    /* =========================================================
       Card Detail Dialog / Inspection Modal
       ========================================================= */
    .sketchbook-modal, .vault-modal {
        background: #111522 !important;
        border-radius: 18px !important;
        padding: 24px 28px !important;
        color: #f8fafc !important;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.8) !important;
        border: 1px solid #283248 !important;
    }
    .sketchbook-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 18px;
        padding-bottom: 12px;
        border-bottom: 1px solid #22293a;
    }
    .sketchbook-title {
        font-family: 'Fraunces', 'Plus Jakarta Sans', Georgia, serif;
        font-style: italic;
        font-size: 2.2rem;
        font-weight: 700;
        color: #f8fafc;
        margin: 0;
        text-align: center;
    }
    .sketchbook-subtitle {
        font-size: 0.74rem;
        font-weight: 800;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        color: #f59e0b;
        text-align: center;
        margin-top: 2px;
    }
    .sketchbook-annot-label {
        font-size: 0.68rem;
        font-weight: 800;
        letter-spacing: 1.2px;
        text-transform: uppercase;
        color: #94a3b8;
        margin-bottom: 2px;
    }
    .sketchbook-annot-val {
        font-family: 'Fraunces', 'Plus Jakarta Sans', Georgia, serif;
        font-style: italic;
        font-size: 1.15rem;
        font-weight: 700;
        color: #f8fafc;
        margin-bottom: 14px;
    }
    .sketchbook-note-card {
        background: #161c2c;
        border: 1px solid #283248;
        border-radius: 10px;
        padding: 12px 14px;
        color: #cbd5e1;
        font-size: 0.88rem;
        line-height: 1.5;
        margin-top: 4px;
    }
    .sketchbook-footer-bar {
        background: #161c2a;
        border: 1px solid #252e42;
        border-radius: 12px;
        padding: 16px 22px;
        margin-top: 22px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        color: #f8fafc;
        flex-wrap: wrap;
        gap: 12px;
    }

    /* Legacy Slab Boxes */
    .slab-box {
        background: var(--bg-surface);
        border: 1px solid var(--border-dark);
        border-radius: 12px;
        padding: 14px;
        margin-bottom: 16px;
        transition: all 0.2s ease;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.3);
    }
    .slab-box:hover {
        border-color: var(--accent-gold);
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.4);
    }

    /* Badges */
    .badge-psa {
        background: rgba(239, 68, 68, 0.15);
        border: 1px solid #ef4444;
        color: #fca5a5;
        padding: 2px 8px;
        border-radius: 12px;
        font-weight: 800;
        font-size: 0.75rem;
        letter-spacing: 0.5px;
        display: inline-block;
    }
    .badge-cgc {
        background: rgba(59, 130, 246, 0.15);
        border: 1px solid #3b82f6;
        color: #93c5fd;
        padding: 2px 8px;
        border-radius: 12px;
        font-weight: 800;
        font-size: 0.75rem;
        letter-spacing: 0.5px;
        display: inline-block;
    }
    .badge-bgs {
        background: rgba(245, 158, 11, 0.15);
        border: 1px solid #f59e0b;
        color: #fde047;
        padding: 2px 8px;
        border-radius: 12px;
        font-weight: 800;
        font-size: 0.75rem;
        letter-spacing: 0.5px;
        display: inline-block;
    }
    .badge-pristine {
        background: linear-gradient(135deg, rgba(6, 182, 212, 0.3), rgba(59, 130, 246, 0.3));
        border: 1px solid #06b6d4;
        color: #a5f3fc;
        padding: 2px 8px;
        border-radius: 12px;
        font-weight: 800;
        font-size: 0.75rem;
        letter-spacing: 0.5px;
        display: inline-block;
        box-shadow: 0 0 10px rgba(6, 182, 212, 0.3);
    }
    .badge-black-label {
        background: linear-gradient(135deg, #09090b, #18181b);
        border: 1px solid #eab308;
        color: #fef08a;
        padding: 2px 8px;
        border-radius: 12px;
        font-weight: 800;
        font-size: 0.75rem;
        letter-spacing: 0.8px;
        display: inline-block;
        box-shadow: 0 0 12px rgba(234, 179, 8, 0.35);
    }
    .badge-raw {
        background: rgba(148, 163, 184, 0.15);
        border: 1px solid #94a3b8;
        color: #cbd5e1;
        padding: 2px 8px;
        border-radius: 12px;
        font-weight: 800;
        font-size: 0.75rem;
        letter-spacing: 0.5px;
        display: inline-block;
    }
    .badge-pop-1 {
        background: linear-gradient(135deg, rgba(234, 179, 8, 0.35), rgba(217, 119, 6, 0.35));
        border: 1px solid #f59e0b;
        color: #fef08a;
        padding: 2px 8px;
        border-radius: 12px;
        font-weight: 800;
        font-size: 0.72rem;
        display: inline-block;
    }
    .badge-low-pop {
        background: rgba(16, 185, 129, 0.18);
        border: 1px solid #10b981;
        color: #6ee7b7;
        padding: 2px 8px;
        border-radius: 12px;
        font-weight: 800;
        font-size: 0.72rem;
        display: inline-block;
    }
    .badge-error {
        background: rgba(239, 68, 68, 0.2);
        border: 1px solid #ef4444;
        color: #fca5a5;
        padding: 2px 8px;
        border-radius: 12px;
        font-weight: 800;
        font-size: 0.72rem;
        display: inline-block;
    }

    /* Buttons & Inputs Styling */
    button[kind="primary"] {
        background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%) !important;
        border: 1px solid #fbbf24 !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 12px rgba(245, 158, 11, 0.3) !important;
    }
    button[kind="primary"]:hover {
        background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%) !important;
        box-shadow: 0 6px 18px rgba(245, 158, 11, 0.45) !important;
    }
    button[kind="secondary"] {
        background-color: var(--bg-surface) !important;
        border: 1px solid var(--border-dark) !important;
        color: var(--text-white) !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
    }
    button[kind="secondary"]:hover {
        border-color: var(--accent-gold) !important;
        color: #ffffff !important;
    }

    /* Link Buttons */
    .btn-ebay {
        display: inline-block;
        background: linear-gradient(135deg, #0284c7, #0369a1);
        color: #ffffff !important;
        text-decoration: none;
        padding: 6px 14px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.8rem;
        transition: all 0.2s ease;
        border: 1px solid #38bdf8;
    }
    .btn-ebay:hover {
        opacity: 0.92;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(2, 132, 199, 0.4);
    }
    .btn-tcg {
        display: inline-block;
        background: linear-gradient(135deg, #d97706, #b45309);
        color: #ffffff !important;
        text-decoration: none;
        padding: 6px 14px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.8rem;
        transition: all 0.2s ease;
        border: 1px solid #f59e0b;
    }
    .btn-tcg:hover {
        opacity: 0.92;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(217, 119, 6, 0.4);
    }
    .btn-pc {
        display: inline-block;
        background: #1e2538;
        color: var(--text-white) !important;
        text-decoration: none;
        padding: 6px 14px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.8rem;
        transition: all 0.2s ease;
        border: 1px solid #334155;
    }
    .btn-pc:hover {
        border-color: #94a3b8;
        transform: translateY(-1px);
    }
    </style>
    """
    st.markdown(clean_html(css), unsafe_allow_html=True)


def render_header():
    """Renders the sleek obsidian header with gold accents."""
    html = """
    <div class="vault-header">
        <div>
            <h1 class="vault-title">🦊 The Vulpix Vault</h1>
            <div class="vault-subtitle">Premier Pokémon Master Set & Investment Portfolio Management System</div>
        </div>
        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <span style="background: rgba(16, 185, 129, 0.15); border: 1px solid #10b981; color: #6ee7b7; padding: 4px 12px; border-radius: 20px; font-size: 0.78rem; font-weight: 700; display: inline-flex; align-items: center; gap: 6px;">
                🟢 Vault Online
            </span>
            <span style="background: rgba(245, 158, 11, 0.15); border: 1px solid #f59e0b; color: #fbbf24; padding: 4px 12px; border-radius: 20px; font-size: 0.78rem; font-weight: 700; display: inline-flex; align-items: center; gap: 6px;">
                💎 Proxmox Production
            </span>
        </div>
    </div>
    """
    st.markdown(clean_html(html), unsafe_allow_html=True)


def get_edition_badge_html(edition: str) -> str:
    """Returns styled HTML badge for 1st Edition, Shadowless, Rainbow Rare, Art Rare, SAR, etc."""
    ed_lower = str(edition).lower()
    if "1st" in ed_lower or "first" in ed_lower:
        return '<span style="background: linear-gradient(135deg, rgba(245, 158, 11, 0.25), rgba(217, 119, 6, 0.25)); border: 1px solid #f59e0b; color: #fbbf24; padding: 2px 8px; border-radius: 12px; font-weight: 800; font-size: 0.72rem; letter-spacing: 0.5px;">🥇 1ST EDITION</span>'
    if "rainbow" in ed_lower or "hr" in ed_lower:
        return '<span style="background: linear-gradient(135deg, rgba(236,72,153,0.3), rgba(59,130,246,0.3), rgba(234,179,8,0.3)); border: 1px solid #ec4899; color: #fbcfe8; padding: 2px 8px; border-radius: 12px; font-weight: 800; font-size: 0.72rem;">🌈 RAINBOW RARE</span>'
    if "special art rare" in ed_lower or "sar" in ed_lower:
        return '<span style="background: linear-gradient(135deg, rgba(245,158,11,0.3), rgba(168,85,247,0.3)); border: 1px solid #a855f7; color: #e9d5ff; padding: 2px 8px; border-radius: 12px; font-weight: 800; font-size: 0.72rem;">✨ SAR</span>'
    if "art rare" in ed_lower or "ar" == ed_lower.strip():
        return '<span style="background: rgba(168, 85, 247, 0.2); border: 1px solid #a855f7; color: #c084fc; padding: 2px 8px; border-radius: 12px; font-weight: 800; font-size: 0.72rem;">🎨 ART RARE</span>'
    if "illustration rare" in ed_lower or "ir" in ed_lower:
        return '<span style="background: rgba(59, 130, 246, 0.2); border: 1px solid #3b82f6; color: #93c5fd; padding: 2px 8px; border-radius: 12px; font-weight: 800; font-size: 0.72rem;">🖼️ IR</span>'
    if "shiny" in ed_lower or "vault" in ed_lower:
        return '<span style="background: linear-gradient(135deg, rgba(56,189,248,0.25), rgba(234,179,8,0.25)); border: 1px solid #38bdf8; color: #bae6fd; padding: 2px 8px; border-radius: 12px; font-weight: 800; font-size: 0.72rem;">⭐ SHINY</span>'
    if "shadowless" in ed_lower:
        return '<span style="background: rgba(168, 85, 247, 0.2); border: 1px solid #a855f7; color: #c084fc; padding: 2px 8px; border-radius: 12px; font-weight: 700; font-size: 0.72rem;">SHADOWLESS</span>'
    if "reverse" in ed_lower:
        return '<span style="background: rgba(59, 130, 246, 0.2); border: 1px solid #3b82f6; color: #60a5fa; padding: 2px 8px; border-radius: 12px; font-weight: 700; font-size: 0.72rem;">REVERSE HOLO</span>'
    if "promo" in ed_lower:
        return '<span style="background: rgba(236, 72, 153, 0.2); border: 1px solid #ec4899; color: #f472b6; padding: 2px 8px; border-radius: 12px; font-weight: 700; font-size: 0.72rem;">PROMO</span>'
    if "playing" in ed_lower:
        return '<span style="background: rgba(234, 179, 8, 0.2); border: 1px solid #eab308; color: #fef08a; padding: 2px 8px; border-radius: 12px; font-weight: 700; font-size: 0.72rem;">🃏 PLAYING CARD</span>'
    if "4th print" in ed_lower or "1999-2000" in ed_lower:
        return '<span style="background: rgba(20, 184, 166, 0.2); border: 1px solid #14b8a6; color: #2dd4bf; padding: 2px 8px; border-radius: 12px; font-weight: 700; font-size: 0.72rem;">UK / 4TH PRINT</span>'
    return ""


def get_pop_badge_html(pop_grade10: int, pop_pristine10: int = 0) -> str:
    """Returns styled HTML badge for low-pop / ultra-rare population counts."""
    if pop_grade10 == 1 or (pop_pristine10 == 1 and pop_grade10 <= 3):
        return '<span class="badge-pop-1">👑 POP 1 OF A KIND</span>'
    if 1 < pop_grade10 <= 15:
        return f'<span class="badge-low-pop">💎 ULTRA LOW POP ({pop_grade10})</span>'
    if 15 < pop_grade10 <= 100:
        return f'<span class="badge-low-pop" style="background: rgba(59, 130, 246, 0.15); border-color: #3b82f6; color: #60a5fa;">POP {pop_grade10}</span>'
    return ""


def get_grading_badge_html(company: str, grade: Any, grade_label: str = "Gem Mint", is_raw: int = 0) -> str:
    """Returns styled HTML badge distinguishing Pristine 10, Black Label 10, Gem Mint, and Raw singles."""
    if is_raw == 1 or str(company).upper() == "RAW":
        return '<span class="badge-raw">RAW SINGLE</span>'

    lbl_upper = str(grade_label).upper()
    if "BLACK LABEL" in lbl_upper:
        return '<span class="badge-black-label">★ BGS BLACK LABEL 10 ★</span>'
    if "PRISTINE" in lbl_upper:
        co = str(company).upper()
        return f'<span class="badge-pristine">💎 {co} PRISTINE 10</span>'

    co_upper = str(company).upper()
    if "PSA" in co_upper:
        css = "badge-psa"
    elif "CGC" in co_upper:
        css = "badge-cgc"
    elif "BGS" in co_upper or "BECKETT" in co_upper:
        css = "badge-bgs"
    else:
        css = "badge-raw"

    grade_display = int(grade) if grade and grade == int(grade) else (grade or "10")
    return f'<span class="{css}">{co_upper} {grade_display}</span>'
