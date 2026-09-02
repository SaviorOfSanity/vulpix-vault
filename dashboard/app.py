"""
The Vulpix Vault - High-Performance Multi-Page Application Router
Organizes your personal collection, master set, market intelligence, and sniper tools into isolated, fast-loading pages.
"""

import streamlit as st

# Global Application Configuration
st.set_page_config(
    page_title="The Vulpix Vault",
    page_icon="🦊",
    layout="wide",
    initial_sidebar_state="expanded",
)

if hasattr(st, "navigation"):
    pages = {
        "Collection & Vault": [
            st.Page("pages/1_vault.py", title="My Vault & Portfolio", icon="💼", default=True),
            st.Page("pages/2_master_set.py", title="Master Set Checklist", icon="📜"),
        ],
        "Sniper & Market Tools": [
            st.Page("pages/3_sniper.py", title="eBay Sniper Watchlist", icon="🎯"),
            st.Page("pages/4_deals.py", title="AI Deal Radar", icon="🔥"),
            st.Page("pages/5_market.py", title="Market Sales Explorer", icon="📊"),
        ],
        "Admin": [
            st.Page("pages/6_settings.py", title="System Controls & Diagnostics", icon="⚙️"),
        ],
    }
    pg = st.navigation(pages)
    pg.run()
else:
    # Fallback for Streamlit < 1.36
    import runpy
    runpy.run_path("pages/1_vault.py")
