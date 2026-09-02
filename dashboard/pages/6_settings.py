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
    sync_ebay_user_account,
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

st.markdown("---")
st.markdown("#### 🛒 Official eBay API Integration & 1-Click Sync")
st.markdown(
    "Connect your eBay Developer credentials to automatically import your **personal Watchlist** into the Sniper Radar, "
    "pull your **past Pokémon purchases (Won List)** directly into your Vault, and track **active bids** in real time."
)

saved_ebay_token = get_system_setting("EBAY_USER_TOKEN", os.getenv("EBAY_USER_TOKEN", ""))
saved_ebay_app_id = get_system_setting("EBAY_APP_ID", os.getenv("EBAY_APP_ID", ""))
saved_ebay_cert_id = get_system_setting("EBAY_CERT_ID", os.getenv("EBAY_CERT_ID", ""))
saved_ebay_dev_id = get_system_setting("EBAY_DEV_ID", os.getenv("EBAY_DEV_ID", ""))

with st.form("ebay_api_settings_form"):
    e_col1, e_col2 = st.columns(2)
    with e_col1:
        in_ebay_app_id = st.text_input("eBay App ID (Client ID)", value=saved_ebay_app_id, placeholder="e.g. YourName-VulpixVa-PRD-xxxxxxxx")
        in_ebay_cert_id = st.text_input("eBay Cert ID (Client Secret)", value=saved_ebay_cert_id, placeholder="e.g. PRD-xxxxxxxxxxxx", type="password")
    with e_col2:
        in_ebay_dev_id = st.text_input("eBay Dev ID (Optional)", value=saved_ebay_dev_id, placeholder="e.g. xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
        in_ebay_token = st.text_area("eBay User Auth Token (Trading API Token)", value=saved_ebay_token, placeholder="v^1.1#i^1#p^3#r^1#I^3...", height=70)

    st.caption("💡 *Get these keys for free at [developer.ebay.com](https://developer.ebay.com). In your eBay Developer portal under **User Tokens**, generate a User Token for your account.*")

    eb_btn1, eb_btn2 = st.columns(2)
    with eb_btn1:
        save_eb_creds = st.form_submit_button("💾 Save eBay Credentials")
    with eb_btn2:
        sync_eb_now = st.form_submit_button("🔄 Auto-Sync Watchlist & Purchases", type="primary")

    if save_eb_creds:
        set_system_setting("EBAY_USER_TOKEN", in_ebay_token.strip())
        set_system_setting("EBAY_APP_ID", in_ebay_app_id.strip())
        set_system_setting("EBAY_CERT_ID", in_ebay_cert_id.strip())
        set_system_setting("EBAY_DEV_ID", in_ebay_dev_id.strip())
        st.success("eBay API credentials saved successfully!")

    if sync_eb_now:
        set_system_setting("EBAY_USER_TOKEN", in_ebay_token.strip())
        set_system_setting("EBAY_APP_ID", in_ebay_app_id.strip())
        set_system_setting("EBAY_CERT_ID", in_ebay_cert_id.strip())
        set_system_setting("EBAY_DEV_ID", in_ebay_dev_id.strip())
        with st.spinner("Connecting to eBay Trading API and syncing account data..."):
            ok, msg, stats = sync_ebay_user_account(
                user_token=in_ebay_token.strip(),
                app_id=in_ebay_app_id.strip(),
                dev_id=in_ebay_dev_id.strip(),
                cert_id=in_ebay_cert_id.strip(),
            )
            if ok:
                st.success(f"✅ {msg}")
                st.rerun()
            else:
                st.error(f"❌ {msg}")
