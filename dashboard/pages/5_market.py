"""
The Vulpix Vault - Page 5: Market Sales Explorer
Historical sales charts and comprehensive transactions log.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from db_utils import load_market_sales_df
from styles import apply_custom_styles, render_header

apply_custom_styles()
render_header()

@st.cache_data(ttl=60)
def get_cached_market_sales_df():
    return load_market_sales_df()

df_market = get_cached_market_sales_df()

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
