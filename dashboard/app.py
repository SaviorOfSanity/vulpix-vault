"""
The Vulpix Vault - Streamlit Web Dashboard
Master Set Completion Tracker, PriceCharting Aggregator, PSA/CGC Population (POP) Reports,
eBay Sniper & Watchlist, 1-Click Live eBay Search, and Multi-Tier AI Deal Radar.
"""

import os
from datetime import datetime
import pandas as pd
import plotly.express as px
import streamlit as st

from db_utils import (
    add_card_to_collection,
    add_to_sniper_watchlist,
    auto_enrich_master_catalog,
    bulk_import_collection_from_df,
    delete_card_from_collection,
    delete_from_sniper_watchlist,
    generate_ebay_search_url,
    get_card_aggregator_links,
    get_csv_template_bytes,
    get_db_path,
    get_master_set_metrics,
    get_portfolio_metrics,
    get_pricecharting_search_url,
    get_psa_cert_lookup_url,
    get_sniper_watchlist_df,
    get_system_setting,
    load_collection_df,
    load_deals_df,
    load_market_sales_df,
    load_master_catalog_df,
    parse_and_preview_catalog,
    parse_ebay_url_details,
    reset_and_clean_sync_master_catalog,
    send_gotify_alert,
    set_system_setting,
    sync_from_google_sheets_url,
    update_card_image_override,
    update_collection_card,
    update_master_card,
)
from metadata_resolver import DEFAULT_CARD_BACK_IMAGE
from styles import apply_custom_styles, get_edition_badge_html, get_grading_badge_html, get_pop_badge_html, render_header

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="The Vulpix Vault",
    page_icon="🦊",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_custom_styles()
render_header()

# Load Core Data
port_metrics = get_portfolio_metrics()
master_metrics = get_master_set_metrics()
df_col = load_collection_df()
df_master = load_master_catalog_df()
df_market = load_market_sales_df()
df_sniper = get_sniper_watchlist_df()

# -------------------------------------------------------------
# Main Navigation Tabs
# -------------------------------------------------------------
tab_portfolio, tab_master_set, tab_sniper, tab_deals, tab_market, tab_settings = st.tabs([
    "💼 My Vault & Portfolio",
    "📜 Master Set Checklist",
    "🎯 eBay Sniper Watchlist",
    "🔥 AI Deal Radar",
    "📊 Market Sales Explorer",
    "⚙️ System Controls & Gotify Sync",
])

