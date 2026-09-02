"""
The Vulpix Vault - Page 4: AI Deal Radar
Scraped live eBay deals evaluated against fair market value with automated discount scoring.
"""

import time
from datetime import datetime
import pandas as pd
import streamlit as st

from db_utils import add_to_sniper_watchlist, appraise_and_add_deal_listing, load_deals_df, parse_ebay_url_details
from styles import apply_custom_styles, render_header

apply_custom_styles()
render_header()

if "deal_flash_msg" in st.session_state:
    st.success(st.session_state.pop("deal_flash_msg"))

st.markdown("### 🔥 Multi-Tier AI Deal Radar")
st.markdown("Live eBay listings automatically evaluated against fair market value with automated discount scoring.")

# Custom Listing Appraiser Form
with st.expander("➕ Appraise & Add Custom eBay Listing to AI Deals", expanded=False):
    st.markdown("Paste an eBay listing link or Item ID to immediately appraise it and add it to the AI Deal Radar:")
    ad_c1, ad_c2 = st.columns([3, 1])
    with ad_c1:
        deal_url_in = st.text_input("eBay Listing URL or Item ID", placeholder="e.g. https://www.ebay.com/itm/128050827605", key="deal_url_in")
    with ad_c2:
        deal_price_in = st.number_input("Listing Price ($)", min_value=0.0, value=0.0, step=5.0, help="Leave 0 to auto-extract or estimate", key="deal_price_in")

    if deal_url_in:
        t_parse_0 = time.perf_counter()
        parsed_preview = parse_ebay_url_details(deal_url_in)
        t_parse_elapsed = (time.perf_counter() - t_parse_0) * 1000
        if parsed_preview:
            p_price = deal_price_in if deal_price_in > 0 else parsed_preview.get("current_bid", 25.0)
            f_val = parsed_preview.get("fair_value", 50.0)
            disc = round(((f_val - p_price) / f_val) * 100, 1) if f_val > 0 else 0.0
            st.info(f"**Card Identified ({t_parse_elapsed:.1f}ms):** `{parsed_preview.get('card_name')}` ({parsed_preview.get('set_name')}) • **Fair Value:** `${f_val:,.2f}` • **Discount:** `{disc:.1f}%`")

            if st.button("🚀 Confirm & Add to AI Deal Radar", key="btn_add_to_ai_radar", type="primary"):
                t_appraise_0 = time.perf_counter()
                ok, msg, data = appraise_and_add_deal_listing(deal_url_in, listing_price=deal_price_in)
                t_appraise_elapsed = (time.perf_counter() - t_appraise_0) * 1000
                if ok:
                    st.session_state["deal_flash_msg"] = f"🔥 {msg} (Saved in {t_appraise_elapsed:.1f}ms)"
                    st.rerun()
                else:
                    st.error(msg)

# Filtering Controls
f1, f2, f3 = st.columns([1.5, 1.8, 1.2])

tier_options = [
    "All Positive Deals (>=10% Off)",
    "⭐ Great Deals (>=25% Off)",
    "🔥 Amazing Deals (>=40% Off)",
    "All Positive Deals (>0% Off)",
    "All Listings (including over market)",
]
tier_map = {
    "All Positive Deals (>=10% Off)": "all_deals",
    "⭐ Great Deals (>=25% Off)": "great_and_amazing",
    "🔥 Amazing Deals (>=40% Off)": "amazing_deal",
    "All Positive Deals (>0% Off)": "positive_only",
    "All Listings (including over market)": None,
}

cond_options = [
    "💎 Gem Mint & Pristine 10 Slabs Only (PSA 10 / CGC 10)",
    "All Graded Slabs (PSA / CGC / BGS)",
    "All Cards (Graded & Raw)",
    "Raw Singles Only",
]

with f1:
    deal_tier_sel = st.selectbox(
        "Minimum Discount Tier",
        tier_options,
        index=0,
        key="deal_tier_sel",
    )
with f2:
    deal_cond_sel = st.selectbox(
        "Card Grade & Format",
        cond_options,
        index=0,  # Defaults to PSA 10 & CGC 10 Slabs Only!
        key="deal_cond_sel",
    )
