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
    send_gotify_alert,
    set_system_setting,
    sync_from_google_sheets_url,
    sync_master_catalog_from_df,
    update_card_image_override,
    update_collection_card,
    update_master_card,
)
from styles import apply_custom_styles, get_grading_badge_html, get_pop_badge_html, render_header

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
# Top KPI Header Metrics
# -------------------------------------------------------------
kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

with kpi1:
    st.markdown(
        f"""<div class="kpi-card">
<div class="kpi-label">Master Set Progress</div>
<div class="kpi-value" style="color: #10b981;">{master_metrics['completion_pct']}%</div>
<div style="color: #94a3b8; font-size: 0.82rem;">{master_metrics['owned_cards']} / {master_metrics['total_cards']} Unique Cards</div>
</div>""",
        unsafe_allow_html=True,
    )

with kpi2:
    st.markdown(
        f"""<div class="kpi-card">
<div class="kpi-label">Cost to Finish Master Set</div>
<div class="kpi-value" style="font-size: 1.35rem; color: #ffd591;">${master_metrics['cost_to_complete_raw']:,.2f} <span style="font-size: 0.8rem; color: #94a3b8;">(Raw)</span></div>
<div style="color: #f59e0b; font-size: 0.8rem; font-weight: 600;">${master_metrics['cost_to_complete_grade10']:,.2f} in Grade 10</div>
</div>""",
        unsafe_allow_html=True,
    )

with kpi3:
    st.markdown(
        f"""<div class="kpi-card">
<div class="kpi-label">Vault Portfolio Value</div>
<div class="kpi-value">${port_metrics['total_value']:,.2f}</div>
<div style="color: #8c8d9a; font-size: 0.82rem;">Cost Basis: ${port_metrics['total_cost']:,.2f}</div>
</div>""",
        unsafe_allow_html=True,
    )

with kpi4:
    gain_class = "kpi-delta-pos" if port_metrics["net_gain"] >= 0 else "kpi-delta-neg"
    sign = "+" if port_metrics["net_gain"] >= 0 else ""
    st.markdown(
        f"""<div class="kpi-card">
<div class="kpi-label">Net Gain / ROI</div>
<div class="kpi-value">{sign}${port_metrics['net_gain']:,.2f}</div>
<div class="{gain_class}">{sign}{port_metrics['roi_percent']:.1f}% Total ROI</div>
</div>""",
        unsafe_allow_html=True,
    )

with kpi5:
    st.markdown(
        f"""<div class="kpi-card">
<div class="kpi-label">Active Sniper & Deals</div>
<div class="kpi-value" style="color: #ff7a45;">{len(df_sniper)} / {port_metrics['amazing_deals_count'] + port_metrics['great_deals_count']}</div>
<div style="color: #ff7a45; font-size: 0.82rem; font-weight: 600;">🎯 {len(df_sniper)} Snipers • 🔥 {port_metrics['amazing_deals_count']} Amazing</div>
</div>""",
        unsafe_allow_html=True,
    )

st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

# -------------------------------------------------------------
# Main Navigation Tabs
# -------------------------------------------------------------
tab_vault, tab_master, tab_sniper, tab_trends, tab_deals, tab_settings = st.tabs([
    "🦊 My Graded & Raw Vault",
    "📜 Master Set Checklist",
    "🎯 eBay Sniper Watchlist",
    "📈 Market Price Trends",
    "🔥 AI Deal Radar",
    "⚙️ System Controls & Sync",
])

