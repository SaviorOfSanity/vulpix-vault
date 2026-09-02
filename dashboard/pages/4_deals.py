"""
The Vulpix Vault - Page 4: AI Deal Radar
Scraped live eBay deals evaluated against fair market value with automated discount scoring.
"""

import pandas as pd
import streamlit as st

from db_utils import load_deals_df
from styles import apply_custom_styles, render_header

apply_custom_styles()
render_header()

st.markdown("### 🔥 Multi-Tier AI Deal Radar")
st.markdown("Live eBay listings automatically evaluated against fair market value with automated discount scoring.")

f1, f2 = st.columns(2)
with f1:
    deal_tier_sel = st.selectbox(
        "Minimum Discount Tier",
        ["🔥 Amazing Deals (>=40% Off)", "⭐ Great Deals (>=25% Off)", "All Positive Deals (>=10% Off)"],
    )
with f2:
    deal_cond_sel = st.selectbox(
        "Card Condition / Format",
        ["All Cards (Graded & Raw)", "Graded Slabs Only", "Raw Singles Only"],
    )

tier_map = {
    "🔥 Amazing Deals (>=40% Off)": "amazing_deal",
    "⭐ Great Deals (>=25% Off)": "great_and_amazing",
    "All Positive Deals (>=10% Off)": "all",
}
df_deals = load_deals_df(deal_filter=tier_map[deal_tier_sel], condition_filter=deal_cond_sel)

if df_deals.empty:
    st.info("💡 No deals currently match this filter. The scraper daemon evaluates eBay periodically!")
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