# -------------------------------------------------------------
# TAB 1: Personal Collection & Portfolio
# -------------------------------------------------------------
with tab_portfolio:
    st.markdown("### 💼 Personal Vault Overview")

    # KPI Metric Cards
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Total Portfolio Value</div>
            <div class="kpi-value">${port_metrics['total_value']:,.2f}</div>
            <div class="kpi-delta-pos">Market Value</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Total Invested Cost</div>
            <div class="kpi-value">${port_metrics['total_cost']:,.2f}</div>
            <div style="color: #94a3b8; font-size: 0.85rem;">Purchase Basis</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        gain_cls = "kpi-delta-pos" if port_metrics["net_gain"] >= 0 else "kpi-delta-neg"
        sign = "+" if port_metrics["net_gain"] >= 0 else ""
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Unrealized Gain / ROI</div>
            <div class="kpi-value">{sign}${port_metrics['net_gain']:,.2f}</div>
            <div class="{gain_cls}">{sign}{port_metrics['roi_percent']}% ROI</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Vault Slabs & Singles</div>
            <div class="kpi-value">{port_metrics['total_slabs'] + port_metrics['total_raw']} Items</div>
            <div style="color: #60a5fa; font-size: 0.85rem;">{port_metrics['total_slabs']} Graded • {port_metrics['total_raw']} Raw</div>
        </div>""", unsafe_allow_html=True)
    with c5:
        st.markdown(f"""<div class="kpi-card">
            <div class="kpi-label">Master Set Progress</div>
            <div class="kpi-value">{master_metrics['completion_pct']}%</div>
            <div style="color: #10b981; font-size: 0.85rem;">{master_metrics['owned_cards']} / {master_metrics['total_cards']} Unique</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Add Card Expanders (Manual + CSV Import)
    col_add1, col_add2 = st.columns(2)
    with col_add1:
        with st.expander("➕ Manually Add Graded Slab or Raw Card to Vault", expanded=False):
            with st.form("manual_add_card_form", clear_on_submit=True):
                f_c1, f_c2 = st.columns(2)
                with f_c1:
                    card_name = st.text_input("Card Name*", value="Vulpix")
                    set_name = st.text_input("Set / Expansion*", value="Base Set")
                    card_num = st.text_input("Card Number", value="68/102")
                    condition_type = st.radio("Condition Category*", ["Graded Slab", "Raw Single"], horizontal=True)
                    grader = st.selectbox("Grading Company", ["RAW", "PSA", "CGC", "BGS", "ARS", "ACE"]) if condition_type == "Graded Slab" else "RAW"
                    grade_num = st.number_input("Numerical Grade", min_value=0.0, max_value=10.0, value=10.0 if condition_type == "Graded Slab" else 0.0, step=0.5)
                with f_c2:
                    grade_label = st.selectbox("Grade Label Tier", ["Raw Single", "Gem Mint", "Pristine 10", "Black Label 10", "Mint 9", "Near Mint 8", "Ungraded"])
                    cert_num = st.text_input("Certification Number (Slab Cert #)", placeholder="e.g. 84729103")
                    buy_price = st.number_input("Purchase Price ($)*", min_value=0.0, value=25.0, step=5.0)
                    buy_date = st.date_input("Purchase Date", value=datetime.today())
                    edition = st.selectbox("Edition", ["Unlimited", "1st Edition", "Shadowless", "Reverse Holo", "Promo", "4th Print (1999-2000)"])
                    language = st.selectbox("Language", ["English", "Japanese", "German", "French", "Korean", "Chinese", "Italian"])

                is_err = st.checkbox("Is Error / Misprint Card?")
                err_desc = st.text_input("Error Description", placeholder="e.g. Blue Ink Drop Error, HP 50 Error") if is_err else ""
                notes = st.text_area("Personal Notes / Provenance", placeholder="e.g. Won on eBay auction, subgrade details...")
                submit_add = st.form_submit_button("💾 Save Card to Vault")

                if submit_add:
                    if not card_name or not set_name:
                        st.error("Card Name and Set Name are required.")
                    else:
                        new_id = add_card_to_collection({
                            "card_name": card_name,
                            "set_name": set_name,
                            "card_number": card_num,
                            "grading_company": grader,
                            "grade": grade_num,
                            "grade_label": grade_label,
                            "cert_number": cert_num,
                            "purchase_price": buy_price,
                            "purchase_date": str(buy_date),
                            "edition": edition,
                            "language": language,
                            "is_error": 1 if is_err else 0,
                            "error_type": err_desc if is_err else None,
                            "is_raw": 1 if condition_type == "Raw Single" else 0,
                            "notes": notes,
                        })
                        st.success(f"Added {card_name} to your Vault!")
                        st.rerun()

    with col_add2:
        with st.expander("📥 Bulk Import Owned Cards from CSV", expanded=False):
            st.markdown("Import cards you already own from a CSV file directly into your Vault.")
            st.download_button(
                "📥 Download Starter CSV Template",
                data=get_csv_template_bytes(),
                file_name="vulpix_collection_starter_template.csv",
                mime="text/csv",
            )
            col_csv_file = st.file_uploader("Upload Collection CSV", type=["csv"], key="vault_csv_uploader")
            if col_csv_file is not None:
                try:
                    df_up_col = pd.read_csv(col_csv_file)
                    st.dataframe(df_up_col.head(3), use_container_width=True)
                    if st.button("🚀 Confirm Bulk Import into Vault"):
                        count_imp, msg_imp = bulk_import_collection_from_df(df_up_col)
                        st.success(msg_imp)
                        st.rerun()
                except Exception as e:
                    st.error(f"Error reading CSV: {e}")

    # Collection Display
    if df_col.empty:
        st.info("💡 Your Vault is currently empty. Add cards above or sync from your Google Sheet in Tab 2!")
    else:
        v_col1, v_col2 = st.columns([3, 1])
        with v_col1:
            st.markdown(f"#### 🏆 Your Collection ({len(df_col)} Items)")
        with v_col2:
            view_mode = st.radio("Display Layout:", ["🃏 Card Grid View", "📋 Table / List View"], horizontal=True, key="vault_v_mode")

        if "Card Grid" in view_mode:
            grid_cols = st.columns(3)
            for idx, row in df_col.iterrows():
                target_col = grid_cols[idx % 3]
                with target_col:
                    grade_badge = get_grading_badge_html(
                        company=row["grading_company"],
                        grade=row["grade"],
                        grade_label=row.get("grade_label", "Gem Mint"),
                        is_raw=row.get("is_raw", 0),
                    )
                    ed_badge = get_edition_badge_html(row.get("edition", "Unlimited"))
                    err_badge = '<span class="badge-error">⚠️ ERROR</span>' if row["is_error"] == 1 else ""
                    pop_badge = get_pop_badge_html(int(row.get("pop_grade10") or 0), int(row.get("pop_pristine10") or 0))

                    img_src = row["image_url"] if row["image_url"] else DEFAULT_CARD_BACK_IMAGE
                    psa_link = get_psa_cert_lookup_url(row["cert_number"]) if row["cert_number"] else None
                    cert_display = f'<a href="{psa_link}" target="_blank" style="color: #60a5fa; text-decoration: none; font-weight: 700;">#{row["cert_number"]} ↗</a>' if psa_link else (f'#{row["cert_number"]}' if row["cert_number"] else 'Raw Single')

                    gain_sign = "+" if row["unrealized_gain"] >= 0 else ""
                    gain_color = "#4ade80" if row["unrealized_gain"] >= 0 else "#f87171"
                    card_num_str = f"#{row['card_number']}" if row['card_number'] and str(row['card_number']).lower() != "nan" else "(Promo / No #)"

                    card_box_html = f"""<div class="slab-box">
<div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
<div style="display: flex; gap: 4px; align-items: center; flex-wrap: wrap;">{grade_badge} {ed_badge} {err_badge}</div>
<div>{pop_badge}</div>
</div>
<div style="text-align: center; margin: 10px 0;">
<img src="{img_src}" style="max-height: 175px; max-width: 100%; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.5);" />
</div>
<div style="font-weight: 800; font-size: 1.05rem; color: #ffffff;">{row['card_name']}</div>
<div style="color: #8c8d9a; font-size: 0.82rem; margin-bottom: 8px;">{row['set_name']} • {card_num_str}</div>
<div style="background: #111217; padding: 8px 10px; border-radius: 8px; font-size: 0.82rem; margin-bottom: 8px;">
<div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
<span style="color: #8c8d9a;">Bought:</span>
<span style="color: #fff; font-weight: 600;">${row['purchase_price']:,.2f} ({row['purchase_date']})</span>
</div>
<div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
<span style="color: #8c8d9a;">Est. Market:</span>
<span style="color: #ffd591; font-weight: 700;">${row['current_market_value']:,.2f}</span>
</div>
<div style="display: flex; justify-content: space-between;">
<span style="color: #8c8d9a;">Gain / ROI:</span>
<span style="color: {gain_color}; font-weight: 700;">{gain_sign}${row['unrealized_gain']:,.2f} ({gain_sign}{row['roi_percent']}%)</span>
</div>
</div>
<div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.78rem; color: #8c8d9a;">
<span>Cert: {cert_display}</span>
<span>{row['language']}</span>
</div>
</div>"""
                    st.markdown(card_box_html, unsafe_allow_html=True)

                    # Action buttons
                    b1, b2, b3 = st.columns(3)
                    with b1:
                        with st.popover("✏️ Edit"):
                            with st.form(f"edit_form_{row['id']}"):
                                e_name = st.text_input("Card Name", value=row["card_name"])
                                e_set = st.text_input("Set Name", value=row["set_name"])
                                e_num = st.text_input("Card #", value=row["card_number"])
                                e_grader = st.selectbox("Grader", ["RAW", "PSA", "CGC", "BGS", "ARS", "ACE"], index=0 if row["is_raw"] else 1)
                                e_grade = st.number_input("Grade", min_value=0.0, max_value=10.0, value=float(row["grade"]), step=0.5)
                                e_label = st.selectbox("Grade Label", ["Raw Single", "Gem Mint", "Pristine 10", "Black Label 10", "Mint 9", "Near Mint 8"])
                                e_cert = st.text_input("Cert #", value=row["cert_number"] or "")
                                e_cost = st.number_input("Purchase Price ($)", min_value=0.0, value=float(row["purchase_price"]), step=5.0)
                                e_date = st.text_input("Purchase Date", value=str(row["purchase_date"]))
                                e_ed = st.text_input("Edition", value=str(row["edition"]))
                                e_lang = st.text_input("Language", value=str(row["language"]))
                                e_err = st.checkbox("Error Card?", value=bool(row["is_error"]))
                                e_err_type = st.text_input("Error Type", value=row["error_type"] or "") if e_err else ""
                                e_img = st.text_input("Image URL", value=row["image_url"] or "")
                                e_notes = st.text_area("Notes", value=row["notes"] or "")

                                if st.form_submit_button("Save Changes"):
                                    update_collection_card(row["id"], {
                                        "card_name": e_name,
                                        "set_name": e_set,
                                        "card_number": e_num,
                                        "grading_company": e_grader,
                                        "grade": e_grade,
                                        "grade_label": e_label,
                                        "cert_number": e_cert,
                                        "purchase_price": e_cost,
                                        "purchase_date": e_date,
                                        "edition": e_ed,
                                        "language": e_lang,
                                        "is_error": 1 if e_err else 0,
                                        "error_type": e_err_type if e_err else None,
                                        "is_raw": 1 if e_grader == "RAW" else 0,
                                        "image_url": e_img,
                                        "notes": e_notes,
                                    })
                                    st.success("Updated card!")
                                    st.rerun()

                    with b2:
                        with st.popover("🗑️ Remove"):
                            st.write(f"Remove **{row['card_name']}** ({row['set_name']}) from your Vault?")
                            if st.button("Confirm Delete", key=f"del_{row['id']}", type="primary"):
                                delete_card_from_collection(row["id"])
                                st.success("Removed from Vault!")
                                st.rerun()

                    with b3:
                        with st.popover("ℹ️ Info"):
                            st.markdown(f"#### 🔍 {row['card_name']}")
                            st.markdown(f"**Set:** {row['set_name']} • **Number:** `{card_num_str}`")
                            st.markdown(f"**Edition:** {row['edition']} • **Language:** {row['language']}")
                            if row["is_error"] == 1 and row.get("error_type"):
                                st.error(f"**⚠️ Known Card Errors & Misprints:**\n\n{row['error_type']}")
                            st.markdown(f"- **Purchase Price:** `${row['purchase_price']:,.2f}` on {row['purchase_date']}")
                            st.markdown(f"- **Est. Market Value:** `${row['current_market_value']:,.2f}` ({gain_sign}${row['unrealized_gain']:,.2f})")
                            if row.get("cert_number"):
                                st.markdown(f"- **Cert #:** `{row['cert_number']}` ({row['grading_company']} {row['grade_label']})")
                            if row.get("notes"):
                                st.markdown(f"- **Notes:** {row['notes']}")
        else:
            st.dataframe(
                df_col[[
                    "card_name", "set_name", "card_number", "grading_company",
                    "grade_label", "cert_number", "edition", "language",
                    "purchase_price", "current_market_value", "unrealized_gain", "roi_percent", "notes"
                ]].rename(columns={
                    "card_name": "Card Name",
                    "set_name": "Set",
                    "card_number": "#",
                    "grading_company": "Grader",
                    "grade_label": "Grade / Slab",
                    "cert_number": "Cert #",
                    "edition": "Edition",
                    "language": "Language",
                    "purchase_price": "Bought ($)",
                    "current_market_value": "Market ($)",
                    "unrealized_gain": "Gain ($)",
                    "roi_percent": "ROI (%)",
                }),
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("---")
        with st.expander("🗑️ Vault Collection Management & Reset (Danger Zone)", expanded=False):
            st.warning("Need to clear out test cards or cards imported from your spreadsheet that you don't actually own?")
            st.write("Clicking below will clear all personal cards currently stored in your Vault collection so you can start completely fresh or add cards individually.")
            if st.button("🚨 Wipe All Owned Cards from Vault", type="primary", key="wipe_vault_btn"):
                cnt = clear_entire_collection()
                st.success(f"Successfully cleared {cnt} cards from your Vault!")
                st.rerun()


# -------------------------------------------------------------
# TAB 2: Master Set Checklist & Pre-Import Verification
# -------------------------------------------------------------
with tab_master_set:
    st.markdown("### 📜 Master Set Checklist & Catalog")

    # Progress Header
    pct = master_metrics["completion_pct"]
    st.markdown(
        f"""<div class="master-box">
<div style="display: flex; justify-content: space-between; align-items: center;">
<div style="font-weight: 800; font-size: 1.2rem; color: #ffffff;">Vulpix Master Set Completion</div>
<div style="font-weight: 800; font-size: 1.4rem; color: #10b981;">{pct}%</div>
</div>
<div class="progress-bar-bg">
<div class="progress-bar-fill" style="width: {pct}%;"></div>
</div>
<div style="display: flex; justify-content: space-between; font-size: 0.85rem; color: #8c8d9a;">
<span>Owned: <strong style="color: #fff;">{master_metrics['owned_cards']}</strong> / {master_metrics['total_cards']} Unique</span>
<span>Missing: <strong style="color: #f87171;">{master_metrics['missing_cards']}</strong> cards</span>
<span>Est. Raw Finish Cost: <strong style="color: #ffd591;">${master_metrics['cost_to_complete_raw']:,.2f}</strong></span>
<span>Est. Grade 10 Finish Cost: <strong style="color: #f59e0b;">${master_metrics['cost_to_complete_grade10']:,.2f}</strong></span>
</div>
</div>""",
        unsafe_allow_html=True,
    )

    # Metadata Verification & Auto-Enrichment Banner
    en_col1, en_col2 = st.columns([3, 1])
    with en_col1:
        st.markdown(
            "💡 *Card name missing or showing wrong artwork? Click to query Pokemon.com & 200+ Master Index to fill exact names (e.g. Blaine's Vulpix) and official card scans.*"
        )
    with en_col2:
        if st.button("⚡ Auto-Enrich Names & Images", key="btn_auto_enrich_master"):
            with st.spinner("Resolving card names and fetching official scans..."):
                cnt, msg = auto_enrich_master_catalog(force_all=True)
                st.success(msg)
                st.rerun()

    # Filter Controls
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1:
        m_view = st.selectbox("Status Filter", ["All Master Cards", "❌ Missing Cards Only", "✅ Owned Cards Only", "🥇 1st Edition Only", "💎 Low Pop (<20 PSA 10)", "⚠️ Error Cards Only"])
    with m_col2:
        m_langs = ["All Languages"] + sorted(df_master["language"].dropna().unique().tolist())
        m_sel_lang = st.selectbox("Language Filter", m_langs)
    with m_col3:
        m_eds = ["All Editions"] + sorted(df_master["edition"].dropna().unique().tolist())
        m_sel_ed = st.selectbox("Edition Filter", m_eds)
    with m_col4:
        m_search = st.text_input("Search Set or Card Name", placeholder="e.g. Neo Destiny, Blaine, CoroCoro...")

    # Filter DataFrame
    filtered_master = df_master.copy()
    if m_view == "❌ Missing Cards Only":
        filtered_master = filtered_master[~filtered_master["is_owned"]]
    elif m_view == "✅ Owned Cards Only":
        filtered_master = filtered_master[filtered_master["is_owned"]]
    elif m_view == "🥇 1st Edition Only":
        filtered_master = filtered_master[filtered_master["edition"].str.contains("1st", case=False, na=False)]
    elif m_view == "💎 Low Pop (<20 PSA 10)":
        filtered_master = filtered_master[(filtered_master["pop_grade10"] > 0) & (filtered_master["pop_grade10"] <= 20)]
    elif m_view == "⚠️ Error Cards Only":
        filtered_master = filtered_master[filtered_master["is_error"] == 1]

    if m_sel_lang != "All Languages":
        filtered_master = filtered_master[filtered_master["language"] == m_sel_lang]
    if m_sel_ed != "All Editions":
        filtered_master = filtered_master[filtered_master["edition"] == m_sel_ed]
    if m_search:
        filtered_master = filtered_master[
            filtered_master["card_name"].str.contains(m_search, case=False, na=False) |
            filtered_master["set_name"].str.contains(m_search, case=False, na=False)
        ]

    # View Mode Toggle
    m_top1, m_top2 = st.columns([3, 1])
    with m_top1:
        st.markdown(f"**Showing {len(filtered_master)} Cards in Catalog**")
    with m_top2:
        master_view_mode = st.radio("Display Layout:", ["🃏 Card Grid View", "📋 Table / List View"], horizontal=True, key="master_v_mode")

    if "Card Grid" in master_view_mode:
        m_cols = st.columns(4)
        for idx, row in filtered_master.iterrows():
            col_target = m_cols[idx % 4]
            with col_target:
                is_owned = row["is_owned"]
                status_badge = (
                    '<span style="background: rgba(34, 197, 94, 0.2); border: 1px solid #22c55e; color: #4ade80; padding: 2px 8px; border-radius: 12px; font-weight: 700; font-size: 0.72rem;">✅ OWNED</span>'
                    if is_owned
                    else '<span style="background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; color: #f87171; padding: 2px 8px; border-radius: 12px; font-weight: 700; font-size: 0.72rem;">❌ MISSING</span>'
                )
                ed_badge = get_edition_badge_html(row.get("edition", "Unlimited"))
                err_badge = '<span class="badge-error">⚠️ ERROR</span>' if row["is_error"] == 1 else ""
                pop_badge = get_pop_badge_html(int(row.get("pop_grade10") or 0), int(row.get("pop_pristine10") or 0))
                img_src = row["image_url"] if row["image_url"] else DEFAULT_CARD_BACK_IMAGE

                # 1-Click Search URLs for Raw, Grade 10, and PriceCharting
                raw_ebay_url = generate_ebay_search_url(
                    card_name=row["card_name"],
                    set_name=row["set_name"],
                    card_number=row["card_number"],
                    edition=row["edition"],
                    language=row["language"],
                    is_raw=True,
                )
                g10_ebay_url = generate_ebay_search_url(
                    card_name=row["card_name"],
                    set_name=row["set_name"],
                    card_number=row["card_number"],
                    edition=row["edition"],
                    language=row["language"],
                    grade_tier="Gem Mint 10",
                )
                pc_url = row.get("pricecharting_url") or get_pricecharting_search_url(row["card_name"], row["set_name"], row["card_number"])

                card_num_display = f"#{row['card_number']}" if row['card_number'] and str(row['card_number']).lower() != "nan" else "(Promo / No #)"

                # Render HTML unindented to prevent markdown code block bug
                master_card_html = f"""<div class="slab-box" style="padding: 12px; margin-bottom: 14px;">
<div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px;">
<div style="font-size: 0.78rem; font-weight: 700; color: #94a3b8;">{row['release_year']} • {row['language']}</div>
<div style="display: flex; gap: 3px; align-items: center; flex-wrap: wrap;">{ed_badge} {err_badge} {status_badge}</div>
</div>
<div style="text-align: center; margin: 8px 0;">
<img src="{img_src}" style="max-height: 155px; max-width: 100%; border-radius: 6px; box-shadow: 0 4px 10px rgba(0,0,0,0.5);" />
</div>
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px;">
<div style="font-weight: 800; font-size: 0.92rem; color: #ffffff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{row['card_name']}</div>
{pop_badge}
</div>
<div style="color: #8c8d9a; font-size: 0.78rem; margin-bottom: 8px;">{row['set_name']} • {card_num_display}</div>
<div style="background: #111217; padding: 6px 8px; border-radius: 6px; font-size: 0.78rem; margin-bottom: 8px;">
<div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
<span style="color: #8c8d9a;">Est Raw:</span>
<span style="color: #ffd591; font-weight: 700;">${row['est_raw_price']:,.2f}</span>
</div>
<div style="display: flex; justify-content: space-between;">
<span style="color: #8c8d9a;">Est PSA 10:</span>
<span style="color: #f59e0b; font-weight: 700;">${row['est_grade10_price']:,.2f}</span>
</div>
</div>
<div style="display: flex; gap: 4px; margin-bottom: 4px;">
<a href="{raw_ebay_url}" target="_blank" class="btn-ebay" style="flex: 1; text-align: center; font-size: 0.72rem; padding: 3px;">
🔍 Raw
</a>
<a href="{g10_ebay_url}" target="_blank" class="btn-ebay" style="flex: 1; text-align: center; font-size: 0.72rem; padding: 3px; background: linear-gradient(135deg, #f59e0b, #d97706);">
💎 PSA 10
</a>
<a href="{pc_url}" target="_blank" class="btn-pc" style="flex: 1; text-align: center; font-size: 0.72rem; padding: 3px;">
📊 Charting
</a>
</div>
</div>"""

                st.markdown(master_card_html, unsafe_allow_html=True)

                # Quick Action Buttons
                act1, act2, act3 = st.columns(3)
                with act1:
                    pop_label = "✅ Owned" if row["is_owned"] else "📥 Add"
                    with st.popover(pop_label):
                        if row["is_owned"]:
                            st.markdown(f"**Status:** Marked as Owned in Vault (`{row['owned_copies']} copy`).")
                            st.caption(f"Details: {row['owned_details']}")
                            if st.button("❌ Remove / Unmark as Owned", key=f"unmark_{row['id']}", type="primary"):
                                unmark_card_as_owned(row["id"], row["card_name"], row["set_name"])
                                st.success("Unmarked card from Vault!")
                                st.rerun()
                            st.markdown("---")
                            st.markdown("**Add another copy to Vault:**")
                        else:
                            st.markdown(f"**Add {row['card_name']} to Vault:**")

                        with st.form(f"quick_add_{row['id']}"):
                            q_cond = st.radio("Condition", ["Raw Single", "Graded Slab"], horizontal=True)
                            q_co = st.selectbox("Grader", ["RAW", "PSA", "CGC", "BGS", "ARS", "ACE"]) if q_cond == "Graded Slab" else "RAW"
                            q_tier = st.selectbox("Grade Label", ["Raw Single", "Gem Mint", "Pristine 10", "Black Label 10", "Mint 9", "Near Mint 8"])
                            q_price = st.number_input("Purchase Price ($)", min_value=0.0, value=float(row["est_raw_price"] or 10.0))
                            if st.form_submit_button("Confirm Add"):
                                add_card_to_collection({
                                    "card_name": row["card_name"],
                                    "set_name": row["set_name"],
                                    "card_number": row["card_number"],
                                    "grading_company": q_co,
                                    "grade": 10.0 if q_cond == "Graded Slab" else 0.0,
                                    "grade_label": q_tier,
                                    "cert_number": "",
                                    "purchase_price": q_price,
                                    "purchase_date": datetime.today().strftime("%Y-%m-%d"),
                                    "edition": row["edition"],
                                    "language": row["language"],
                                    "is_error": row["is_error"],
                                    "error_type": row.get("error_description"),
                                    "is_raw": 1 if q_cond == "Raw Single" else 0,
                                    "pop_grade10": int(row.get("pop_grade10") or 0),
                                    "master_card_id": row["id"],
                                    "image_url": row["image_url"],
                                    "notes": f"Added from Master Set Catalog.",
                                })
                                st.success("Added to Vault!")
                                st.rerun()

                with act2:
                    with st.popover("✏️ Edit"):
                        with st.form(f"edit_m_{row['id']}"):
                            em_name = st.text_input("Card Name", value=row["card_name"])
                            em_set = st.text_input("Set Name", value=row["set_name"])
                            em_num = st.text_input("Card #", value=row["card_number"])
                            em_ed = st.text_input("Edition", value=row["edition"])
                            em_lang = st.text_input("Language", value=row["language"])
                            em_raw_p = st.number_input("Est Raw Price ($)", min_value=0.0, value=float(row["est_raw_price"]), step=2.0)
                            em_g10_p = st.number_input("Est Grade 10 Price ($)", min_value=0.0, value=float(row["est_grade10_price"]), step=10.0)
                            em_pop = st.number_input("PSA/CGC Pop (Grade 10)", min_value=0, value=int(row.get("pop_grade10") or 0))
                            em_img = st.text_input("Image URL (Replace/Flag)", value=row["image_url"])
                            em_err = st.checkbox("Is Error Card?", value=bool(row["is_error"]))
                            em_notes = st.text_area("Notes / Error Description", value=row.get("error_description") or row.get("notes") or "")
                            if st.form_submit_button("Save Changes"):
                                update_master_card(row["id"], {
                                    "card_name": em_name,
                                    "set_name": em_set,
                                    "card_number": em_num,
                                    "release_year": int(row["release_year"]),
                                    "language": em_lang,
                                    "edition": em_ed,
                                    "rarity": row["rarity"],
                                    "is_error": 1 if em_err else 0,
                                    "error_description": em_notes if em_err else "",
                                    "est_raw_price": em_raw_p,
                                    "est_grade10_price": em_g10_p,
                                    "pricecharting_raw": em_raw_p,
                                    "pricecharting_grade10": em_g10_p,
                                    "pop_grade10": int(em_pop),
                                    "image_url": em_img,
                                    "notes": em_notes,
                                })
                                st.success("Saved!")
                                st.rerun()

                        if row["image_url"] and row["image_url"] != DEFAULT_CARD_BACK_IMAGE:
                            if st.button("🚩 Reset Image to Card Back", key=f"flag_edit_{row['id']}"):
                                update_card_image_override("master_set_catalog", row["id"], DEFAULT_CARD_BACK_IMAGE)
                                st.success("Reset image to Card Back placeholder!")
                                st.rerun()

                with act3:
                    with st.popover("ℹ️ Info"):
                        st.markdown(f"#### 🔍 {row['card_name']}")
                        st.markdown(f"**Set:** {row['set_name']} • **Number:** `{card_num_display}`")
                        st.markdown(f"**Edition:** {row['edition']} • **Language:** {row['language']} • **Year:** {row['release_year']}")
                        
                        if row["is_owned"]:
                            st.success(f"**Ownership:** ✅ Owned in Vault ({row['owned_details']})")
                            if st.button("❌ Remove from Vault", key=f"info_unmark_{row['id']}"):
                                unmark_card_as_owned(row["id"], row["card_name"], row["set_name"])
                                st.success("Removed from Vault!")
                                st.rerun()

                        if row["is_error"] == 1:
                            err_text = row.get("error_description") or row.get("notes") or "Error Card / Misprint"
                            st.error(f"**⚠️ Known Card Errors & Misprints:**\n\n{err_text}")
                        
                        st.markdown(f"- **Est. Raw Value:** `${row['est_raw_price']:,.2f}`")
                        st.markdown(f"- **Est. PSA 10 Value:** `${row['est_grade10_price']:,.2f}`")
                        if row.get("pop_grade10"):
                            st.markdown(f"- **PSA 10 Population:** `{row['pop_grade10']}`")

                        if row["image_url"] and row["image_url"] != DEFAULT_CARD_BACK_IMAGE:
                            if st.button("🚩 Flag Image as Incorrect", key=f"flag_info_{row['id']}"):
                                update_card_image_override("master_set_catalog", row["id"], DEFAULT_CARD_BACK_IMAGE)
                                st.success("Image reset to Card Back placeholder!")
                                st.rerun()

                        # Multi-Database Discovery & Verification Links
                        aggr_links = get_card_aggregator_links(row["card_name"], row["set_name"], row["card_number"])
                        st.markdown("---")
                        st.markdown("**🌐 External Card Data & Scans:**")
                        c_a1, c_a2 = st.columns(2)
                        with c_a1:
                            st.markdown(f'<a href="{aggr_links["pricecharting"]}" target="_blank" class="btn-pc" style="display:block; text-align:center; padding: 5px; font-size:0.75rem; text-decoration:none; margin-bottom:6px;">📊 PriceCharting</a>', unsafe_allow_html=True)
                            st.markdown(f'<a href="{aggr_links["tcgcollector"]}" target="_blank" class="btn-ebay" style="display:block; text-align:center; padding: 5px; font-size:0.75rem; text-decoration:none; background:#0ea5e9;">🎴 TCGCollector</a>', unsafe_allow_html=True)
                        with c_a2:
                            st.markdown(f'<a href="{aggr_links["pokecardex"]}" target="_blank" class="btn-ebay" style="display:block; text-align:center; padding: 5px; font-size:0.75rem; text-decoration:none; margin-bottom:6px; background:#4b5563;">📖 Pokecardex</a>', unsafe_allow_html=True)
                            st.markdown(f'<a href="{aggr_links["pokemon_com"]}" target="_blank" class="btn-ebay" style="display:block; text-align:center; padding: 5px; font-size:0.75rem; text-decoration:none; background:#1e3a8a;">🌐 Pokemon.com</a>', unsafe_allow_html=True)
    else:
        disp_df = filtered_master[[
            "release_year", "card_name", "set_name", "card_number",
            "edition", "language", "pop_grade10", "est_raw_price", "est_grade10_price", "notes"
        ]].rename(columns={
            "release_year": "Year",
            "card_name": "Card Name",
            "set_name": "Set / Expansion",
            "card_number": "#",
            "edition": "Edition",
            "language": "Language",
            "pop_grade10": "PSA 10 Pop",
            "est_raw_price": "Est Raw ($)",
            "est_grade10_price": "Est 10 ($)",
            "notes": "Notes",
        })
        st.dataframe(disp_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ---------------------------------------------------------
    # Pre-Import Verification & Diagnostic Inspector
    # ---------------------------------------------------------
    st.markdown("#### 🔄 Sync 200+ Master Cards with Pre-Import Verification")

    with st.expander("🔍 **Pre-Import Verification & Diagnostic Inspector** (Click to Preview Before Syncing)", expanded=True):
        st.markdown(
            "This diagnostic inspector verifies cards from your spreadsheet, checks for 1st Edition stamps, separates error descriptions, filters out duplicate 'Code:' entries, and extracts verified card names before writing to the database."
        )

        sheet_url_input = st.text_input(
            "Google Sheet URL",
            value="https://docs.google.com/spreadsheets/d/12RkRdPNwbFly1SXmCS7DQkB5Q5zQZcPAnLX-P8M_vNA/edit?gid=0#gid=0",
        )

        prev_col1, prev_col2, prev_col3 = st.columns([1, 1.5, 1.5])
        with prev_col1:
            btn_preview = st.button("🔍 Run Verification Preview")
        with prev_col2:
            btn_clean_sync = st.button("🚀 Clean & Re-Import into Master Catalog", type="primary")
        with prev_col3:
            clean_csv_path = os.path.join(os.path.dirname(__file__), "..", "data", "vulpix_master_set_cleaned.csv")
            if os.path.exists(clean_csv_path):
                with open(clean_csv_path, "rb") as f:
                    st.download_button(
                        "📥 Download Clean 7-Col CSV",
                        data=f.read(),
                        file_name="vulpix_master_set_cleaned.csv",
                        mime="text/csv",
                        help="Filtered out 'Code:' entries and trimmed columns after Error/Notes.",
                    )

        if btn_preview or "preview_cache_df" in st.session_state:
            if btn_preview:
                with st.spinner("Downloading and verifying Google Sheet..."):
                    try:
                        doc_match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", sheet_url_input)
                        if doc_match:
                            doc_id = doc_match.group(1)
                            gid_match = re.search(r"[#&?]gid=([0-9]+)", sheet_url_input)
                            gid = gid_match.group(1) if gid_match else "0"
                            export_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid={gid}"
                            req = urllib.request.Request(export_url, headers={"User-Agent": "Mozilla/5.0"})
                            with urllib.request.urlopen(req, timeout=15) as resp:
                                content = resp.read().decode("utf-8")
                            df_raw = pd.read_csv(io.StringIO(content))
                            df_prev, stats = parse_and_preview_catalog(df_raw)
                            st.session_state["preview_cache_df"] = df_prev
                            st.session_state["preview_cache_stats"] = stats
                    except Exception as e:
                        st.error(f"Error previewing sheet: {e}")

            if "preview_cache_df" in st.session_state:
                df_prev = st.session_state["preview_cache_df"]
                stats = st.session_state["preview_cache_stats"]

                st.markdown(
                    f"**✨ Verification Result:** `{stats['total']} Cards Verified` • `🥇 {stats['first_ed']} 1st Edition` • `⚠️ {stats['errors']} Errors` • `🌐 {stats['languages']} Languages` • `📦 {stats['sets']} Sets` *(Filtered out e-Reader 'Code:' duplicates)*"
                )

                tab_p1, tab_p2, tab_p3 = st.tabs(["All Verified Cards", "🥇 1st Edition Cards", "⚠️ Error Cards"])
                with tab_p1:
                    st.dataframe(df_prev[["release_year", "card_name", "set_name", "card_number", "edition", "language", "error_description", "est_raw_price", "est_grade10_price"]], use_container_width=True, hide_index=True)
                with tab_p2:
                    st.dataframe(df_prev[df_prev["is_1st_edition"] == 1][["release_year", "card_name", "set_name", "card_number", "edition", "language", "est_raw_price", "est_grade10_price"]], use_container_width=True, hide_index=True)
        auto_import_col = st.checkbox("Also automatically import cards flagged as owned in sheet into Vault", value=False)

        if btn_clean_sync:
            with st.spinner("Purging old malformed records and cleanly populating verified cards..."):
                count, msg, _ = sync_from_google_sheets_url(sheet_url_input, auto_import_owned=auto_import_col)
                if count > 0:
                    st.success(f"✅ {msg}")
                    st.rerun()
                else:
                    st.error(msg)


# -------------------------------------------------------------
# TAB 3: eBay Sniper & Watchlist
# -------------------------------------------------------------
with tab_sniper:
    st.markdown("### 🎯 eBay Sniper & Auction Watchlist")
    st.markdown(
        "Paste any eBay listing URL or Item ID below. The sniper engine will automatically extract the card details, condition, fair market value, and bidding thresholds."
    )

    with st.expander("➕ Add eBay Auction by Link / Item ID", expanded=True):
        sn_col1, sn_col2 = st.columns([3, 2])
        with sn_col1:
            ebay_input_url = st.text_input(
                "🔗 eBay Listing Link or Item ID*",
                placeholder="Paste https://www.ebay.com/itm/... or item number",
                key="sniper_link_input",
            )
        with sn_col2:
            bid_mode_choice = st.selectbox(
                "🎯 Snipe Strategy",
                [
                    "🔥 Amazing Deal (~60% of Fair Value)",
                    "⭐ Great Deal (~75% of Fair Value)",
                    "💵 Custom Max Bid ($)",
                ],
                key="sniper_strat_choice",
            )

        custom_bid_val = 0.0
        if "Custom" in bid_mode_choice:
            custom_bid_val = st.number_input("Your Custom Max Bid ($)*", min_value=1.0, value=50.0, step=5.0, key="sniper_custom_max")

        if ebay_input_url:
            parsed = parse_ebay_url_details(ebay_input_url)

            # Determine target max bid based on selected mode
            if "Amazing" in bid_mode_choice:
                target_max = parsed["amazing_deal_max"]
                target_mode_code = "amazing_deal"
            elif "Great" in bid_mode_choice:
                target_max = parsed["great_deal_max"]
                target_mode_code = "great_deal"
            else:
                target_max = custom_bid_val if custom_bid_val > 0 else parsed["fair_value"]
                target_mode_code = "custom_max"

            st.markdown("---")
            st.markdown("#### 🔍 Auto-Detected Listing Preview")

            prev_col1, prev_col2 = st.columns([1, 4])
            with prev_col1:
                st.image(parsed["image_url"], width=120)
            with prev_col2:
                st.markdown(f"**🏷️ {parsed['title']}**")
                st.markdown(f"**Card:** `{parsed['card_name']}` • **Set:** `{parsed['set_name']}` • **Edition:** `{parsed['edition']}`")
                st.markdown(f"**Format:** `{parsed['condition_desc']}` • **Est. Fair Value:** `${parsed['fair_value']:,.2f}`")
                st.markdown(
                    f"🎯 **Calculated Max Snipe Bid:** <span style='color: #4ade80; font-weight: 800; font-size: 1.15rem;'>${target_max:,.2f}</span>",
                    unsafe_allow_html=True,
                )

            with st.expander("⚙️ Adjust Listing Details (Optional)", expanded=False):
                e_title = st.text_input("Auction Title", value=parsed["title"], key="sn_edit_title")
                e_bid = st.number_input("Current Bid ($)", min_value=0.0, value=parsed["current_bid"], step=2.0, key="sn_edit_bid")
                e_ship = st.number_input("Shipping ($)", min_value=0.0, value=parsed["shipping_cost"], step=0.5, key="sn_edit_ship")
                e_end = st.text_input("Auction End Time", value=parsed["auction_end_time"], key="sn_edit_end")
                e_notes = st.text_input("Sniper Notes / Bidding Strategy", value=f"Targeting {bid_mode_choice} with max bid ${target_max:,.2f}", key="sn_edit_notes")

            if st.button("🎯 Confirm & Start Sniping", type="primary", use_container_width=True):
                final_title = e_title if "e_title" in locals() and e_title else parsed["title"]
                final_bid = e_bid if "e_bid" in locals() else parsed["current_bid"]
                final_ship = e_ship if "e_ship" in locals() else parsed["shipping_cost"]
                final_end = e_end if "e_end" in locals() and e_end else parsed["auction_end_time"]
                final_notes = e_notes if "e_notes" in locals() and e_notes else f"Auto-sniping with {bid_mode_choice}"

                add_to_sniper_watchlist({
                    "listing_id": parsed["listing_id"],
                    "card_name": parsed["card_name"],
                    "title": final_title,
                    "listing_url": parsed["listing_url"],
                    "image_url": parsed["image_url"],
                    "auction_end_time": final_end,
                    "current_bid": final_bid,
                    "shipping_cost": final_ship,
                    "target_bid_mode": target_mode_code,
                    "custom_max_bid": target_max if target_mode_code == "custom_max" else None,
                    "max_calculated_bid": target_max,
                    "status": "watching",
                    "notes": final_notes,
                })
                st.success(f"✅ Auction '{final_title}' added to Sniper Watchlist with Max Bid: ${target_max:,.2f}!")
                st.rerun()

    if df_sniper.empty:
        st.info("💡 No active auctions on your Sniper Watchlist. Add an auction above or click 'Snipe' from the Deal Radar!")
    else:
        st.markdown(f"#### 🎯 Active Sniper Targets ({len(df_sniper)} Watching)")
        for _, s_row in df_sniper.iterrows():
            s_img = s_row.get("image_url") or DEFAULT_CARD_BACK_IMAGE
            target_bid_val = s_row["max_calculated_bid"] or s_row["custom_max_bid"] or (s_row["current_bid"] * 1.5)
            
            st.markdown(f"""<div class="sniper-card">
<div style="display: flex; gap: 14px; align-items: center;">
<img src="{s_img}" style="height: 70px; width: 50px; object-fit: cover; border-radius: 4px;" />
<div style="flex: 1;">
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
<div style="font-weight: 800; font-size: 1.02rem; color: #ffffff;">{s_row['title']}</div>
<span class="sniper-badge-alert">● SNIPER ACTIVE</span>
</div>
<div style="display: flex; gap: 16px; font-size: 0.85rem; color: #8c8d9a; flex-wrap: wrap; margin-bottom: 6px;">
<span>Current Bid: <strong style="color: #ffd591;">${s_row['current_bid']:,.2f}</strong> (+${s_row['shipping_cost']:,.2f} ship)</span>
<span>Target Max Bid: <strong style="color: #4ade80;">${target_bid_val:,.2f}</strong></span>
<span>Strategy: <strong style="color: #60a5fa;">{s_row['target_bid_mode'].replace('_', ' ').title()}</strong></span>
<span>Ends: <strong style="color: #fff;">{s_row['auction_end_time']}</strong></span>
</div>
<div>
<a href="{s_row['listing_url']}" target="_blank" class="btn-ebay" style="padding: 4px 10px; font-size: 0.8rem;">↗ Open Live Listing on eBay</a>
</div>
</div>
</div>
</div>""", unsafe_allow_html=True)
            if st.button("🗑️ Remove from Watchlist", key=f"del_sn_{s_row['id']}"):
                delete_from_sniper_watchlist(s_row["id"])
                st.rerun()


# -------------------------------------------------------------
# TAB 4: AI Deal Radar
# -------------------------------------------------------------
with tab_deals:
    st.markdown("### 🔥 Multi-Tier AI Deal Radar")
    st.markdown(
        "Real-time market scanner ranking live eBay listings using Gaussian Fair Value estimates. Filter by **Amazing Deals** (>=40% discount) or **Great Deals** (>=25% discount)."
    )

    d_col1, d_col2 = st.columns(2)
    with d_col1:
        deal_tier_sel = st.selectbox("Deal Tier Filter", ["All High-Conviction Deals", "🔥 Amazing Deals (>=40% Off)", "⭐ Great Deals (>=25% Off)"])
    with d_col2:
        deal_cond_sel = st.selectbox("Card Format Filter", ["All Formats", "Grade 10 Slabs Only", "Raw Singles Only"])

    tier_map = {
        "All High-Conviction Deals": "all_deals",
        "🔥 Amazing Deals (>=40% Off)": "amazing_deal",
        "⭐ Great Deals (>=25% Off)": "great_and_amazing",
    }
    df_deals = load_deals_df(deal_filter=tier_map[deal_tier_sel], condition_filter=deal_cond_sel)

    if df_deals.empty:
        st.info("💡 No deals currently match this filter. The scraper daemon evaluates eBay every few minutes!")
    else:
        st.markdown(f"**Found {len(df_deals)} Active Deals**")
        d_grid = st.columns(3)
        for d_idx, d_row in df_deals.iterrows():
            d_target = d_grid[d_idx % 3]
            with d_target:
                rating = d_row["deal_rating"]
                badge_cls = "deal-amazing" if rating == "amazing_deal" else ("deal-great" if rating == "great_deal" else "deal-good")
                badge_text = "🔥 AMAZING DEAL" if rating == "amazing_deal" else ("⭐ GREAT DEAL" if rating == "great_deal" else "GOOD DEAL")

                st.markdown(f"""<div class="slab-box">
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
<span class="{badge_cls}">{badge_text}</span>
<span style="font-weight: 800; color: #4ade80; font-size: 0.95rem;">{d_row['discount_percentage']:.1f}% OFF</span>
</div>
<div style="font-weight: 800; font-size: 0.98rem; color: #ffffff; margin-bottom: 4px;">{d_row['title']}</div>
<div style="background: #111217; padding: 8px; border-radius: 8px; font-size: 0.82rem; margin: 8px 0;">
<div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
<span style="color: #8c8d9a;">Listing Price:</span>
<span style="color: #fff; font-weight: 700;">${d_row['total_price']:,.2f}</span>
</div>
<div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
<span style="color: #8c8d9a;">Fair Value Est:</span>
<span style="color: #ffd591; font-weight: 700;">${d_row['fair_value_estimate']:,.2f}</span>
</div>
</div>
<div style="font-size: 0.78rem; color: #94a3b8; font-style: italic; margin-bottom: 8px;">
"{d_row['ai_rationale']}"
</div>
<a href="{d_row['listing_url']}" target="_blank" class="btn-ebay" style="width: 100%; text-align: center; display: block; box-sizing: border-box;">
🛒 Buy / View on eBay ↗
</a>
</div>""", unsafe_allow_html=True)


# -------------------------------------------------------------
# TAB 5: Market Sales Explorer
# -------------------------------------------------------------
with tab_market:
    st.markdown("### 📊 Market Sales & Historical Price Explorer")

    if df_market.empty:
        st.info("💡 Historical sales data will populate automatically as the scraper runs.")
    else:
        st.markdown(f"**Total Tracked Sales & Listings:** `{len(df_market)}`")
        fig = px.scatter(
            df_market,
            x="sale_date",
            y="total_price",
            color="condition_type",
            size="total_price",
            hover_data=["title", "grading_company", "grade", "deal_rating"],
            title="Recent Vulpix Sales & Market Listings",
            template="plotly_dark",
        )
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(
            df_market[[
                "card_name", "title", "grading_company", "grade", "condition_type",
                "total_price", "deal_rating", "discount_percentage", "sale_date", "listing_url"
            ]].rename(columns={
                "card_name": "Card",
                "title": "Title",
                "grading_company": "Grader",
                "grade": "Grade",
                "condition_type": "Format",
                "total_price": "Price ($)",
                "deal_rating": "Deal Rating",
                "discount_percentage": "Discount (%)",
                "sale_date": "Date",
                "listing_url": "URL",
            }),
            use_container_width=True,
            hide_index=True,
        )


# -------------------------------------------------------------
# TAB 6: System Controls & Gotify Sync
# -------------------------------------------------------------
with tab_settings:
    st.markdown("### ⚙️ System Controls & Diagnostics")

    col_s1, col_s2 = st.columns(2)

    with col_s1:
        st.markdown("#### 🗄️ Database Diagnostics")
        db_path = get_db_path()
        file_size_kb = round(os.path.getsize(db_path) / 1024, 2) if os.path.exists(db_path) else 0

        st.markdown(f"- **Database Path:** `{db_path}`")
        st.markdown(f"- **Database File Size:** `{file_size_kb} KB`")
        st.markdown(f"- **Master Set Catalog:** `{master_metrics['total_cards']} unique cards`")
        st.markdown(f"- **Personal Vault Records:** `{len(df_col)} items`")
        st.markdown(f"- **Sniper Watchlist:** `{len(df_sniper)} active targets`")
        st.markdown(f"- **Historical Sales Records:** `{len(df_market)} listings`")

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
                        "edition": "1st Edition",
                        "language": "English",
                        "total_price": 95.00,
                        "price": 95.00,
                        "listing_url": "https://www.ebay.com",
                    }
                    test_appraisal = {
                        "deal_rating": "amazing_deal",
                        "fair_value_estimate": 240.00,
                        "discount_percentage": 60.4,
                        "rationale": f"Live test push alert verified from Vulpix Vault Dashboard to Gotify.",
                    }
                    res = send_gotify_alert(test_listing, test_appraisal, gotify_url=in_url, gotify_token=in_token)
                    if res:
                        st.success(f"✅ Push notification successfully delivered to Gotify ({in_url}) and saved!")
                    else:
                        st.error(f"❌ Could not deliver push alert. Attempted: {in_url}, http://gotify:80, and http://10.0.0.48:8070. Please verify your Gotify App Token.")
                else:
                    st.error("Please enter a valid Gotify Application Token.")
