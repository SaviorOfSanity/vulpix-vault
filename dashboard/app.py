"""
The Vulpix Vault - Streamlit Web Dashboard
Self-hosted Pokémon card market tracking application with real-time portfolio valuation,
interactive market analytics, and AI deal radar.
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
    get_portfolio_metrics,
    load_collection_df,
    load_deals_df,
    load_market_sales_df,
)
from styles import apply_custom_styles, get_grading_badge_html, render_header

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="The Vulpix Vault",
    page_icon="🦊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Apply CSS Styling
apply_custom_styles()
render_header()

# Load Data
metrics = get_portfolio_metrics()
df_col = load_collection_df()
df_market = load_market_sales_df()

# -------------------------------------------------------------
# Top Portfolio KPI Metrics
# -------------------------------------------------------------
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Vault Portfolio Value</div>
            <div class="kpi-value">${metrics['total_value']:,.2f}</div>
            <div class="kpi-delta-pos">Est. Market Value</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Total Cost Basis</div>
            <div class="kpi-value">${metrics['total_cost']:,.2f}</div>
            <div style="color: #8c8d9a; font-size: 0.85rem;">Acquisition Cost</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col3:
    gain_class = "kpi-delta-pos" if metrics["net_gain"] >= 0 else "kpi-delta-neg"
    sign = "+" if metrics["net_gain"] >= 0 else ""
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Net Unrealized Gain</div>
            <div class="kpi-value">{sign}${metrics['net_gain']:,.2f}</div>
            <div class="{gain_class}">{sign}{metrics['roi_percent']:.1f}% ROI</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col4:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">Graded Slabs</div>
            <div class="kpi-value">{metrics['total_slabs']}</div>
            <div style="color: #8c8d9a; font-size: 0.85rem;">In Personal Vault</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col5:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">AI Deal Radar</div>
            <div class="kpi-value" style="color: #ff7a45;">{metrics['amazing_deals_count']}</div>
            <div style="color: #ff7a45; font-size: 0.85rem; font-weight: 600;">🔥 Amazing Deals Found</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

# -------------------------------------------------------------
# Main Navigation Tabs
# -------------------------------------------------------------
tab_vault, tab_trends, tab_deals, tab_settings = st.tabs([
    "🦊 My Graded Vault",
    "📈 Market Price Trends",
    "🎯 AI Deal Radar",
    "⚙️ System & Controls",
])

# -------------------------------------------------------------
# TAB 1: My Graded Vault
# -------------------------------------------------------------
with tab_vault:
    st.markdown("### 🏆 Graded Slabs Collection")

    # Add Slab Expander Form
    with st.expander("➕ Add New Graded Slab to Vault", expanded=False):
        with st.form("add_slab_form", clear_on_submit=True):
            f_col1, f_col2, f_col3 = st.columns(3)
            with f_col1:
                card_name = st.text_input("Card Name", placeholder="e.g. Base Set 1st Edition Vulpix #68")
                set_name = st.text_input("Set Name", placeholder="e.g. Base Set (1999)")
                card_number = st.text_input("Card Number", placeholder="e.g. 68/102")
            with f_col2:
                grading_company = st.selectbox("Grading Company", ["PSA", "CGC", "BGS", "ARS", "ACE", "SGC"])
                grade = st.number_input("Grade", min_value=1.0, max_value=10.0, value=10.0, step=0.5)
                cert_number = st.text_input("Certification Number", placeholder="e.g. 48291039")
            with f_col3:
                purchase_price = st.number_input("Purchase Price ($)", min_value=0.0, value=50.0, step=5.0)
                purchase_date = st.date_input("Purchase Date", value=datetime.today())
                image_url = st.text_input("Card Image URL (optional)", placeholder="https://...")
            notes = st.text_area("Collector Notes (optional)", placeholder="Subgrades, provenance, or condition notes...")

            submitted = st.form_submit_button("Save Slab to Vault")
            if submitted:
                if card_name:
                    add_card_to_collection({
                        "card_name": card_name,
                        "set_name": set_name or "Unknown Set",
                        "card_number": card_number or "",
                        "grading_company": grading_company,
                        "grade": grade,
                        "cert_number": cert_number or "",
                        "purchase_price": purchase_price,
                        "purchase_date": purchase_date.strftime("%Y-%m-%d"),
                        "image_url": image_url or "https://images.pokemontcg.io/base1/68_hires.png",
                        "notes": notes or "",
                    })
                    st.success(f"Added {card_name} ({grading_company} {grade}) to Vault!")
                    st.rerun()
                else:
                    st.error("Please enter a Card Name.")

    # Grid Display of Slabs
    if df_col.empty:
        st.info("Your vault is currently empty. Add your first graded slab using the form above!")
    else:
        # Display cards in 3 responsive columns
        cols = st.columns(3)
        for idx, row in df_col.iterrows():
            col_target = cols[idx % 3]
            with col_target:
                badge_html = get_grading_badge_html(row["grading_company"], row["grade"])
                gain = row.get("unrealized_gain", 0.0)
                roi = row.get("roi_percent", 0.0)
                gain_color = "#4ade80" if gain >= 0 else "#f87171"
                gain_sign = "+" if gain >= 0 else ""

                img_src = row["image_url"] if row["image_url"] else "https://images.pokemontcg.io/base1/68_hires.png"

                st.markdown(
                    f"""
                    <div class="slab-box">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
                            <div>
                                <div style="font-weight: 800; font-size: 1.1rem; color: #fff;">{row['card_name']}</div>
                                <div style="color: #8c8d9a; font-size: 0.85rem;">{row['set_name']} • #{row['card_number']}</div>
                            </div>
                            {badge_html}
                        </div>
                        <div style="text-align: center; margin: 12px 0;">
                            <img src="{img_src}" style="max-height: 180px; max-width: 100%; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.5);" />
                        </div>
                        <div style="background: #111217; padding: 10px 14px; border-radius: 10px; margin-top: 10px;">
                            <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 4px;">
                                <span style="color: #8c8d9a;">Cost Basis:</span>
                                <span style="color: #ffffff; font-weight: 600;">${row['purchase_price']:,.2f}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 4px;">
                                <span style="color: #8c8d9a;">Market Est:</span>
                                <span style="color: #ffd591; font-weight: 700;">${row['current_market_value']:,.2f}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; font-size: 0.85rem;">
                                <span style="color: #8c8d9a;">Gain / ROI:</span>
                                <span style="color: {gain_color}; font-weight: 700;">{gain_sign}${gain:,.2f} ({gain_sign}{roi:.1f}%)</span>
                            </div>
                        </div>
                        <div style="margin-top: 8px; font-size: 0.75rem; color: #666; text-align: right;">
                            Cert: {row['cert_number'] or 'N/A'} • Acquired: {row['purchase_date']}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button(f"🗑️ Remove", key=f"del_{row['id']}"):
                    delete_card_from_collection(row["id"])
                    st.rerun()