# -------------------------------------------------------------
# TAB 1: My Graded & Raw Vault
# -------------------------------------------------------------
with tab_vault:
    st.markdown("### 🏆 Personal Vulpix Collection")

    # Add Card or Bulk CSV Import
    col_v_act1, col_v_act2 = st.columns([1, 1])

    with col_v_act1:
        with st.expander("➕ Add Single Card or Slab to Vault", expanded=False):
            with st.form("add_card_vault_form", clear_on_submit=True):
                f1, f2, f3 = st.columns(3)
                with f1:
                    f_card_name = st.text_input("Card Name", placeholder="e.g. Vulpix or Erika's Vulpix")
                    f_set_name = st.text_input("Set Name", placeholder="e.g. Base Set or Gym Heroes")
                    f_card_num = st.text_input("Card Number", placeholder="e.g. 68/102")
                    f_edition = st.selectbox("Edition / Variant", ["Unlimited", "1st Edition", "Shadowless", "Reverse Holo", "Promo", "1st Print"])
                with f2:
                    f_condition = st.radio("Condition", ["Graded Slab", "Raw Single"], horizontal=True)
                    f_is_raw = 1 if f_condition == "Raw Single" else 0
                    f_co = st.selectbox("Grading Company", ["PSA", "CGC", "BGS", "ARS", "ACE", "SGC", "RAW"]) if not f_is_raw else "RAW"
                    f_grade_label = st.selectbox("Grade Tier", ["Gem Mint", "Pristine 10", "Black Label 10", "Mint", "Near Mint", "Raw Single"])
                    f_grade_num = st.number_input("Numerical Grade", min_value=1.0, max_value=10.0, value=10.0, step=0.5) if not f_is_raw else 0.0
                    f_cert = st.text_input("Certification Number", placeholder="e.g. 48291039") if not f_is_raw else ""
                    f_pop = st.number_input("PSA/CGC Pop (Grade 10 Count)", min_value=0, value=0, step=1)
                with f3:
                    f_lang = st.selectbox("Language", ["English", "Japanese", "German", "French", "Italian", "Spanish", "Korean", "Chinese"])
                    f_price = st.number_input("Purchase Price ($ USD)", min_value=0.0, value=25.0, step=5.0)
                    f_date = st.date_input("Purchase Date", value=datetime.today())
                    f_img = st.text_input("Card Image URL (optional)", placeholder="https://...")

                st.markdown("---")
                e1, e2 = st.columns([1, 3])
                with e1:
                    f_is_err = st.checkbox("⚠️ Is Error Card?")
                with e2:
                    f_err_type = st.text_input("Error Type (if applicable)", placeholder="e.g. HP 50 Error, No Rarity Symbol...")

                f_notes = st.text_area("Collector Notes", placeholder="Subgrades, provenance, or condition details...")

                submit_card = st.form_submit_button("Save Card to Vault")
                if submit_card:
                    if f_card_name:
                        add_card_to_collection({
                            "card_name": f_card_name,
                            "set_name": f_set_name or "Unknown Set",
                            "card_number": f_card_num or "",
                            "grading_company": f_co,
                            "grade": f_grade_num,
                            "grade_label": f_grade_label,
                            "cert_number": f_cert,
                            "purchase_price": f_price,
                            "purchase_date": f_date.strftime("%Y-%m-%d"),
                            "edition": f_edition,
                            "language": f_lang,
                            "is_error": 1 if f_is_err else 0,
                            "error_type": f_err_type if f_is_err else None,
                            "is_raw": f_is_raw,
                            "pop_grade10": int(f_pop),
                            "image_url": f_img or "https://images.pokemontcg.io/base1/68_hires.png",
                            "notes": f_notes or "",
                        })
                        st.success(f"Added {f_card_name} ({f_edition} - {f_grade_label}) to Vault!")
                        st.rerun()
                    else:
                        st.error("Please provide a Card Name.")

    with col_v_act2:
        with st.expander("📥 Bulk Import Owned Cards (CSV File)", expanded=False):
            st.markdown("Upload a CSV list of cards in your collection to import them in bulk:")
            vault_csv = st.file_uploader("Upload Collection CSV", type=["csv"], key="vault_csv_up")
            if vault_csv is not None:
                if st.button("📥 Import Collection CSV"):
                    try:
                        df_v_csv = pd.read_csv(vault_csv)
                        cnt, v_msg = bulk_import_collection_from_df(df_v_csv)
                        st.success(v_msg)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error importing CSV: {e}")

    # View Mode Selector
    v_mode_col1, v_mode_col2 = st.columns([2, 1])
    with v_mode_col2:
        vault_view_mode = st.radio("Display Layout:", ["🃏 Card Grid View", "📋 Table / List View"], horizontal=True, key="vault_v_mode")

    if df_col.empty:
        st.info("Your vault is empty. Add cards manually or bulk-import a CSV above!")
    else:
        if "Card Grid" in vault_view_mode:
            cols = st.columns(3)
            for idx, row in df_col.iterrows():
                col_target = cols[idx % 3]
                with col_target:
                    badge_html = get_grading_badge_html(
                        row.get("grading_company", "PSA"),
                        row.get("grade", 10),
                        row.get("grade_label", "Gem Mint"),
                        row.get("is_raw", 0),
                    )
                    pop_badge_html = get_pop_badge_html(int(row.get("pop_grade10") or 0), int(row.get("pop_pristine10") or 0))
                    gain = row.get("unrealized_gain", 0.0)
                    roi = row.get("roi_percent", 0.0)
                    gain_color = "#4ade80" if gain >= 0 else "#f87171"
                    gain_sign = "+" if gain >= 0 else ""
                    error_badge = '<span class="badge-error">⚠️ ERROR</span>' if row.get("is_error") == 1 else ""
                    img_src = row["image_url"] if row["image_url"] else "https://images.pokemontcg.io/base1/68_hires.png"

                    # Generate live eBay & PriceCharting links
                    ebay_search_link = generate_ebay_search_url(
                        card_name=row["card_name"],
                        set_name=row["set_name"],
                        card_number=row["card_number"],
                        edition=row.get("edition", ""),
                        language=row.get("language", "English"),
                        is_raw=bool(row.get("is_raw", 0)),
                        grade_tier=row.get("grade_label"),
                    )
                    pc_search_link = get_pricecharting_search_url(row["card_name"], row["set_name"], row["card_number"])
                    psa_cert_link = get_psa_cert_lookup_url(str(row.get("cert_number", "")))

                    # Format Cert or Slab indicator (DO NOT display 'Raw' for graded slabs)
                    if row.get("cert_number"):
                        cert_label_html = f'<a href="{psa_cert_link}" target="_blank" style="color: #94a3b8; font-size: 0.72rem; text-decoration: underline;">Cert #{row["cert_number"]}</a>'
                    elif row.get("is_raw") == 1 or str(row.get("grading_company", "")).upper() == "RAW":
                        cert_label_html = '<span style="font-size: 0.72rem; color: #666;">Raw Single</span>'
                    else:
                        cert_label_html = '<span style="font-size: 0.72rem; color: #8c8d9a;">Graded Slab</span>'

                    card_box_html = f"""<div class="slab-box">
<div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
<div>
<div style="font-weight: 800; font-size: 1.05rem; color: #fff;">{row['card_name']}</div>
<div style="color: #8c8d9a; font-size: 0.82rem;">{row['set_name']} • #{row['card_number']} ({row.get('edition', 'Unlimited')})</div>
</div>
<div style="text-align: right;">
{badge_html}
<div style="margin-top: 4px;">{pop_badge_html} {error_badge}</div>
</div>
</div>
<div style="text-align: center; margin: 10px 0;">
<img src="{img_src}" style="max-height: 165px; max-width: 100%; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.5);" />
</div>
<div style="background: #111217; padding: 8px 12px; border-radius: 8px; margin-top: 8px; font-size: 0.82rem;">
<div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
<span style="color: #8c8d9a;">Language:</span>
<span style="color: #ffffff; font-weight: 600;">{row.get('language', 'English')}</span>
</div>
<div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
<span style="color: #8c8d9a;">Cost Basis:</span>
<span style="color: #ffffff; font-weight: 600;">${row['purchase_price']:,.2f}</span>
</div>
<div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
<span style="color: #8c8d9a;">Market Est:</span>
<span style="color: #ffd591; font-weight: 700;">${row['current_market_value']:,.2f}</span>
</div>
<div style="display: flex; justify-content: space-between;">
<span style="color: #8c8d9a;">Gain / ROI:</span>
<span style="color: {gain_color}; font-weight: 700;">{gain_sign}${gain:,.2f} ({gain_sign}{roi:.1f}%)</span>
</div>
</div>
<div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px; gap: 4px;">
<a href="{ebay_search_link}" target="_blank" class="btn-ebay">
🔍 Live eBay →
</a>
<a href="{pc_search_link}" target="_blank" class="btn-pc">
📊 PriceCharting
</a>
{cert_label_html}
</div>
</div>"""

                    st.markdown(card_box_html, unsafe_allow_html=True)

                    btn_c1, btn_c2 = st.columns(2)
                    with btn_c1:
                        with st.popover("✏️ Edit Card"):
                            with st.form(f"edit_form_{row['id']}"):
                                ed_name = st.text_input("Card Name", value=str(row["card_name"]))
                                ed_set = st.text_input("Set Name", value=str(row["set_name"]))
                                ed_num = st.text_input("Card Number", value=str(row["card_number"]))
                                ed_co = st.selectbox("Grading Company", ["PSA", "CGC", "BGS", "ARS", "ACE", "SGC", "RAW"], index=["PSA", "CGC", "BGS", "ARS", "ACE", "SGC", "RAW"].index(row["grading_company"]) if row["grading_company"] in ["PSA", "CGC", "BGS", "ARS", "ACE", "SGC", "RAW"] else 0)
                                ed_grade = st.number_input("Grade", min_value=0.0, max_value=10.0, value=float(row.get("grade", 10.0)), step=0.5)
                                ed_tier = st.selectbox("Grade Label", ["Gem Mint", "Pristine 10", "Black Label 10", "Mint", "Near Mint", "Raw Single"])
                                ed_cert = st.text_input("Cert Number", value=str(row.get("cert_number", "")))
                                ed_pop = st.number_input("Pop (Grade 10 Count)", min_value=0, value=int(row.get("pop_grade10") or 0))
                                ed_price = st.number_input("Purchase Price ($)", min_value=0.0, value=float(row["purchase_price"]), step=5.0)
                                ed_img = st.text_input("Image URL", value=str(row.get("image_url", "")))
                                ed_notes = st.text_area("Notes", value=str(row.get("notes", "")))
                                if st.form_submit_button("Update Slab"):
                                    update_collection_card(row["id"], {
                                        "card_name": ed_name,
                                        "set_name": ed_set,
                                        "card_number": ed_num,
                                        "grading_company": ed_co,
                                        "grade": ed_grade,
                                        "grade_label": ed_tier,
                                        "cert_number": ed_cert,
                                        "purchase_price": ed_price,
                                        "purchase_date": str(row.get("purchase_date", "2024-01-01")),
                                        "edition": str(row.get("edition", "Unlimited")),
                                        "language": str(row.get("language", "English")),
                                        "is_error": int(row.get("is_error", 0)),
                                        "error_type": row.get("error_type"),
                                        "is_raw": 1 if ed_co == "RAW" else 0,
                                        "pop_grade10": int(ed_pop),
                                        "image_url": ed_img,
                                        "notes": ed_notes,
                                    })
                                    st.success("Updated!")
                                    st.rerun()

                    with btn_c2:
                        if st.button("🗑️ Delete", key=f"del_{row['id']}"):
                            delete_card_from_collection(row["id"])
                            st.rerun()
        else:
            st.dataframe(
                df_col[[
                    "card_name", "set_name", "card_number", "grading_company",
                    "grade", "grade_label", "edition", "language", "pop_grade10", "purchase_price",
                    "current_market_value", "unrealized_gain", "roi_percent", "purchase_date", "notes"
                ]].rename(columns={
                    "card_name": "Card Name",
                    "set_name": "Set",
                    "card_number": "#",
                    "grading_company": "Grader",
                    "grade": "Grade",
                    "grade_label": "Grade Tier",
                    "edition": "Edition",
                    "language": "Lang",
                    "pop_grade10": "Pop (10)",
                    "purchase_price": "Cost ($)",
                    "current_market_value": "Market ($)",
                    "unrealized_gain": "Gain ($)",
                    "roi_percent": "ROI %",
                    "purchase_date": "Acquired",
                }),
                use_container_width=True,
                hide_index=True,
            )

