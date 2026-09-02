"""
The Vulpix Vault - Page 6: System Controls & Settings
Database diagnostics, push notification configuration, and system parameters.
"""

import os
import streamlit as st

from db_utils import (
    clear_entire_collection,
    get_db_path,
    get_master_set_metrics,
    get_portfolio_metrics,
    get_sniper_watchlist_df,
    get_system_setting,
    load_collection_df,
    load_market_sales_df,
    send_gotify_alert,
    set_system_setting,
)
from styles import apply_custom_styles, render_header

apply_custom_styles()
render_header()

st.markdown("### ⚙️ System Controls & Diagnostics")

col_s1, col_s2 = st.columns(2)

with col_s1:
    st.markdown("#### 🗄️ Database Diagnostics")
    db_path = get_db_path()
    file_size_kb = round(os.path.getsize(db_path) / 1024, 2) if os.path.exists(db_path) else 0
    master_metrics = get_master_set_metrics()
    df_col = load_collection_df()
    df_sniper = get_sniper_watchlist_df()
    df_market = load_market_sales_df()

    st.markdown(f"- **Database Path:** `{db_path}`")
    st.markdown(f"- **Database File Size:** `{file_size_kb} KB`")
    st.markdown(f"- **Master Set Catalog:** `{master_metrics['total_cards']} unique cards`")
    st.markdown(f"- **Personal Vault Records:** `{len(df_col)} items`")
    st.markdown(f"- **Sniper Watchlist:** `{len(df_sniper)} active targets`")
    st.markdown(f"- **Historical Sales Records:** `{len(df_market)} listings`")

    st.markdown("---")
    st.markdown("#### 🗑️ Vault Collection Management & Reset (Danger Zone)")
    st.warning("Need to clear out test cards or cards imported from your spreadsheet that you don't actually own?")
    st.write("Clicking below will clear all personal cards currently stored in your Vault collection so you can start completely fresh.")
    if st.button("🚨 Wipe All Owned Cards from Vault", type="primary", key="wipe_vault_btn"):
        cnt = clear_entire_collection()
        st.cache_data.clear()
        st.success(f"Successfully cleared {cnt} cards from your Vault!")
        st.rerun()

with col_s2:
    st.markdown("#### 🔔 Gotify Push Notification Settings")
    saved_token = get_system_setting("GOTIFY_APP_TOKEN", os.getenv("GOTIFY_APP_TOKEN", ""))
    saved_url = get_system_setting("GOTIFY_URL", os.getenv("GOTIFY_URL", "http://gotify:80"))

    with st.form("gotify_settings_form"):
        in_token = st.text_input(
            "Gotify Application Token (App Key)",
            value=saved_token,
            placeholder="e.g. Axxxxxxxxxxxxxx",
            type="password",
            help="Created in Gotify Web UI -> Apps -> Create App",
        )
        in_url = st.text_input(
            "Gotify Server URL",
            value=saved_url or "http://gotify:80",
            placeholder="http://gotify:80 or http://10.0.0.48:8070",
            help="Inside Docker, http://gotify:80 connects directly. On host network, use port 8070.",
        )

        st.caption("💡 *Inside Docker container, `http://gotify:80` connects directly. On host network, use `http://10.0.0.48:8070`.*")
        save_gotify = st.form_submit_button("💾 Save Credentials & Send Test Alert")

        if save_gotify:
            if in_token.strip():
                set_system_setting("GOTIFY_APP_TOKEN", in_token.strip())
                set_system_setting("GOTIFY_URL", in_url.strip())
                test_listing = {
                    "listing_id": "test_alert_005",
                    "title": "Vulpix 1st Edition Base Set PSA 10 (TEST GOTIFY ALERT)",
                    "card_name": "Vulpix",
                    "grading_company": "PSA",
                    "grade": 10.0,
                    "grade_label": "Gem Mint 10",
                    "condition_type": "Graded",
                    "total_price": 75.0,
                    "listing_url": "https://www.ebay.com",
                }
                test_appraisal = {
                    "deal_rating": "amazing_deal",
                    "fair_value": 240.0,
                    "discount_percentage": 68.75,
                    "rationale": "Test push alert dispatched directly from Vulpix Vault System Settings.",
                }
                ok = send_gotify_alert(test_listing, test_appraisal, gotify_url=in_url.strip(), gotify_token=in_token.strip())
                if ok:
                    st.success("✅ Test push notification delivered successfully to Gotify!")
                else:
                    st.error("Failed to connect to Gotify. Check server URL and application token.")
            else:
                st.warning("Please enter a Gotify application token.")
