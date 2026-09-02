"""
The Vulpix Vault - Page 3: eBay Sniper Watchlist
Targeted auction tracking, ending time countdowns, and automated deal thresholds.
"""

from datetime import datetime
import pandas as pd
import streamlit as st

from db_utils import (
    add_to_sniper_watchlist,
    delete_from_sniper_watchlist,
    get_sniper_watchlist_df,
    parse_ebay_url_details,
)
from styles import apply_custom_styles, render_header

import time

apply_custom_styles()
render_header()

if "sniper_flash_msg" in st.session_state:
    st.success(st.session_state.pop("sniper_flash_msg"))

# Direct SQLite load (<3ms)
df_sniper = get_sniper_watchlist_df()

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

        if "Amazing" in bid_mode_choice:
            target_max = parsed["amazing_deal_max"]
            target_mode_code = "amazing_deal"
        elif "Great" in bid_mode_choice:
            target_max = parsed["great_deal_max"]
            target_mode_code = "great_deal"
        else:
            target_max = custom_bid_val if custom_bid_val > 0 else parsed["fair_value"]
            target_mode_code = "custom_max"

        card_display_name = parsed.get("card_name", "Vulpix")
        set_display_name = parsed.get("set_name", "Unknown Set")
        edition_display = parsed.get("edition", "Unlimited")
        grader_display = parsed.get("grading_company", "RAW")
        label_display = parsed.get("grade_label", "Raw Single")
        fair_val_display = parsed.get("fair_value", 0.0)

        st.markdown(f"""
        <div style="background: #181920; border: 1px solid rgba(255, 122, 69, 0.3); border-radius: 10px; padding: 12px 16px; margin: 12px 0;">
            <div style="font-weight: 800; font-size: 1.05rem; color: #ffffff;">{parsed.get('title', 'eBay Auction')}</div>
            <div style="color: #8c8d9a; font-size: 0.85rem; margin-bottom: 8px;">
                Identified: <strong>{card_display_name}</strong> ({set_display_name}) • {edition_display} • {grader_display} {label_display}
            </div>
            <div style="display: flex; gap: 20px; font-size: 0.9rem;">
                <div>Fair Market Value: <strong style="color: #ffd591;">${fair_val_display:,.2f}</strong></div>
                <div>Your Max Bid Threshold: <strong style="color: #4ade80;">${target_max:,.2f}</strong></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("🚀 Confirm & Add to Sniper Watchlist", key="btn_confirm_add_sniper", type="primary"):
            t0 = time.perf_counter()
            new_sn_id = add_to_sniper_watchlist({
                "listing_id": parsed.get("item_id") or parsed.get("listing_id"),
                "title": parsed.get("title", "eBay Auction"),
                "card_name": card_display_name,
                "grading_company": grader_display,
                "grade": parsed.get("grade", 0.0),
                "grade_label": label_display,
                "condition_type": parsed.get("condition_type", "Raw"),
                "edition": edition_display,
                "current_bid": parsed.get("current_bid") or parsed.get("current_price", 0.0),
                "shipping_cost": parsed.get("shipping_cost", 0.0),
                "max_bid_target": target_max,
                "fair_market_value": fair_val_display,
                "snipe_mode": target_mode_code,
                "listing_url": parsed.get("canonical_url") or parsed.get("listing_url", ""),
                "auction_end_time": parsed.get("auction_end_time", datetime.today().strftime("%Y-%m-%d %H:%M:%S")),
            })
            elapsed_ms = (time.perf_counter() - t0) * 1000
            st.session_state["sniper_flash_msg"] = f"🎯 Added '{card_display_name}' to Sniper Watchlist in {elapsed_ms:.1f}ms!"
            st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

if df_sniper.empty:
    st.info("🎯 No active auctions on your watchlist. Paste an eBay listing above to track your first card!")
else:
    st.markdown(f"#### 🔭 Active Watchlist Targets ({len(df_sniper)} Auctions)")
    for s_idx, s_row in df_sniper.iterrows():
        s_title = s_row.get("title", "eBay Auction")
        s_card = s_row.get("card_name", "Vulpix")
        s_ed = s_row.get("edition") or "Unlimited"
        s_grader = s_row.get("grading_company") or "RAW"
        s_label = s_row.get("grade_label") or "Raw Single"
        s_curr = float(s_row.get("current_bid") or 0.0)
        s_fair = float(s_row.get("fair_market_value") or s_row.get("max_calculated_bid") or 25.0)
        s_max = float(s_row.get("max_bid_target") or s_row.get("custom_max_bid") or s_row.get("max_calculated_bid") or 15.0)
        s_url = s_row.get("listing_url") or "#"
        s_id = s_row.get("id")

        s_box = f"""<div class="slab-box" style="margin-bottom: 12px; padding: 14px 18px;">
<div style="display: flex; justify-content: space-between; align-items: flex-start;">
<div>
<div style="font-weight: 800; font-size: 1.05rem; color: #ffffff;">{s_title}</div>
<div style="color: #8c8d9a; font-size: 0.82rem; margin-top: 2px;">
{s_card} • {s_ed} • {s_grader} {s_label}
</div>
</div>
<span style="background: rgba(239, 68, 68, 0.2); border: 1px solid #ef4444; color: #f87171; padding: 2px 10px; border-radius: 12px; font-weight: 800; font-size: 0.75rem;">
SNIPING
</span>
</div>
<div style="display: flex; justify-content: space-between; align-items: center; background: #111217; padding: 10px 14px; border-radius: 8px; margin: 10px 0;">
<div><span style="color: #8c8d9a; font-size: 0.8rem;">Current Price:</span> <strong style="color: #fff; font-size: 0.95rem;">${s_curr:,.2f}</strong></div>
<div><span style="color: #8c8d9a; font-size: 0.8rem;">Fair Market Value:</span> <strong style="color: #ffd591; font-size: 0.95rem;">${s_fair:,.2f}</strong></div>
<div><span style="color: #8c8d9a; font-size: 0.8rem;">Your Max Bid Limit:</span> <strong style="color: #4ade80; font-size: 0.95rem;">${s_max:,.2f}</strong></div>
</div>
<div style="display: flex; justify-content: space-between; align-items: center;">
<a href="{s_url}" target="_blank" class="btn-ebay" style="padding: 4px 14px; font-size: 0.82rem;">
🔗 View Live on eBay ↗
</a>
</div>
</div>"""
        st.markdown(s_box, unsafe_allow_html=True)
        if st.button("🗑️ Remove from Watchlist", key=f"del_sn_{s_id}"):
            t0 = time.perf_counter()
            delete_from_sniper_watchlist(s_id)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            st.session_state["sniper_flash_msg"] = f"🗑️ Target removed in {elapsed_ms:.1f}ms!"
            st.rerun()