# -------------------------------------------------------------
# TAB 2: Master Set Checklist & Google Sheets / CSV Column Mapper
# -------------------------------------------------------------
with tab_master:
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
            "💡 *Card name missing or just 'Vulpix'? Click to query Pokemon.com, Pokecardex & 200+ Master Index by set & card number to fill exact names (e.g. Blaine's Vulpix) and official card scans.*"
        )
    with en_col2:
        if st.button("⚡ Auto-Enrich Names & Images", key="btn_auto_enrich_master"):
            with st.spinner("Resolving missing card names and fetching high-res scans..."):
                cnt, msg = auto_enrich_master_catalog()
                st.success(msg)
                st.rerun()

    # Filter Controls
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1:
        m_view = st.selectbox("Status Filter", ["All Master Cards", "❌ Missing Cards Only", "✅ Owned Cards Only", "💎 Low Pop (<20 PSA 10)", "⚠️ Error Cards Only"])
    with m_col2:
        m_langs = ["All Languages"] + sorted(df_master["language"].dropna().unique().tolist())
        m_sel_lang = st.selectbox("Language Filter", m_langs)
    with m_col3:
        m_eds = ["All Editions"] + sorted(df_master["edition"].dropna().unique().tolist())
        m_sel_ed = st.selectbox("Edition Filter", m_eds)
    with m_col4:
        m_search = st.text_input("Search Set or Card Name", placeholder="e.g. Neo Destiny, CoroCoro...")

    # Filter DataFrame
    filtered_master = df_master.copy()
    if m_view == "❌ Missing Cards Only":
        filtered_master = filtered_master[~filtered_master["is_owned"]]
    elif m_view == "✅ Owned Cards Only":
        filtered_master = filtered_master[filtered_master["is_owned"]]
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
                err_badge = '<span class="badge-error" style="font-size: 0.68rem;">⚠️ ERROR</span>' if row["is_error"] == 1 else ""
                pop_badge = get_pop_badge_html(int(row.get("pop_grade10") or 0), int(row.get("pop_pristine10") or 0))
                img_src = row["image_url"] if row["image_url"] else "https://images.pokemontcg.io/base1/68_hires.png"

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

                # Render HTML unindented to prevent markdown code block bug
                master_card_html = f"""<div class="slab-box" style="padding: 12px; margin-bottom: 14px;">
<div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px;">
<div style="font-size: 0.78rem; font-weight: 700; color: #94a3b8;">{row['release_year']} • {row['language']}</div>
<div>{status_badge} {err_badge}</div>
</div>
<div style="text-align: center; margin: 8px 0;">
<img src="{img_src}" style="max-height: 155px; max-width: 100%; border-radius: 6px; box-shadow: 0 4px 10px rgba(0,0,0,0.5);" />
</div>
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px;">
<div style="font-weight: 800; font-size: 0.92rem; color: #ffffff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{row['card_name']}</div>
{pop_badge}
</div>
<div style="color: #8c8d9a; font-size: 0.78rem; margin-bottom: 8px;">{row['set_name']} #{row['card_number']} ({row['edition']})</div>
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
                act1, act2 = st.columns(2)
                with act1:
                    with st.popover("📥 Add to Vault"):
                        with st.form(f"quick_add_{row['id']}"):
                            st.markdown(f"**Add {row['card_name']} to Vault:**")
                            q_cond = st.radio("Condition", ["Raw Single", "Graded Slab"], horizontal=True)
                            q_co = st.selectbox("Grader", ["RAW", "PSA", "CGC", "BGS", "ARS", "ACE"]) if q_cond == "Graded Slab" else "RAW"
                            q_tier = st.selectbox("Grade Label", ["Raw Single", "Gem Mint", "Pristine 10", "Black Label 10", "Mint"])
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
                    with st.popover("✏️ Edit Card"):
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
                            em_notes = st.text_area("Notes / Error Description", value=row["notes"] or "")
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
    else:
        disp_df = filtered_master[[
            "is_owned", "release_year", "card_name", "set_name", "card_number",
            "edition", "language", "pop_grade10", "est_raw_price", "est_grade10_price", "notes"
        ]].copy()
        disp_df["Status"] = disp_df["is_owned"].apply(lambda x: "✅ OWNED" if x else "❌ MISSING")

        st.dataframe(
            disp_df[[
                "Status", "release_year", "card_name", "set_name", "card_number",
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
            }),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("---")
    st.markdown("#### 🔄 Sync 200+ Master Cards with Interactive Column Mapper")

    sync_col1, sync_col2 = st.columns(2)
    with sync_col1:
        st.markdown("##### 🌐 Sync via Google Sheets Link")
        sheet_url_input = st.text_input(
            "Google Sheet URL",
            value="https://docs.google.com/spreadsheets/d/12RkRdPNwbFly1SXmCS7DQkB5Q5zQZcPAnLX-P8M_vNA/edit?gid=0#gid=0",
        )
        if st.button("🔄 Sync Google Sheet into Catalog"):
            with st.spinner("Fetching and importing Google Sheet..."):
                count, msg, diags = sync_from_google_sheets_url(sheet_url_input)
                if count > 0:
                    st.success(msg)
                    st.rerun()
                else:
                    st.warning(msg)
                    st.info("💡 **Tip:** Set your Google Sheet share setting to *'Anyone with the link can view'*, or download as CSV and upload on the right.")

    with sync_col2:
        st.markdown("##### 📁 Upload CSV with Interactive Column Mapper")
        st.download_button(
            "📥 Download Starter CSV Template",
            data=get_csv_template_bytes(),
            file_name="vulpix_master_set_template.csv",
            mime="text/csv",
        )
        uploaded_csv = st.file_uploader("Choose your CSV file", type=["csv"], key="master_csv_up")
        if uploaded_csv is not None:
            try:
                df_up = pd.read_csv(uploaded_csv)
                st.markdown(f"**Found {len(df_up)} rows in CSV. Preview:**")
                st.dataframe(df_up.head(3), use_container_width=True)

                st.markdown("##### 🎛️ Confirm / Map Column Headers:")
                csv_cols = ["None"] + list(df_up.columns)
                
                # Smart fuzzy guess
                def guess_col(keywords, default_idx=0):
                    for idx, c in enumerate(csv_cols):
                        c_low = c.lower()
                        if any(k in c_low for k in keywords):
                            return idx
                    return default_idx

                map_c1, map_c2, map_c3 = st.columns(3)
                with map_c1:
                    map_card_name = st.selectbox("Card Name Column*", csv_cols, index=guess_col(["card name", "name", "pokemon"]))
                    map_set_name = st.selectbox("Set / Expansion Column*", csv_cols, index=guess_col(["set name", "set", "expansion"]))
                    map_card_num = st.selectbox("Card # Column", csv_cols, index=guess_col(["card number", "number", "card #", "#", "no"]))
                with map_c2:
                    map_edition = st.selectbox("Edition Column", csv_cols, index=guess_col(["edition", "variant", "ed"]))
                    map_language = st.selectbox("Language Column", csv_cols, index=guess_col(["language", "lang", "region"]))
                    map_is_error = st.selectbox("Error Flag Column", csv_cols, index=guess_col(["error", "is error"]))
                with map_c3:
                    map_raw_price = st.selectbox("Est Raw Price Column", csv_cols, index=guess_col(["raw price", "raw", "price", "market"]))
                    map_g10_price = st.selectbox("Est Grade 10 Price Column", csv_cols, index=guess_col(["grade 10", "psa 10", "10 price", "est 10"]))
                    map_owned = st.selectbox("Owned Status Column", csv_cols, index=guess_col(["owned", "have", "status"]))

                if st.button("🚀 Import Mapped CSV into Master Catalog"):
                    custom_map = {
                        "card_name": map_card_name,
                        "set_name": map_set_name,
                        "card_number": map_card_num,
                        "edition": map_edition,
                        "language": map_language,
                        "is_error": map_is_error,
                        "est_raw_price": map_raw_price,
                        "est_grade10_price": map_g10_price,
                        "owned_status": map_owned,
                    }
                    count, msg, diags = sync_master_catalog_from_df(df_up, custom_col_map=custom_map)
                    st.success(msg)
                    if diags:
                        with st.expander("Diagnostic Import Details"):
                            for d in diags[:20]:
                                st.write(d)
                    st.rerun()

            except Exception as e:
                st.error(f"Failed to parse CSV: {e}")

# -------------------------------------------------------------
# TAB 3: eBay Sniper & Watchlist
# -------------------------------------------------------------
with tab_sniper:
    st.markdown("### 🎯 eBay Sniper & Auction Watchlist")
    st.markdown(
        "Track active eBay auctions, set auto-bid caps based on **Amazing Deal** or **Great Deal** AI thresholds, and receive urgent push notifications before auctions close."
    )

    with st.expander("➕ Add Active eBay Auction to Sniper Watchlist", expanded=False):
        with st.form("add_sniper_form", clear_on_submit=True):
            sn1, sn2 = st.columns(2)
            with sn1:
                sn_card = st.selectbox("Target Master Card", ["Vulpix"] + [f"{r['card_name']} - {r['set_name']} ({r['edition']})" for _, r in df_master.iterrows()])
                sn_title = st.text_input("Auction Title", placeholder="e.g. 1999 Base Set 1st Edition Vulpix PSA 10")
                sn_url = st.text_input("eBay Listing URL*", placeholder="https://www.ebay.com/itm/1234567890")
            with sn2:
                sn_bid = st.number_input("Current Bid ($)", min_value=0.0, value=15.0, step=5.0)
                sn_ship = st.number_input("Shipping Cost ($)", min_value=0.0, value=4.99, step=1.0)
                sn_strat = st.selectbox("Max Bid Strategy", ["🔥 Amazing Deal Cap (30% Off Fair Value)", "⭐ Great Deal Cap (15% Off Fair Value)", "Custom Max Dollar Amount"])
                sn_custom_max = st.number_input("Custom Max Bid ($) (if selected)", min_value=0.0, value=50.0, step=5.0)

            sn_end = st.text_input("Auction End Date/Time (optional)", placeholder="2026-08-30 18:00:00")
            sn_notes = st.text_area("Notes", placeholder="Seller feedback, condition checks, or subgrades...")

            if st.form_submit_button("Add to Sniper Watchlist"):
                if sn_url:
                    item_id_match = re.search(r"/itm/(?:[a-zA-Z0-9\-_]+/)?([0-9]{9,15})", sn_url)
                    listing_id = item_id_match.group(1) if item_id_match else f"manual_snip_{int(datetime.now().timestamp())}"

                    add_to_sniper_watchlist({
                        "listing_id": listing_id,
                        "card_name": sn_card.split(" - ")[0],
                        "title": sn_title or f"Auction for {sn_card}",
                        "listing_url": sn_url,
                        "image_url": "https://images.pokemontcg.io/base1/68_hires.png",
                        "auction_end_time": sn_end or datetime.today().strftime("%Y-%m-%d %H:%M:%S"),
                        "current_bid": sn_bid,
                        "shipping_cost": sn_ship,
                        "target_bid_mode": "custom_max" if "Custom" in sn_strat else ("amazing_deal" if "Amazing" in sn_strat else "great_deal"),
                        "custom_max_bid": sn_custom_max,
                        "status": "watching",
                        "notes": sn_notes,
                    })
                    st.success("Added to Sniper Watchlist!")
                    st.rerun()
                else:
                    st.error("Please enter an eBay listing URL.")

    # Active Watchlist Display
    if df_sniper.empty:
        st.info("Your Sniper Watchlist is currently empty. Add auctions using the form above!")
    else:
        st.markdown(f"**Tracking {len(df_sniper)} active auction targets:**")
        for _, sn in df_sniper.iterrows():
            curr_bid = float(sn["current_bid"])
            max_bid = float(sn.get("custom_max_bid") or 100.0)
            is_under = curr_bid <= max_bid
            badge_sn = '<span class="sniper-badge-ok">🟢 BID UNDER CAP</span>' if is_under else '<span class="sniper-badge-alert">🔴 EXCEEDS MAX CAP</span>'

            with st.container():
                st.markdown(
                    f"""<div class="sniper-card">