with f3:
    deal_type_sel = st.selectbox(
        "Listing Type",
        ["All Listings", "🎯 Live Auctions Only", "⚡ Buy It Now Only"],
        index=0,
        key="deal_type_sel",
    )

only_missing_chk = st.checkbox("👑 Only Show Cards Missing from My Vault", value=False, key="deals_only_missing")

df_deals = load_deals_df(
    deal_filter=tier_map[deal_tier_sel],
    condition_filter=deal_cond_sel,
    listing_type_filter=deal_type_sel if deal_type_sel != "All Listings" else None,
    missing_only=only_missing_chk,
)

if df_deals.empty:
    st.info("💡 No deals currently match this filter. Change the discount tier or grade filter above to expand results.")
else:
    st.markdown(f"**Found {len(df_deals)} Active Deals**")
    d_grid = st.columns(3)
    for d_idx, d_row in df_deals.iterrows():
        d_target = d_grid[d_idx % 3]
        with d_target:
            rating = d_row.get("deal_rating", "")
            disc = float(d_row.get("discount_percentage", 0.0))
            is_auction = "auction" in str(d_row.get("listing_type", "")).lower()

            if disc >= 40.0:
                badge_cls = "deal-amazing"
                badge_text = "🔥 AMAZING DEAL"
            elif disc >= 25.0:
                badge_cls = "deal-great"
                badge_text = "⭐ GREAT DEAL"
            elif disc >= 10.0:
                badge_cls = "deal-good"
                badge_text = "✨ GOOD DEAL"
            elif disc > 0.0:
                badge_cls = "deal-good"
                badge_text = "FAIR DEAL"
            else:
                badge_cls = "badge-error"
                badge_text = "⛔ OVERPRICED"

            disc_color = "#4ade80" if disc >= 0 else "#f87171"
            disc_label = f"{disc:.1f}% OFF" if disc >= 0 else f"+{abs(disc):.1f}% OVER"
            type_label = "🎯 Auction" if is_auction else "⚡ Buy It Now"
            type_color = "#60a5fa" if is_auction else "#a78bfa"

            st.markdown(f"""<div class="slab-box">
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
<span class="{badge_cls}">{badge_text}</span>
<span style="font-weight: 800; color: {disc_color}; font-size: 0.95rem;">{disc_label}</span>
</div>
<div style="font-size: 0.76rem; color: {type_color}; font-weight: 700; margin-bottom: 4px;">{type_label}</div>
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
"{d_row.get('ai_rationale') or 'Evaluated against recent comps.'}"
</div>
<a href="{d_row['listing_url']}" target="_blank" class="btn-ebay" style="width: 100%; text-align: center; display: block; box-sizing: border-box; margin-bottom: 6px;">
🛒 View on eBay ↗
</a>
</div>""", unsafe_allow_html=True)

            if is_auction:
                if st.button("🎯 Track in Sniper Watchlist", key=f"track_deal_{d_row['listing_id']}", use_container_width=True):
                    add_to_sniper_watchlist({
                        "listing_id": d_row["listing_id"],
                        "title": d_row["title"],
                        "card_name": d_row.get("card_name", "Vulpix"),
                        "grading_company": d_row.get("grading_company", "PSA"),
                        "grade": d_row.get("grade", 10.0),
                        "grade_label": d_row.get("grade_label", "Gem Mint"),
                        "condition_type": d_row.get("condition_type", "Graded"),
                        "edition": d_row.get("edition", "Unlimited"),
                        "current_bid": d_row.get("total_price", 0.0),
                        "shipping_cost": d_row.get("shipping_cost", 0.0),
                        "max_bid_target": round(float(d_row.get("fair_value_estimate", 0.0)) * 0.75, 2),
                        "fair_market_value": float(d_row.get("fair_value_estimate", 0.0)),
                        "snipe_mode": "great_deal",
                        "listing_url": d_row["listing_url"],
                        "auction_end_time": datetime.today().strftime("%Y-%m-%d %H:%M:%S"),
                    })
                    st.session_state["deal_flash_msg"] = f"🎯 Added '{d_row['title']}' to your Sniper Watchlist!"
                    st.rerun()
