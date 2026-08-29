"""
Custom CSS styling and HTML components for The Vulpix Vault Streamlit Dashboard.
"""

import streamlit as st


def apply_custom_styles():
    """Injects custom CSS for a modern, sleek Pokémon collector interface."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap');

        html, body, [class*="css"] {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        /* Hero Banner */
        .vault-header {
            background: linear-gradient(135deg, #1e1e24 0%, #2a1b1b 50%, #1f1a24 100%);
            border: 1px solid rgba(255, 94, 54, 0.25);
            border-radius: 16px;
            padding: 24px 30px;
            margin-bottom: 24px;
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
            color: #a0a0b0;
            font-size: 0.95rem;
            margin-top: 4px;
        }

        /* Metric Cards */
        .kpi-card {
            background: #181920;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 14px;
            padding: 18px 20px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.2);
            transition: transform 0.2s ease, border-color 0.2s ease;
        }
        .kpi-card:hover {
            transform: translateY(-2px);
            border-color: rgba(255, 94, 54, 0.4);
        }
        .kpi-label {
            color: #8c8d9a;
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .kpi-value {
            font-size: 1.7rem;
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

        /* Slab Card */
        .slab-box {
            background: #181920;
            border-radius: 14px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            padding: 16px;
            margin-bottom: 18px;
            transition: all 0.2s ease-in-out;
        }
        .slab-box:hover {
            border-color: #ff7a45;
            box-shadow: 0 8px 24px rgba(255, 122, 69, 0.15);
        }

        /* Grading Badges */
        .badge-psa {
            background: linear-gradient(135deg, #d32f2f, #9a0007);
            color: white;
            padding: 4px 10px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.8rem;
            display: inline-block;
            box-shadow: 0 2px 6px rgba(211, 47, 47, 0.4);
        }
        .badge-cgc {
            background: linear-gradient(135deg, #0288d1, #005b9f);
            color: white;
            padding: 4px 10px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.8rem;
            display: inline-block;
            box-shadow: 0 2px 6px rgba(2, 136, 209, 0.4);
        }
        .badge-bgs {
            background: linear-gradient(135deg, #d4af37, #aa820a);
            color: #121212;
            padding: 4px 10px;
            border-radius: 6px;
            font-weight: 800;
            font-size: 0.8rem;
            display: inline-block;
            box-shadow: 0 2px 6px rgba(212, 175, 55, 0.4);
        }
        .badge-other {
            background: #424242;
            color: white;
            padding: 4px 10px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 0.8rem;
            display: inline-block;
        }

        /* Deal Badges */
        .deal-amazing {
            background: rgba(239, 68, 68, 0.15);
            border: 1px solid #ef4444;
            color: #f87171;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: 700;
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

        /* Hide Streamlit Default Padding for cleaner look */
        .block-container {
            padding-top: 2rem;
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
                <div class="vault-subtitle">Self-Hosted Graded Slab Valuation & Automated AI Deal Radar</div>
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


def get_grading_badge_html(company: str, grade: float) -> str:
    """Returns styled HTML badge for grading slab."""
    co_upper = str(company).upper()
    if "PSA" in co_upper:
        css_class = "badge-psa"
    elif "CGC" in co_upper:
        css_class = "badge-cgc"
    elif "BGS" in co_upper or "BECKETT" in co_upper:
        css_class = "badge-bgs"
    else:
        css_class = "badge-other"

    grade_display = int(grade) if grade == int(grade) else grade
    return f'<span class="{css_class}">{co_upper} {grade_display}</span>'