<div style="display: flex; justify-content: space-between; align-items: center;">
<div>
{badge_sn}
<span style="font-weight: 800; font-size: 1.1rem; color: #fff; margin-left: 8px;">{sn['title']}</span>
</div>
<div>
<span style="color: #8c8d9a; font-size: 0.82rem;">Current Bid: </span>
<span style="font-size: 1.3rem; font-weight: 800; color: #4ade80;">${curr_bid:,.2f}</span>
</div>
</div>
<div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; background: #111217; padding: 10px 14px; border-radius: 8px; margin: 10px 0; font-size: 0.85rem;">
<div>
<span style="color: #8c8d9a;">Target Card:</span> <strong style="color: #fff;">{sn['card_name']}</strong>
</div>
<div>
<span style="color: #8c8d9a;">Max Bid Cap:</span> <strong style="color: #ffd591;">${max_bid:,.2f}</strong>
</div>
<div>
<span style="color: #8c8d9a;">Auction Closes:</span> <strong style="color: #f59e0b;">{sn['auction_end_time'] or 'Ongoing'}</strong>
</div>
</div>
<div style="display: flex; justify-content: space-between; align-items: center;">
<span style="color: #94a3b8; font-size: 0.8rem;">{sn['notes'] or ''}</span>
<div style="display: flex; gap: 8px;">
<a href="{sn['listing_url']}" target="_blank" class="btn-ebay" style="background: linear-gradient(135deg, #ef4444, #dc2626);">
⚡ Place Bid on eBay →
</a>
</div>
</div>
</div>""",
                    unsafe_allow_html=True,
                )
                if st.button("🗑️ Remove Target", key=f"del_snip_{sn['id']}"):
                    delete_from_sniper_watchlist(sn["id"])
                    st.rerun()

# -------------------------------------------------------------
# TAB 4: Market Price Trends
# -------------------------------------------------------------
with tab_trends:
    st.markdown("### 📈 Market Sales & Price Analytics")

    if df_market.empty:
        st.info("No market sales recorded yet.")
    else:
        f1, f2, f3 = st.columns(3)
        with f1:
            all_variants = ["All Cards"] + sorted(df_market["card_name"].dropna().unique().tolist())
            selected_variant = st.selectbox("Filter by Card Variant", all_variants)
        with f2:
            all_conds = ["All Conditions", "Grade 10 Slabs", "Raw Singles"]
            selected_cond = st.selectbox("Condition / Tier", all_conds)
        with f3:
            all_cos = ["All Grading Companies"] + sorted([c for c in df_market["grading_company"].dropna().unique() if c != "RAW"])
            selected_co = st.selectbox("Grading Company", all_cos)

        filtered_df = df_market.copy()
        if selected_variant != "All Cards":
            filtered_df = filtered_df[filtered_df["card_name"] == selected_variant]
        if selected_cond == "Grade 10 Slabs":
            filtered_df = filtered_df[(filtered_df["condition_type"] == "Graded") & (filtered_df["grade"] == 10.0)]
        elif selected_cond == "Raw Singles":
            filtered_df = filtered_df[filtered_df["condition_type"] == "Raw"]
        if selected_co != "All Grading Companies":
            filtered_df = filtered_df[filtered_df["grading_company"] == selected_co]

        if not filtered_df.empty:
            filtered_df["display_date"] = pd.to_datetime(
                filtered_df["sale_date"].fillna(filtered_df["scraped_at"])
            )
            filtered_df = filtered_df.sort_values(by="display_date")

            fig = px.scatter(
                filtered_df,
                x="display_date",
                y="total_price",
                color="grade_label",
                symbol="condition_type",
                hover_data=["title", "total_price", "edition", "language", "deal_rating"],
                labels={
                    "display_date": "Sale / Scraped Date",
                    "total_price": "Price ($ USD)",
                    "grade_label": "Grade / Label",
                },
                title="Historical Sales & Listing Trajectory (Raw vs Slabs)",
                template="plotly_dark",
            )
            fig.update_traces(marker=dict(size=9, line=dict(width=1, color="DarkSlateGrey")))
            fig.update_layout(
                paper_bgcolor="#181920",
                plot_bgcolor="#14151b",
                hovermode="closest",
                margin=dict(l=20, r=20, t=50, b=20),
            )
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(
                filtered_df[[
                    "sale_date", "card_name", "condition_type", "grading_company",
                    "grade_label", "edition", "language", "total_price", "deal_rating", "title"
                ]].rename(columns={
                    "sale_date": "Date",
                    "card_name": "Card",
                    "condition_type": "Condition",
                    "grading_company": "Company",
                    "grade_label": "Grade Label",
                    "edition": "Edition",
                    "language": "Lang",
                    "total_price": "Price ($)",
                    "deal_rating": "Appraisal",
                    "title": "eBay Listing Title",
                }),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.warning("No sales matched the selected filters.")

# -------------------------------------------------------------
# TAB 5: AI Deal Radar
# -------------------------------------------------------------
with tab_deals:
    st.markdown("### 🔥 Google Gemini AI Deal Radar")
    st.markdown(
        "Automated appraisal engine scans every scraped eBay listing against recent sales to flag deals across Grade 10 slabs and Raw singles."
    )

    d_col1, d_col2 = st.columns(2)
    with d_col1:
        deal_tier_opt = st.radio(
            "Deal Tier Filter:",
            ["🔥 Amazing Deals (>=30% Off)", "⭐ Great & Amazing Deals (>=15% Off)", "All Value Deals (Amazing/Great/Good)", "All Listings"],
            horizontal=True,
        )
    with d_col2:
        deal_cond_opt = st.selectbox("Condition Filter:", ["All Conditions", "Grade 10 Slabs Only", "Raw Singles Only"])

    tier_map = {
        "🔥 Amazing Deals (>=30% Off)": "amazing_deal",
        "⭐ Great & Amazing Deals (>=15% Off)": "great_and_amazing",
        "All Value Deals (Amazing/Great/Good)": "all_deals",
        "All Listings": None,
    }

    df_deals = load_deals_df(deal_filter=tier_map.get(deal_tier_opt), condition_filter=deal_cond_opt)

    if df_deals.empty:
        st.info("No active deals found matching your filter criteria right now.")
    else:
        st.markdown(f"**Found {len(df_deals)} deals matching criteria:**")
        for _, deal in df_deals.iterrows():
            rating = deal.get("deal_rating", "unrated")
            if rating == "amazing_deal":
                badge_deal = '<span class="deal-amazing">🔥 AMAZING DEAL</span>'
                border_color = '#ef4444'
            elif rating == "great_deal":
                badge_deal = '<span class="deal-great">⭐ GREAT DEAL</span>'
                border_color = '#f59e0b'
            else:
                badge_deal = '<span class="deal-good">✨ GOOD DEAL</span>'
                border_color = '#22c55e'

            grading_badge = get_grading_badge_html(
                deal["grading_company"],
                deal["grade"],
                deal.get("grade_label", "Gem Mint"),
                1 if deal.get("condition_type") == "Raw" else 0,
            )

            discount = deal.get("discount_percentage", 0.0) or 0.0
            fair_val = deal.get("fair_value_estimate", deal["total_price"]) or deal["total_price"]
            rationale = deal.get("ai_rationale") or "AI appraisal calculated from comparable market sales."

            with st.container():
                st.markdown(
                    f"""<div style="background: #181920; border: 1px solid {border_color}; border-radius: 12px; padding: 16px; margin-bottom: 14px;">