# -------------------------------------------------------------
# TAB 2: Market Price Trends
# -------------------------------------------------------------
with tab_trends:
    st.markdown("### 📈 Graded Market Sales & Price Trends")

    if df_market.empty:
        st.info("No market sales data available yet. The background scraper will populate this table automatically.")
    else:
        # Filter controls
        f1, f2, f3 = st.columns(3)
        with f1:
            all_variants = ["All Cards"] + sorted(df_market["card_name"].dropna().unique().tolist())
            selected_variant = st.selectbox("Filter by Card", all_variants)
        with f2:
            all_cos = ["All Companies"] + sorted(df_market["grading_company"].dropna().unique().tolist())
            selected_co = st.selectbox("Grading Company", all_cos)
        with f3:
            all_grades = ["All Grades"] + sorted([f"{g:g}" for g in df_market["grade"].dropna().unique()], reverse=True)
            selected_grade = st.selectbox("Grade", all_grades)

        # Apply Filters
        filtered_df = df_market.copy()
        if selected_variant != "All Cards":
            filtered_df = filtered_df[filtered_df["card_name"] == selected_variant]
        if selected_co != "All Companies":
            filtered_df = filtered_df[filtered_df["grading_company"] == selected_co]
        if selected_grade != "All Grades":
            filtered_df = filtered_df[filtered_df["grade"] == float(selected_grade)]

        # Time Series Chart
        if not filtered_df.empty:
            filtered_df["display_date"] = pd.to_datetime(
                filtered_df["sale_date"].fillna(filtered_df["scraped_at"])
            )
            filtered_df = filtered_df.sort_values(by="display_date")

            fig = px.scatter(
                filtered_df,
                x="display_date",
                y="total_price",
                color="grading_company",
                size="grade",
                hover_data=["title", "total_price", "grade", "deal_rating"],
                labels={
                    "display_date": "Sale / Scraped Date",
                    "total_price": "Price ($ USD)",
                    "grading_company": "Company",
                },
                title="Historical Sales & Listing Price Trajectory",
                template="plotly_dark",
            )

            # Add trend line
            fig.update_traces(marker=dict(size=9, line=dict(width=1, color="DarkSlateGrey")))
            fig.update_layout(
                paper_bgcolor="#181920",
                plot_bgcolor="#14151b",
                hovermode="closest",
                margin=dict(l=20, r=20, t=50, b=20),
            )
            st.plotly_chart(fig, use_container_width=True)

            # Historical Sales Table
            st.markdown("#### 📋 Historical Sales Records")
            st.dataframe(
                filtered_df[[
                    "sale_date", "card_name", "grading_company", "grade",
                    "total_price", "deal_rating", "title"
                ]].rename(columns={
                    "sale_date": "Date",
                    "card_name": "Card",
                    "grading_company": "Slab",
                    "grade": "Grade",
                    "total_price": "Price ($)",
                    "deal_rating": "Appraisal",
                    "title": "eBay Title",
                }),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.warning("No sales matched the selected filters.")

# -------------------------------------------------------------
# TAB 3: AI Deal Radar
# -------------------------------------------------------------
with tab_deals:
    st.markdown("### 🎯 Google Gemini AI Deal Radar")
    st.markdown(
        "Automated appraisal engine scans every scraped eBay listing against the last 10 comparable sales to flag undervalued cards."
    )

    deal_filter_opt = st.radio(
        "Filter Deals:",
        ["🔥 Amazing Deals (>=20% Discount)", "✨ All Value Deals (Amazing + Good)", "All Market Listings"],
        horizontal=True,
    )

    if "Amazing Deals" in deal_filter_opt:
        df_deals = load_deals_df(deal_filter="amazing_deal")
    elif "All Value Deals" in deal_filter_opt:
        df_deals = load_deals_df(deal_filter="all_deals")
    else:
        df_deals = load_deals_df()

    if df_deals.empty:
        st.info("No deals matching your filter criteria right now. Check back after the next scraper cycle!")
    else:
        for _, deal in df_deals.iterrows():
            rating = deal.get("deal_rating", "unrated")
            badge_deal = (
                '<span class="deal-amazing">🔥 AMAZING DEAL</span>'
                if rating == "amazing_deal"
                else '<span class="deal-good">✨ GOOD DEAL</span>'
            )
            grading_badge = get_grading_badge_html(deal["grading_company"], deal["grade"])

            discount = deal.get("discount_percentage", 0.0) or 0.0
            fair_val = deal.get("fair_value_estimate", deal["total_price"]) or deal["total_price"]
            rationale = deal.get("ai_rationale") or "No appraisal rationale provided."

            with st.container():
                st.markdown(
                    f"""
                    <div style="background: #181920; border: 1px solid {'#ef4444' if rating == 'amazing_deal' else '#22c55e'}; border-radius: 12px; padding: 18px; margin-bottom: 16px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                {badge_deal} &nbsp; {grading_badge}
                                <span style="font-weight: 800; font-size: 1.15rem; color: #fff; margin-left: 8px;">{deal['title']}</span>
                            </div>
                            <div style="text-align: right;">
                                <span style="color: #8c8d9a; font-size: 0.85rem;">Listed: </span>
                                <span style="font-size: 1.3rem; font-weight: 800; color: #4ade80;">${deal['total_price']:,.2f}</span>
                            </div>
                        </div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; background: #111217; padding: 12px 16px; border-radius: 8px; margin: 12px 0;">
                            <div>
                                <div style="color: #8c8d9a; font-size: 0.75rem; text-transform: uppercase;">Estimated Fair Value</div>
                                <div style="color: #ffffff; font-weight: 700; font-size: 1.05rem;">${fair_val:,.2f}</div>
                            </div>
                            <div>
                                <div style="color: #8c8d9a; font-size: 0.75rem; text-transform: uppercase;">Discount Below Market</div>
                                <div style="color: #f87171; font-weight: 800; font-size: 1.05rem;">{discount:+.1f}% OFF</div>
                            </div>
                            <div>
                                <div style="color: #8c8d9a; font-size: 0.75rem; text-transform: uppercase;">Listing Format</div>
                                <div style="color: #ffffff; font-weight: 600;">{deal.get('listing_type', 'Buy It Now')}</div>
                            </div>
                        </div>
                        <div style="color: #d1d5db; font-size: 0.9rem; font-style: italic; margin-bottom: 10px;">
                            💬 <strong>AI Valuation Rationale:</strong> {rationale}
                        </div>
                        <div style="text-align: right;">
                            <a href="{deal['listing_url']}" target="_blank" style="background: linear-gradient(135deg, #ff7a45, #ff4d4f); color: white; text-decoration: none; padding: 8px 18px; border-radius: 8px; font-weight: 700; font-size: 0.85rem; display: inline-block;">
                                🛒 View Listing on eBay →
                            </a>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

# -------------------------------------------------------------
# TAB 4: System Diagnostics & Settings
# -------------------------------------------------------------
with tab_settings:
    st.markdown("### ⚙️ System Controls & Diagnostics")

    col_s1, col_s2 = st.columns(2)

    with col_s1:
        st.markdown("#### 🗄️ Database & Storage")
        db_path = get_db_path()
        file_size_kb = round(os.path.getsize(db_path) / 1024, 2) if os.path.exists(db_path) else 0

        st.markdown(f"- **Database Path:** `{db_path}`")
        st.markdown(f"- **Database File Size:** `{file_size_kb} KB`")
        st.markdown(f"- **Collection Records:** `{len(df_col)} slabs`")
        st.markdown(f"- **Historical Sales Records:** `{len(df_market)} listings`")

    with col_s2:
        st.markdown("#### 🔔 Push Notifications (Gotify)")
        gotify_url = os.getenv("GOTIFY_URL", "http://gotify:80")
        st.markdown(f"- **Gotify Server URL:** `{gotify_url}`")
        st.markdown(f"- **Alert Priority:** `8 (High / Urgent)`")

        if st.button("🔔 Send Test Push Notification"):
            from notifier import send_gotify_alert
            test_listing = {
                "listing_id": "test_alert_001",
                "title": "Base Set 1st Edition Vulpix PSA 10 (TEST ALERT)",
                "card_name": "Base Set 1st Edition Vulpix #68",
                "grading_company": "PSA",
                "grade": 10.0,
                "total_price": 99.00,
                "price": 99.00,
                "listing_url": "https://www.ebay.com",
            }
            test_appraisal = {
                "deal_rating": "amazing_deal",
                "fair_value_estimate": 240.00,
                "discount_percentage": 58.7,
                "rationale": "This is a test alert from The Vulpix Vault dashboard to verify Gotify push notifications.",
            }
            res = send_gotify_alert(test_listing, test_appraisal)
            if res:
                st.success("Test notification successfully dispatched to Gotify!")
            else:
                st.warning("Could not reach Gotify. Ensure GOTIFY_APP_TOKEN is configured in .env and Gotify container is up.")

    st.markdown("---")
    st.markdown("#### 🔄 Manual Scraper Trigger")
    if st.button("⚡ Run eBay Scraper & AI Appraisal Cycle Now"):
        with st.spinner("Scraping eBay & appraising deals..."):
            try:
                import sys
                sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scraper"))
                from cron_scraper import run_scrape_and_appraisal_cycle
                run_scrape_and_appraisal_cycle()
                st.success("Scrape cycle completed!")
                st.rerun()
            except Exception as e:
                st.error(f"Error running scraper: {e}")
