"""
Custom CSS styling and HTML components for The Vulpix Vault Streamlit Dashboard.
Includes special grade badges (Pristine 10, Black Label 10), 1st Edition badges,
Error indicators, Population (POP) badges, PriceCharting benchmarks, and Master Set progress tracking.
"""

from typing import Any, Optional
import streamlit as st


def apply_custom_styles():
    """Injects custom CSS for modern Pokémon Master Set & slab interface."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap');

        html, body, [class*="css"] {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        /* Hero Banner */
        .vault-header {
            background: linear-gradient(135deg, #1c1d24 0%, #2b1b1f 50%, #171c26 100%);
            border: 1px solid rgba(255, 94, 54, 0.25);
            border-radius: 16px;
            padding: 22px 28px;
            margin-bottom: 20px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .vault-title {
            font-size: 2.1rem;
            font-weight: 800;
            background: linear-gradient(90deg, #ff7a45 0%, #ffa940 50%, #ffd591 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin: 0;
        }
        .vault-subtitle {
            color: #94a3b8;
            font-size: 0.95rem;
            margin-top: 4px;
        }

        /* Metric Cards */
        .kpi-card {
            background: #181920;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 14px;
            padding: 16px 18px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.2);
            transition: transform 0.2s ease, border-color 0.2s ease;
        }
        .kpi-card:hover {
            transform: translateY(-2px);
            border-color: rgba(255, 94, 54, 0.4);
        }
        .kpi-label {
            color: #8c8d9a;
            font-size: 0.78rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .kpi-value {
            font-size: 1.6rem;
            font-weight: 800;
            color: #ffffff;
            margin: 4px 0;
        }
        .kpi-delta-pos {
            color: #4ade80;
            font-size: 0.85rem;
            font-weight: 600;
        }
        .kpi-delta-neg {
            color: #f87171;
            font-size: 0.85rem;
            font-weight: 600;
        }

        /* Master Set Progress Bar */
        .master-box {
            background: #181920;
            border: 1px solid rgba(255, 122, 69, 0.3);
            border-radius: 14px;
            padding: 18px 22px;
            margin-bottom: 20px;
        }
        .progress-bar-bg {
            background: #27272a;
            border-radius: 10px;
            height: 14px;
            width: 100%;
            overflow: hidden;
            margin: 10px 0;
        }
        .progress-bar-fill {
            background: linear-gradient(90deg, #ff7a45 0%, #10b981 100%);
            height: 100%;
            border-radius: 10px;
            transition: width 0.6s ease;
        }

        /* Card Slab Display Containers */
        .slab-box {
            background: #181920;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 14px;
            margin-bottom: 16px;
            transition: all 0.2s ease;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        }
        .slab-box:hover {
            border-color: rgba(255, 122, 69, 0.45);
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.3);
        }

        /* Badges */
        .badge-psa {
            background: rgba(239, 68, 68, 0.15);
            border: 1px solid #ef4444;
            color: #f87171;
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
            color: #60a5fa;
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
            color: #fbbf24;
            padding: 2px 8px;
            border-radius: 12px;
            font-weight: 800;
            font-size: 0.75rem;
            letter-spacing: 0.5px;
            display: inline-block;
        }
        .badge-pristine {
            background: linear-gradient(135deg, rgba(236, 72, 153, 0.3), rgba(168, 85, 247, 0.3));
            border: 1px solid #ec4899;
            color: #f472b6;
            padding: 2px 9px;
            border-radius: 12px;
            font-weight: 800;
            font-size: 0.75rem;
            letter-spacing: 0.5px;
            display: inline-block;
        }
        .badge-black-label {
            background: #09090b;
            border: 1px solid #eab308;
            color: #facc15;
            padding: 2px 9px;
            border-radius: 12px;
            font-weight: 900;
            font-size: 0.75rem;
            letter-spacing: 0.5px;
            display: inline-block;
            box-shadow: 0 0 8px rgba(234, 179, 8, 0.4);
        }
        .badge-raw {
            background: rgba(148, 163, 184, 0.15);
            border: 1px solid #94a3b8;
            color: #cbd5e1;
            padding: 2px 8px;
            border-radius: 12px;
            font-weight: 700;
            font-size: 0.75rem;
            display: inline-block;
        }
        .badge-error {
            background: rgba(220, 38, 38, 0.25);
            border: 1px solid #dc2626;
            color: #fca5a5;
            padding: 2px 8px;
            border-radius: 12px;
            font-weight: 800;
            font-size: 0.72rem;
            display: inline-block;
        }
        .badge-low-pop {
            background: rgba(245, 158, 11, 0.15);
            border: 1px solid #f59e0b;
            color: #fbbf24;
            padding: 2px 8px;
            border-radius: 12px;
            font-weight: 800;
            font-size: 0.72rem;
            display: inline-block;
        }
        .badge-pop-1 {
            background: linear-gradient(135deg, rgba(234, 179, 8, 0.3), rgba(249, 115, 22, 0.3));
            border: 1px solid #eab308;
            color: #fef08a;
            padding: 2px 9px;
            border-radius: 12px;
            font-weight: 900;
            font-size: 0.72rem;
            display: inline-block;
            box-shadow: 0 0 10px rgba(234, 179, 8, 0.4);
        }

        /* Deal Badges */
        .deal-amazing {
            background: rgba(239, 68, 68, 0.2);
            border: 1px solid #ef4444;
            color: #f87171;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: 800;
            font-size: 0.8rem;
            display: inline-block;
            box-shadow: 0 0 8px rgba(239, 68, 68, 0.3);
        }
        .deal-great {
            background: rgba(245, 158, 11, 0.2);
            border: 1px solid #f59e0b;
            color: #fbbf24;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: 800;
            font-size: 0.8rem;
            display: inline-block;
        }
        .deal-good {
            background: rgba(34, 197, 94, 0.15);
            border: 1px solid #22c55e;
            color: #4ade80;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: 700;
            font-size: 0.8rem;
            display: inline-block;
        }

        /* Sniper Watchlist Styles */
        .sniper-card {
            background: #181920;
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 14px;
        }
        .sniper-badge-alert {
            background: rgba(239, 68, 68, 0.2);
            border: 1px solid #ef4444;
            color: #f87171;
            padding: 3px 10px;
            border-radius: 12px;
            font-weight: 800;
            font-size: 0.75rem;
            display: inline-block;
        }
        .sniper-badge-ok {
            background: rgba(34, 197, 94, 0.15);
            border: 1px solid #22c55e;
            color: #4ade80;
            padding: 3px 10px;
            border-radius: 12px;
            font-weight: 700;
            font-size: 0.75rem;
            display: inline-block;
        }

        .btn-ebay {
            background: linear-gradient(135deg, #3b82f6, #1d4ed8);
            color: white !important;
            text-decoration: none;
            padding: 5px 10px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.75rem;
            display: inline-block;
            transition: opacity 0.2s ease;
        }
        .btn-ebay:hover {
            opacity: 0.9;
        }

        .btn-pc {
            background: linear-gradient(135deg, #10b981, #059669);
            color: white !important;
            text-decoration: none;
            padding: 4px 8px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.72rem;
            display: inline-block;
        }

        .block-container {
            padding-top: 1.8rem;
            padding-bottom: 3rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header():
    """Renders the top branding header."""
    st.markdown(
        """
        <div class="vault-header">
            <div>
                <div class="vault-title">🦊 The Vulpix Vault</div>
                <div class="vault-subtitle">Master Set Completion, PriceCharting Aggregator, PSA Population & AI Deal Sniper</div>
            </div>
            <div style="text-align: right;">
                <span style="background: rgba(74, 222, 128, 0.15); color: #4ade80; border: 1px solid #4ade80; padding: 6px 14px; border-radius: 20px; font-weight: 700; font-size: 0.85rem;">
                    ● Daemon Live
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_edition_badge_html(edition: str) -> str:
    """Returns styled HTML badge for 1st Edition, Shadowless, Rainbow Rare, Art Rare, SAR, etc."""
    ed_lower = str(edition).lower()
    if "1st" in ed_lower or "first" in ed_lower:
        return '<span style="background: linear-gradient(135deg, rgba(245, 158, 11, 0.25), rgba(217, 119, 6, 0.15)); border: 1px solid #f59e0b; color: #fbbf24; padding: 2px 8px; border-radius: 12px; font-weight: 800; font-size: 0.72rem; letter-spacing: 0.5px;">🥇 1ST EDITION</span>'
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