<div style="display: flex; justify-content: space-between; align-items: center;">
<div>
{badge_deal} &nbsp; {grading_badge}
<span style="font-weight: 800; font-size: 1.1rem; color: #fff; margin-left: 6px;">{deal['title']}</span>
</div>
<div style="text-align: right;">
<span style="color: #8c8d9a; font-size: 0.82rem;">Listed: </span>
<span style="font-size: 1.25rem; font-weight: 800; color: #4ade80;">${deal['total_price']:,.2f}</span>
</div>
</div>
<div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 10px; background: #111217; padding: 10px 14px; border-radius: 8px; margin: 10px 0; font-size: 0.85rem;">
<div>
<div style="color: #8c8d9a; font-size: 0.72rem; text-transform: uppercase;">Fair Market Value</div>
<div style="color: #ffffff; font-weight: 700; font-size: 1.0rem;">${fair_val:,.2f}</div>
</div>
<div>
<div style="color: #8c8d9a; font-size: 0.72rem; text-transform: uppercase;">Discount Below Market</div>
<div style="color: #f87171; font-weight: 800; font-size: 1.0rem;">{discount:+.1f}% OFF</div>
</div>
<div>
<div style="color: #8c8d9a; font-size: 0.72rem; text-transform: uppercase;">Edition / Language</div>
<div style="color: #ffffff; font-weight: 600;">{deal.get('edition', 'Unlimited')} ({deal.get('language', 'English')})</div>
</div>
<div>
<div style="color: #8c8d9a; font-size: 0.72rem; text-transform: uppercase;">Condition Tier</div>
<div style="color: #ffffff; font-weight: 600;">{deal.get('condition_type', 'Graded')} ({deal.get('grade_label', 'Gem Mint')})</div>
</div>
</div>
<div style="color: #d1d5db; font-size: 0.88rem; font-style: italic; margin-bottom: 8px;">
💬 <strong>AI Valuation Rationale:</strong> {rationale}
</div>
<div style="text-align: right;">
<a href="{deal['listing_url']}" target="_blank" style="background: linear-gradient(135deg, #ff7a45, #ff4d4f); color: white; text-decoration: none; padding: 6px 16px; border-radius: 8px; font-weight: 700; font-size: 0.82rem; display: inline-block;">
🛒 View & Buy on eBay →
</a>
</div>
</div>""",
                    unsafe_allow_html=True,
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
                placeholder="e.g. AkxDddkn03D.Zcx",
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
                if in_token and in_token != "your_gotify_app_token_here":
                    set_system_setting("GOTIFY_APP_TOKEN", in_token)
                    set_system_setting("GOTIFY_URL", in_url)
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
