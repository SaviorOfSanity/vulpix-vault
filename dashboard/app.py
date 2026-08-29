"""
The Vulpix Vault - Streamlit Web Dashboard
Master Set Completion Tracker, Special Grades (Pristine 10, Black Label 10),
Google Sheets Catalog Sync, and Multi-Tier AI Deal Radar.
"""

import os
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from db_utils import (
    add_card_to_collection,
    delete_card_from_collection,
    get_db_path,
    get_master_set_metrics,
    get_portfolio_metrics,
    load_collection_df,
    load_deals_df,
    load_market_sales_df,
    load_master_catalog_df,
    sync_from_google_sheets_url,
    sync_master_catalog_from_df,
)
from styles import apply_custom_styles, get_grading_badge_html, render_header

# Set Page Config
st.set_page_config(
    page_title="The Vulpix Vault",
    page_icon="🦊",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_custom_styles()
render_header()

# Load Core Analytics
port_metrics = get_portfolio_metrics()
master_metrics = get_master_set_metrics()
df_col = load_collection_df()
df_master = load_master_catalog_df()
df_market = load_market_sales_df()

# -------------------------------------------------------------
# Top KPI Header Metrics
# -------------------------------------------------------------
kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

with kpi1:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Master Set Progress</div>
            <div class="kpi-value" style="color: #10b981;">{master_metrics['completion_pct']}%</div>
            <div style="color: #94a3b8; font-size: 0.82rem;">{master_metrics['owned_cards']} / {master_metrics['total_cards']} Unique Cards</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with kpi2:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Cost to Finish Master Set</div>
            <div class="kpi-value" style="font-size: 1.35rem; color: #ffd591;">${master_metrics['cost_to_complete_raw']:,.2f} <span style="font-size: 0.8rem; color: #94a3b8;">(Raw)</span></div>
            <div style="color: #f59e0b; font-size: 0.8rem; font-weight: 600;">${master_metrics['cost_to_complete_grade10']:,.2f} in Grade 10</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with kpi3:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Vault Portfolio Value</div>
            <div class="kpi-value">${port_metrics['total_value']:,.2f}</div>
            <div style="color: #8c8d9a; font-size: 0.82rem;">Cost Basis: ${port_metrics['total_cost']:,.2f}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with kpi4:
    gain_class = "kpi-delta-pos" if port_metrics["net_gain"] >= 0 else "kpi-delta-neg"
    sign = "+" if port_metrics["net_gain"] >= 0 else ""
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Net Gain / ROI</div>
            <div class="kpi-value">{sign}${port_metrics['net_gain']:,.2f}</div>
            <div class="{gain_class}">{sign}{port_metrics['roi_percent']:.1f}% Total ROI</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with kpi5:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">AI Deal Radar</div>
            <div class="kpi-value" style="color: #ff7a45;">{port_metrics['amazing_deals_count'] + port_metrics['great_deals_count']}</div>
            <div style="color: #ff7a45; font-size: 0.82rem; font-weight: 600;">🔥 {port_metrics['amazing_deals_count']} Amazing • ⭐ {port_metrics['great_deals_count']} Great</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

# -------------------------------------------------------------
# Main Navigation Tabs
# -------------------------------------------------------------
tab_vault, tab_master, tab_trends, tab_deals, tab_settings = st.tabs([
    "🦊 My Graded & Raw Vault",
    "📜 Master Set Checklist",
    "📈 Market Price Trends",
    "🎯 AI Deal Radar",
    "⚙️ System Controls & Sync",
])

# -------------------------------------------------------------
# TAB 1: My Graded & Raw Vault
# -------------------------------------------------------------
with tab_vault:
    st.markdown("### 🏆 Personal Vulpix Collection")

    # Add Slab / Raw Card Form
    with st.expander("➕ Add New Card or Slab to Vault", expanded=False):
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
            with f3:
                f_lang = st.selectbox("Language", ["English", "Japanese", "German", "French", "Italian", "Spanish", "Korean", "Chinese"])
                f_price = st.number_input("Purchase Price ($ USD)", min_value=0.0, value=25.0, step=5.0)
                f_date = st.date_input("Purchase Date", value=datetime.today())
                f_img = st.text_input("Card Image URL (optional)", placeholder="https://...")

            st.markdown("---")
            e1, e2 = st.columns([1, 3])
            with e1:
                f_is_err = st.checkbox("⚠️ Is this an Error Card?")
            with e2:
                f_err_type = st.text_input("Error Description (if applicable)", placeholder="e.g. HP 50 Error, No Rarity Symbol, Miscut...")

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
                        "image_url": f_img or "https://images.pokemontcg.io/base1/68_hires.png",
                        "notes": f_notes or "",
                    })
                    st.success(f"Added {f_card_name} ({f_edition} - {f_grade_label}) to Vault!")
                    st.rerun()
                else:
                    st.error("Please provide a Card Name.")

    # Grid Display of Slabs & Raw Cards
    if df_col.empty:
        st.info("Your vault is empty. Add your first card or slab above!")
    else:
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
                gain = row.get("unrealized_gain", 0.0)
                roi = row.get("roi_percent", 0.0)
                gain_color = "#4ade80" if gain >= 0 else "#f87171"
                gain_sign = "+" if gain >= 0 else ""

                error_badge = '<span class="badge-error">⚠️ ERROR CARD</span>' if row.get("is_error") == 1 else ""
                img_src = row["image_url"] if row["image_url"] else "https://images.pokemontcg.io/base1/68_hires.png"

                st.markdown(
                    f"""
                    <div class="slab-box">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                            <div>
                                <div style="font-weight: 800; font-size: 1.05rem; color: #fff;">{row['card_name']}</div>
                                <div style="color: #8c8d9a; font-size: 0.82rem;">{row['set_name']} • #{row['card_number']} ({row.get('edition', 'Unlimited')})</div>
                            </div>
                            <div style="text-align: right;">
                                {badge_html}
                                <div style="margin-top: 4px;">{error_badge}</div>
                            </div>
                        </div>
                        <div style="text-align: center; margin: 10px 0;">
                            <img src="{img_src}" style="max-height: 170px; max-width: 100%; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.5);" />
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
                        <div style="margin-top: 8px; font-size: 0.72rem; color: #666; text-align: right;">
                            {f"Cert: {row['cert_number']}" if row.get('cert_number') else 'Raw'} • Acquired: {row['purchase_date']}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button(f"🗑️ Delete", key=f"del_{row['id']}"):
                    delete_card_from_collection(row["id"])
                    st.rerun()

# -------------------------------------------------------------
# TAB 2: Master Set Checklist & Google Sheets Sync
# -------------------------------------------------------------
with tab_master:
    st.markdown("### 📜 Master Set Checklist & Catalog")

    # Master Set Progress Bar Header
    pct = master_metrics["completion_pct"]
    st.markdown(
        f"""
        <div class="master-box">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="font-weight: 800; font-size: 1.2rem; color: #ffffff;">Vulpix Master Set Completion</div>
                <div style="font-weight: 800; font-size: 1.4rem; color: #10b981;">{pct}%</div>
            </div>
            <div class="progress-bar-bg">
                <div class="progress-bar-fill" style="width: {pct}%;"></div>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.85rem; color: #8c8d9a;">
                <span>Owned: <strong style="color: #fff;">{master_metrics['owned_cards']}</strong> / {master_metrics['total_cards']}</span>
                <span>Missing: <strong style="color: #f87171;">{master_metrics['missing_cards']}</strong> cards</span>
                <span>Est. Raw Cost: <strong style="color: #ffd591;">${master_metrics['cost_to_complete_raw']:,.2f}</strong></span>
                <span>Est. Grade 10 Cost: <strong style="color: #f59e0b;">${master_metrics['cost_to_complete_grade10']:,.2f}</strong></span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Filter Controls for Master Set Table
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1:
        m_view = st.selectbox("View Filter", ["All Master Cards", "❌ Missing Cards Only", "✅ Owned Cards Only", "⚠️ Error Cards Only"])
    with m_col2:
        m_langs = ["All Languages"] + sorted(df_master["language"].dropna().unique().tolist())
        m_sel_lang = st.selectbox("Language", m_langs)
    with m_col3:
        m_eds = ["All Editions"] + sorted(df_master["edition"].dropna().unique().tolist())
        m_sel_ed = st.selectbox("Edition", m_eds)
    with m_col4:
        m_search = st.text_input("Search Set or Card Name", placeholder="e.g. Neo Destiny, Promo...")

    # Filter Dataframe
    filtered_master = df_master.copy()
    if m_view == "❌ Missing Cards Only":
        filtered_master = filtered_master[~filtered_master["is_owned"]]
    elif m_view == "✅ Owned Cards Only":
        filtered_master = filtered_master[filtered_master["is_owned"]]
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

    # Checklist Table
    st.markdown(f"**Showing {len(filtered_master)} Cards in Master Catalog**")

    # Render checklist cards or interactive table
    display_df = filtered_master[[
        "is_owned", "release_year", "card_name", "set_name", "card_number",
        "edition", "language", "is_error", "est_raw_price", "est_grade10_price", "notes"
    ]].copy()

    display_df["Status"] = display_df["is_owned"].apply(lambda x: "✅ OWNED" if x else "❌ MISSING")
    display_df["Error?"] = display_df["is_error"].apply(lambda x: "⚠️ Yes" if x == 1 else "No")

    st.dataframe(
        display_df[[
            "Status", "release_year", "card_name", "set_name", "card_number",
            "edition", "language", "Error?", "est_raw_price", "est_grade10_price", "notes"
        ]].rename(columns={
            "release_year": "Year",
            "card_name": "Card Name",
            "set_name": "Set / Expansion",
            "card_number": "#",
            "edition": "Edition",
            "language": "Language",
            "est_raw_price": "Est Raw ($)",
            "est_grade10_price": "Est 10 ($)",
            "notes": "Notes",
        }),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("---")
    st.markdown("#### 🔄 Import / Sync Google Sheet or CSV Catalog")
    st.markdown(
        "Have a custom spreadsheet tracking your Vulpix Master Set? Sync it here to automatically update prices, missing cards, and variants."
    )

    sync_col1, sync_col2 = st.columns(2)
    with sync_col1:
        st.markdown("##### 🌐 Sync via Google Sheets Public Link")
        sheet_url_input = st.text_input(
            "Google Sheet URL",
            value="https://docs.google.com/spreadsheets/d/12RkRdPNwbFly1SXmCS7DQkB5Q5zQZcPAnLX-P8M_vNA/edit?gid=0#gid=0",
        )
        if st.button("🔄 Sync Google Sheet into Catalog"):
            with st.spinner("Fetching and importing Google Sheet..."):
                count, msg = sync_from_google_sheets_url(sheet_url_input)
                if count > 0:
                    st.success(msg)
                    st.rerun()
                else:
                    st.warning(msg)
                    st.info("💡 **Tip:** Ensure your Google Sheet is set to *'Anyone with the link can view'*, or download it as CSV and upload it on the right.")

    with sync_col2:
        st.markdown("##### 📁 Upload CSV File Directly")
        uploaded_csv = st.file_uploader("Choose a CSV file", type=["csv"])
        if uploaded_csv is not None:
            if st.button("📥 Import Uploaded CSV"):
                try:
                    df_up = pd.read_csv(uploaded_csv)
                    count, msg = sync_master_catalog_from_df(df_up)
                    st.success(msg)
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to parse CSV: {e}")

# -------------------------------------------------------------
# TAB 3: Market Price Trends
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
# TAB 4: AI Deal Radar
# -------------------------------------------------------------
with tab_deals:
    st.markdown("### 🎯 Google Gemini AI Deal Radar")
    st.markdown(
        "Automated appraisal engine scans every scraped eBay listing against the last 10 comparable sales to flag undervalued cards across Grade 10 slabs and Raw singles."
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
                    f"""
                    <div style="background: #181920; border: 1px solid {border_color}; border-radius: 12px; padding: 16px; margin-bottom: 14px;">
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
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

# -------------------------------------------------------------
# TAB 5: System Controls & Diagnostics
# -------------------------------------------------------------
with tab_settings:
    st.markdown("### ⚙️ System Controls & Health")

    col_s1, col_s2 = st.columns(2)

    with col_s1:
        st.markdown("#### 🗄️ Database & Catalog Diagnostics")
        db_path = get_db_path()
        file_size_kb = round(os.path.getsize(db_path) / 1024, 2) if os.path.exists(db_path) else 0

        st.markdown(f"- **Database Path:** `{db_path}`")
        st.markdown(f"- **Database File Size:** `{file_size_kb} KB`")
        st.markdown(f"- **Master Set Catalog:** `{master_metrics['total_cards']} unique cards`")
        st.markdown(f"- **Personal Vault Records:** `{len(df_col)} items`")
        st.markdown(f"- **Historical Sales Records:** `{len(df_market)} listings`")

    with col_s2:
        st.markdown("#### 🔔 Gotify Push Alerts")
        gotify_url = os.getenv("GOTIFY_URL", "http://gotify:80")
        st.markdown(f"- **Gotify Server URL:** `{gotify_url}`")
        st.markdown(f"- **Alert Levels:** `Priority 8 (Amazing Deals), Priority 6 (Great Deals)`")

        if st.button("🔔 Send Test Push Alert"):
            import sys
            sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scraper"))
            from notifier import send_gotify_alert
            test_listing = {
                "listing_id": "test_alert_002",
                "title": "Light Vulpix Neo Destiny 1st Edition CGC Pristine 10 (TEST ALERT)",
                "card_name": "Light Vulpix",
                "grading_company": "CGC",
                "grade": 10.0,
                "grade_label": "Pristine 10",
                "condition_type": "Graded",
                "edition": "1st Edition",
                "language": "English",
                "total_price": 125.00,
                "price": 125.00,
                "listing_url": "https://www.ebay.com",
            }
            test_appraisal = {
                "deal_rating": "amazing_deal",
                "fair_value_estimate": 280.00,
                "discount_percentage": 55.4,
                "rationale": "Pristine 10 gold label copy listed at less than standard Gem Mint fair market price.",
            }
            res = send_gotify_alert(test_listing, test_appraisal)
            if res:
                st.success("Test notification dispatched to Gotify!")
            else:
                st.warning("Could not reach Gotify. Ensure GOTIFY_APP_TOKEN is configured in .env.")

    st.markdown("---")
    st.markdown("#### ⚡ Trigger Multi-Query eBay Scrape Now")
    if st.button("⚡ Run Scraper & AI Appraisal Cycle"):
        with st.spinner("Scraping eBay for Raw, Grade 10, and Error Vulpix cards..."):
            try:
                import sys
                sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scraper"))
                from cron_scraper import run_scrape_and_appraisal_cycle
                run_scrape_and_appraisal_cycle()
                st.success("Scrape cycle completed!")
                st.rerun()
            except Exception as e:
                st.error(f"Scraper error: {e}")
