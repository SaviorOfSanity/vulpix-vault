"""
The Vulpix Vault - Page 2: Master Set Checklist & Catalog
Curated collector catalog, 4x4 binder sheet grid, sketchbook card inspection modal,
smart filtering, and Google Sheets sync.
"""

import io
import re
import urllib.request
from datetime import datetime
import pandas as pd
import streamlit as st

from db_utils import (
    EDITION_OPTIONS,
    LANGUAGE_OPTIONS,
    sync_pokecottage_catalog,
    add_card_to_collection,
    auto_enrich_master_catalog,
    download_all_card_images_locally,
    generate_ebay_search_url,
    get_card_image_data_uri,
    get_consolidated_release_groups,
    get_master_set_metrics,
    get_pricecharting_search_url,
    load_master_catalog_df,
    parse_and_preview_catalog,
    sync_from_google_sheets_url,
    unmark_card_as_owned,
    update_card_image_override,
    update_master_card,
)
from metadata_resolver import DEFAULT_CARD_BACK_IMAGE
from styles import (
    apply_custom_styles,
    get_edition_badge_html,
    get_pop_badge_html,
    render_header,
)

apply_custom_styles()
render_header()

# Check URL Query Parameter for Direct Inspection Link (e.g. ?inspect=123)
query_params = getattr(st, "query_params", {})
if "inspect" in query_params:
    try:
        st.session_state["modal_card_id"] = int(query_params["inspect"])
    except Exception:
        pass

# Top Controls Bar: Cameo Filter
c_top_title, c_top_opt = st.columns([3, 2])
with c_top_title:
    st.markdown("### 📜 Vulpix Master Set Checklist & Catalog")
with c_top_opt:
    exclude_cameos = st.checkbox(
        "🚫 Exclude Cameo Cards (Pikachu/Cameos)",
        value=True,
        help="When checked, non-Vulpix cards that only feature Vulpix in the background/cameo (e.g. Poncho Pikachu, Sapporo's Pikachu, Pokémon Rumble) are hidden and excluded from Master Set completion statistics.",
        key="exclude_cameos_toggle"
    )

df_master = load_master_catalog_df()
master_metrics = get_master_set_metrics(exclude_cameos=exclude_cameos)

# Calculate Region & Printing Counts dynamically for the Hero Banner
if exclude_cameos:
    df_count_base = df_master[df_master.get("is_cameo", 0) != 1] if "is_cameo" in df_master.columns else df_master
else:
    df_count_base = df_master

english_count = len(df_count_base[df_count_base["language"] == "English"])
japanese_count = len(df_count_base[df_count_base["language"] == "Japanese"])
chinese_count = len(df_count_base[df_count_base["language"].str.contains("Chinese", case=False, na=False)])
promo_count = len(df_count_base[
    df_count_base["edition"].str.contains("Promo", case=False, na=False) |
    df_count_base["set_name"].str.contains("Promo", case=False, na=False)
])
try:
    unique_printings = df_count_base.groupby(["card_name", "set_name", "card_number"]).ngroups
except Exception:
    unique_printings = len(df_count_base)
additional_variants = max(0, len(df_count_base) - unique_printings)
total_master_count = len(df_count_base)

# =========================================================
# PokeCottage-Style Editorial Header & Valuation Breakdown
# =========================================================
cameo_sub_badge = ' <span style="font-size: 0.74rem; font-weight: 600; color: #8da693; background: #162b1b; padding: 2px 8px; border-radius: 6px; border: 1px solid #23452b;">Cameos Excluded</span>' if exclude_cameos else ""

st.markdown(
    f"""
    <div class="cottage-hero">
        <h2 class="cottage-hero-title">Vulpix Master Set Card Count</h2>
        
        <div class="cottage-stats-grid">
            <div class="cottage-stat-item">
                <div class="cottage-stat-label">ENGLISH</div>
                <div class="cottage-stat-val">{english_count} cards</div>
            </div>
            <div class="cottage-stat-item">
                <div class="cottage-stat-label">JAPANESE</div>
                <div class="cottage-stat-val">{japanese_count} cards</div>
            </div>
            <div class="cottage-stat-item">
                <div class="cottage-stat-label">S. CHINESE</div>
                <div class="cottage-stat-val">{chinese_count} cards</div>
            </div>
            <div class="cottage-stat-item">
                <div class="cottage-stat-label">PROMOS</div>
                <div class="cottage-stat-val">{promo_count} cards</div>
            </div>
            <div class="cottage-stat-item">
                <div class="cottage-stat-label">UNIQUE PRINTINGS</div>
                <div class="cottage-stat-val">{unique_printings} cards</div>
            </div>
            <div class="cottage-stat-item">
                <div class="cottage-stat-label">ADDITIONAL VARIANTS</div>
                <div class="cottage-stat-val">{additional_variants} cards</div>
            </div>
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <div style="font-family: 'Fraunces', Georgia, serif; font-size: 1.25rem; font-weight: 700; color: #f5f2eb;">
                Master Set Progress{cameo_sub_badge}
            </div>
            <div style="font-family: 'Fraunces', Georgia, serif; font-size: 1.5rem; font-weight: 700; color: #34d399;">
                {master_metrics['completion_pct']}%
            </div>
        </div>

        <div class="progress-bar-bg">
            <div class="progress-bar-fill" style="width: {master_metrics['completion_pct']}%;"></div>
        </div>

        <div style="display: flex; justify-content: space-between; font-size: 0.85rem; color: #9cb3a2; flex-wrap: wrap; gap: 8px; margin-top: 10px;">
            <span>Owned: <strong style="color: #f5f2eb;">{master_metrics['owned_cards']}</strong> / {master_metrics['total_cards']} Unique</span>
            <span>Missing: <strong style="color: #f87171;">{master_metrics['missing_cards']}</strong> cards</span>
            <span>Est. Raw Finish Cost: <strong style="color: #fde047;">${master_metrics['cost_to_complete_raw']:,.2f}</strong></span>
            <span>Est. Grade 10 Finish Cost: <strong style="color: #d4af37;">${master_metrics['cost_to_complete_grade10']:,.2f}</strong></span>
            <span>Total Value: <strong style="color: #34d399;">${master_metrics['total_raw_value']:,.2f} Raw</strong> • <strong style="color: #d4af37;">${master_metrics['total_grade10_value']:,.2f} PSA 10</strong></span>
        </div>

        <div style="margin-top: 24px;">
            <div class="cottage-oval-banner">
                <span>How Many Cards Are in the Vulpix Master Set?</span>
                <span class="cottage-oval-pill">{total_master_count} cards</span>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Metadata Verification & Auto-Enrichment Controls
en_col1, en_col2, en_col3, en_col4 = st.columns([1.8, 1.1, 1.1, 1.2])
with en_col1:
    st.markdown(
        "💡 *Sync with official PokeCottage Grand Master Set or download verified high-res scans directly to your local server.*"
    )
with en_col2:
    if st.button("✨ Auto-Enrich Names", key="btn_auto_enrich_master", use_container_width=True):
        with st.spinner("Resolving card names and fetching official scans..."):
            cnt, msg = auto_enrich_master_catalog(force_all=True)
            st.success(msg)
            st.rerun()
with en_col3:
    if st.button("⚡ Cache Scans", key="btn_download_images_local", use_container_width=True):
        with st.spinner("Downloading high-res images to server for instant offline loading..."):
            d_cnt, d_msg = download_all_card_images_locally()
            st.success(d_msg)
            st.rerun()
with en_col4:
    if st.button("🏡 Sync PokeCottage", key="btn_sync_pokecottage", use_container_width=True):
        with st.spinner("Fetching latest PokeCottage Grand Master Set checklist & scans..."):
            s_ok, s_msg = sync_pokecottage_catalog()
            if s_ok:
                st.success(s_msg)
            else:
                st.warning(s_msg)
            st.rerun()

# =========================================================
# Filter Controls
# =========================================================
m_col1, m_col2, m_col3, m_col4 = st.columns(4)
with m_col1:
    m_view = st.selectbox(
        "Status Filter",
        [
            "All Master Cards",
            "❌ Missing Cards Only",
            "✅ Owned Cards Only",
            "🌐 International Cards",
            "🇯🇵 Japan Releases",
            "🇨🇳 China Releases",
            "🥇 1st Edition Only",
            "💎 Low Pop (<20 PSA 10)",
            "⚠️ Error Cards Only",
            "🎭 Cameo Cards Only",
        ],
    )
with m_col2:
    m_langs = ["All Languages"] + sorted(df_master["language"].dropna().unique().tolist())
    m_sel_lang = st.selectbox("Language Filter", m_langs)
with m_col3:
    m_eds = ["All Editions"] + sorted(df_master["edition"].dropna().unique().tolist())
    m_sel_ed = st.selectbox("Edition Filter", m_eds)
with m_col4:
    m_search = st.text_input("Search Set or Card Name", placeholder="e.g. Neo Destiny, Blaine, CoroCoro...")

# Apply Filters
filtered_master = df_master.copy()
if exclude_cameos and m_view != "🎭 Cameo Cards Only":
    if "is_cameo" in filtered_master.columns:
        filtered_master = filtered_master[filtered_master["is_cameo"] != 1]

if m_view == "❌ Missing Cards Only":
    filtered_master = filtered_master[~filtered_master["is_owned"]]
elif m_view == "✅ Owned Cards Only":
    filtered_master = filtered_master[filtered_master["is_owned"]]
elif m_view == "🎭 Cameo Cards Only":
    if "is_cameo" in filtered_master.columns:
        filtered_master = filtered_master[filtered_master["is_cameo"] == 1]
elif m_view == "🌐 International Cards":
    filtered_master = filtered_master[
        filtered_master["region"].fillna("International").str.contains("International|All|USA|Europe", case=False, na=False)
    ]
elif m_view == "🇯🇵 Japan Releases":
    filtered_master = filtered_master[filtered_master["region"].fillna("").str.contains("Japan", case=False, na=False)]
elif m_view == "🇨🇳 China Releases":
    filtered_master = filtered_master[filtered_master["region"].fillna("").str.contains("China", case=False, na=False)]
elif m_view == "🥇 1st Edition Only":
    filtered_master = filtered_master[filtered_master["edition"].str.contains("1st", case=False, na=False)]
elif m_view == "💎 Low Pop (<20 PSA 10)":
    filtered_master = filtered_master[
        (filtered_master["pop_grade10"] > 0) & (filtered_master["pop_grade10"] <= 20)
    ]
elif m_view == "⚠️ Error Cards Only":
    filtered_master = filtered_master[filtered_master["is_error"] == 1]

if m_sel_lang != "All Languages":
    filtered_master = filtered_master[filtered_master["language"] == m_sel_lang]

if m_sel_ed != "All Editions":
    filtered_master = filtered_master[filtered_master["edition"] == m_sel_ed]

if m_search:
    s_query = m_search.strip().lower()
    filtered_master = filtered_master[
        filtered_master["card_name"].str.lower().str.contains(s_query, na=False)
        | filtered_master["set_name"].str.lower().str.contains(s_query, na=False)
        | filtered_master["card_number"].str.lower().str.contains(s_query, na=False)
    ]

# View Mode Selection (4x4 Binder is DEFAULT)
v_top1, v_top2 = st.columns([3, 2])
with v_top1:
    master_view_mode = st.radio(
        "Display Layout:",
        ["🃏 4x4 Collector Binder (Default)", "🗂️ Consolidated Release Matrix", "📋 Table / List View"],
        horizontal=True,
        key="master_v_mode",
    )

# =========================================================
# Sketchbook Card Detail Dialog (Image 3)
# =========================================================
dialog_fn = getattr(st, "dialog", getattr(st, "experimental_dialog", None))


def render_sketchbook_modal_content(card_id: int, active_df: pd.DataFrame):
    """Renders the parchment graph paper card detail dialog matching Image 3."""
    matches = active_df[active_df["id"] == card_id]
    if matches.empty:
        st.warning("Card not found in active filtered view.")
        return

    row = matches.iloc[0]
    id_list = active_df["id"].tolist()
    curr_idx = id_list.index(card_id) if card_id in id_list else 0
    total_in_view = len(id_list)

    # Top Navigation Row (< 1 / 251 >)
    nav_c1, nav_c2, nav_c3 = st.columns([1, 2, 1])
    with nav_c1:
        if curr_idx > 0:
            prev_id = id_list[curr_idx - 1]
            if st.button("⬅ Previous", key=f"btn_prev_{card_id}", use_container_width=True):
                st.session_state["modal_card_id"] = prev_id
                st.rerun()
        else:
            st.caption("First Card")
    with nav_c2:
        st.markdown(
            f"""
            <div style="text-align: center;">
                <div style="font-family: 'Fraunces', Georgia, serif; font-style: italic; font-size: 1.7rem; font-weight: 700; color: #122215; margin: 0;">
                    {row['card_name']}
                </div>
                <div style="font-size: 0.72rem; font-weight: 800; letter-spacing: 1.5px; text-transform: uppercase; color: #855b2e;">
                    {row['set_name']} • {row['language']} • ({curr_idx + 1} / {total_in_view})
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with nav_c3:
        if curr_idx < total_in_view - 1:
            next_id = id_list[curr_idx + 1]
            if st.button("Next ➡", key=f"btn_next_{card_id}", use_container_width=True):
                st.session_state["modal_card_id"] = next_id
                st.rerun()
        else:
            st.caption("Last Card")

    # Main Sketchbook Parchment Grid Canvas
    img_src = get_card_image_data_uri(row["image_url"] if row["image_url"] else DEFAULT_CARD_BACK_IMAGE)
    artist_name = row.get("artist") or "Ken Sugimori"
    finish_style = row.get("finish") or row.get("edition") or "Standard"
    cnum_display = f"#{row['card_number']}" if row["card_number"] and str(row["card_number"]).lower() != "nan" else "Promo"
    rarity_name = row.get("rarity") or "Common"

    # Dynamic or custom collector's note
    if row.get("notes") and len(str(row["notes"]).strip()) > 5:
        collector_note = str(row["notes"]).strip()
    else:
        collector_note = f"This card was released in the {row['language']} {row['set_name']} expansion ({row['release_year']}) featuring art by {artist_name}."

    st.markdown('<div class="sketchbook-modal">', unsafe_allow_html=True)
    b_col1, b_col2, b_col3 = st.columns([1, 1.4, 1])

    with b_col1:
        st.markdown(
            f"""
            <div style="padding: 12px 0;">
                <div class="sketchbook-annot-label">CARD NUMBER</div>
                <div class="sketchbook-annot-val">{cnum_display}</div>
                
                <div class="sketchbook-annot-label">ILLUSTRATOR</div>
                <div class="sketchbook-annot-val">{artist_name}</div>
                
                <div class="sketchbook-annot-label">RELEASE YEAR</div>
                <div class="sketchbook-annot-val">{row['release_year']}</div>
                
                <div class="sketchbook-annot-label">LANGUAGE</div>
                <div class="sketchbook-annot-val">{row['language']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with b_col2:
        st.markdown(
            f"""
            <div style="text-align: center; padding: 6px 0;">
                <img src="{img_src}" style="max-height: 380px; max-width: 100%; border-radius: 12px; box-shadow: 0 16px 36px rgba(0,0,0,0.5);" />
                <div style="font-size: 0.72rem; color: #7d9683; font-style: italic; margin-top: 8px;">
                    *Official verified scan from Pokémon TCG master catalog.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with b_col3:
        st.markdown(
            f"""
            <div style="padding: 12px 0;">
                <div class="sketchbook-annot-label">RARITY</div>
                <div class="sketchbook-annot-val">{rarity_name}</div>
                
                <div class="sketchbook-annot-label">FINISH</div>
                <div class="sketchbook-annot-val">{finish_style}</div>
                
                <div class="sketchbook-annot-label">COLLECTOR'S NOTE</div>
                <div class="sketchbook-handwritten">
                    "{collector_note}"
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)

    # Bottom Dark Forest Bar: Set, Valuation & Direct Links
    raw_ebay_url = generate_ebay_search_url(
        card_name=row["card_name"],
        set_name=row["set_name"],
        card_number=row["card_number"],
        edition=row["edition"],
        language=row["language"],
        is_raw=True,
    )
    pc_url = row.get("pricecharting_url") or get_pricecharting_search_url(row["card_name"], row["set_name"], row["card_number"])
    tcg_url = row.get("tcgplayer_url") or f"https://www.tcgplayer.com/search/pokemon/product?q={row['card_name']}+{row['set_name']}"

    st.markdown(
        f"""
        <div class="sketchbook-footer-bar">
            <div>
                <div style="font-size: 0.68rem; font-weight: 800; letter-spacing: 1px; text-transform: uppercase; color: #8da693;">SET</div>
                <div style="font-family: 'Fraunces', Georgia, serif; font-style: italic; font-size: 1.15rem; font-weight: 700; color: #f5f2eb;">{row['set_name']}</div>
            </div>
            <div>
                <div style="font-size: 0.68rem; font-weight: 800; letter-spacing: 1px; text-transform: uppercase; color: #8da693;">MARKET PRICE</div>
                <div style="font-family: 'Fraunces', Georgia, serif; font-size: 1.2rem; font-weight: 700; color: #d4af37;">
                    Raw: ${row['est_raw_price']:,.2f} • PSA 10: ${row['est_grade10_price']:,.2f}
                </div>
            </div>
            <div style="display: flex; gap: 8px;">
                <a href="{raw_ebay_url}" target="_blank" class="btn-ebay">🛒 Buy on eBay</a>
                <a href="{tcg_url}" target="_blank" class="btn-tcg">📦 Buy on TCGPlayer</a>
                <a href="{pc_url}" target="_blank" class="btn-pc">📊 Comps</a>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Collection Status & Toggle
    is_owned = bool(row["is_owned"])
    status_label = f"✅ In Your Collection ({row.get('owned_details', 'Owned')})" if is_owned else "❌ Not in Your Collection Yet"
    act_c1, act_c2, act_c3 = st.columns([2.5, 1.2, 1])
    with act_c1:
        st.markdown(f"**Collection Status:** {status_label}")
    with act_c2:
        if is_owned:
            if st.button("❌ Remove from Vault", key=f"modal_unmark_{card_id}", use_container_width=True):
                unmark_card_as_owned(row["id"])
                st.rerun()
        else:
            if st.button("✅ Mark as Owned", key=f"modal_mark_{card_id}", use_container_width=True):
                add_card_to_collection(
                    card_name=row["card_name"],
                    set_name=row["set_name"],
                    card_number=row["card_number"],
                    grading_company="RAW",
                    grade=0.0,
                    purchase_price=row["est_raw_price"] or 1.0,
                    purchase_date=datetime.now().strftime("%Y-%m-%d"),
                    edition=row["edition"],
                    language=row["language"],
                    master_card_id=row["id"],
                    image_url=row["image_url"],
                )
                st.rerun()
    with act_c3:
        if st.button("✕ Close", key=f"modal_close_{card_id}", use_container_width=True):
            st.session_state["modal_card_id"] = None
            if "inspect" in getattr(st, "query_params", {}):
                del st.query_params["inspect"]
            st.rerun()


if dialog_fn:
    @dialog_fn("Vulpix Collector's Field Guide", width="large")
    def show_card_dialog(card_id: int, active_df: pd.DataFrame):
        render_sketchbook_modal_content(card_id, active_df)
else:
    def show_card_dialog(card_id: int, active_df: pd.DataFrame):
        with st.container():
            render_sketchbook_modal_content(card_id, active_df)


# If modal_card_id is active, launch dialog
if st.session_state.get("modal_card_id") is not None:
    show_card_dialog(st.session_state["modal_card_id"], filtered_master)

# =========================================================
# Layout Mode 1: 4x4 Collector Binder (Image 2)
# =========================================================
if "Binder" in master_view_mode:
    with v_top1:
        st.markdown(f"**Found {len(filtered_master)} Cards in Binder**")
    with v_top2:
        page_size_options = [16, 32, 48, 96, "All"]
        per_page_choice = st.selectbox("Cards per binder spread:", page_size_options, index=0, key="m_binder_per_page")

    b_per_page = len(filtered_master) if per_page_choice == "All" or len(filtered_master) == 0 else int(per_page_choice)
    b_total_pages = max(1, (len(filtered_master) + b_per_page - 1) // b_per_page) if b_per_page > 0 else 1

    if b_total_pages > 1:
        b_pg1, b_pg2, b_pg3 = st.columns([1, 2, 1])
        with b_pg2:
            b_page_num = st.number_input(
                f"Binder Page (1 to {b_total_pages})",
                min_value=1,
                max_value=b_total_pages,
                value=1,
                step=1,
                key="m_binder_page_num",
            )
    else:
        b_page_num = 1

    b_start_idx = (b_page_num - 1) * b_per_page
    b_end_idx = min(b_start_idx + b_per_page, len(filtered_master))
    page_cards = filtered_master.iloc[b_start_idx:b_end_idx]

    if b_total_pages > 1:
        st.caption(f"Showing cards **{b_start_idx + 1}–{b_end_idx}** of **{len(filtered_master)}** (Binder Page {b_page_num} of {b_total_pages})")

    st.markdown('<div class="binder-page-container">', unsafe_allow_html=True)
    m_cols = st.columns(4)

    for idx, (_, row) in enumerate(page_cards.iterrows()):
        col_target = m_cols[idx % 4]
        with col_target:
            is_owned = bool(row["is_owned"])
            owned_cls = "owned-card" if is_owned else ""
            status_badge = (
                '<span style="background: rgba(16, 185, 129, 0.22); border: 1px solid #10b981; color: #6ee7b7; padding: 2px 8px; border-radius: 12px; font-weight: 700; font-size: 0.72rem;">✅ OWNED</span>'
                if is_owned
                else '<span style="background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; color: #fca5a5; padding: 2px 8px; border-radius: 12px; font-weight: 700; font-size: 0.72rem;">❌ MISSING</span>'
            )
            ed_badge = get_edition_badge_html(row.get("edition", "Unlimited"))
            err_badge = '<span class="badge-error">⚠️ ERROR</span>' if row["is_error"] == 1 else ""
            img_src = get_card_image_data_uri(row["image_url"] if row["image_url"] else DEFAULT_CARD_BACK_IMAGE)

            reg_val = str(row.get("region") or "International")
            reg_icon = "🇯🇵" if "japan" in reg_val.lower() else ("🇨🇳" if "china" in reg_val.lower() else "🌐")
            card_num_display = f"#{row['card_number']}" if row['card_number'] and str(row['card_number']).lower() != "nan" else "(Promo)"
            cameo_badge = '<span style="background: rgba(99, 102, 241, 0.2); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.4); border-radius: 4px; padding: 1px 6px; font-size: 0.68rem; font-weight: 700;">🎭 Cameo</span>' if row.get("is_cameo") == 1 else ""

            st.markdown(
                f"""
                <div class="binder-card-sleeve {owned_cls}">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <span style="font-size: 0.76rem; font-weight: 700; color: #8da693;">{reg_icon} {row['release_year']}</span>
                        <div style="display: flex; gap: 4px; align-items: center;">{cameo_badge} {status_badge}</div>
                    </div>
                    <div style="text-align: center; margin: 6px 0;">
                        <a href="?inspect={row['id']}" target="_self">
                            <img src="{img_src}" class="binder-card-img" title="Click to inspect {row['card_name']}" />
                        </a>
                    </div>
                    <div style="font-family: 'Fraunces', Georgia, serif; font-weight: 700; font-size: 0.95rem; color: #f5f2eb; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 4px;">
                        {row['card_name']}
                    </div>
                    <div style="color: #8da693; font-size: 0.74rem; margin-bottom: 6px;">
                        {row['set_name']} • {card_num_display}
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.74rem; background: rgba(0,0,0,0.25); padding: 4px 8px; border-radius: 6px; margin-bottom: 8px;">
                        <span style="color: #9cb3a2;">Raw: <strong style="color: #fde047;">${row['est_raw_price']:,.2f}</strong></span>
                        <span style="color: #9cb3a2;">PSA 10: <strong style="color: #d4af37;">${row['est_grade10_price']:,.2f}</strong></span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Direct Button to Inspect Card
            if st.button("🔍 Inspect Card", key=f"binder_btn_{row['id']}", use_container_width=True):
                st.session_state["modal_card_id"] = int(row["id"])
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# =========================================================
# Layout Mode 2: Consolidated Release Matrix
# =========================================================
elif "Consolidated" in master_view_mode:
    release_groups = get_consolidated_release_groups(filtered_master)
    with v_top1:
        st.markdown(f"**Found {len(release_groups)} Releases ({len(filtered_master)} Total Variants)**")
    with v_top2:
        rel_page_choice = st.selectbox("Releases per page:", [10, 20, 40, "All"], index=1, key="m_rel_per_page")

    r_per_page = len(release_groups) if rel_page_choice == "All" or len(release_groups) == 0 else int(rel_page_choice)
    r_total_pages = max(1, (len(release_groups) + r_per_page - 1) // r_per_page) if r_per_page > 0 else 1

    if r_total_pages > 1:
        r_pg1, r_pg2, r_pg3 = st.columns([1, 2, 1])
        with r_pg2:
            r_page_num = st.number_input(f"Page (1 to {r_total_pages})", min_value=1, max_value=r_total_pages, value=1, step=1, key="m_r_page_num")
    else:
        r_page_num = 1

    r_start_idx = (r_page_num - 1) * r_per_page
    r_end_idx = min(r_start_idx + r_per_page, len(release_groups))
    page_releases = release_groups[r_start_idx:r_end_idx]

    if r_total_pages > 1:
        st.caption(f"Showing releases **{r_start_idx + 1}–{r_end_idx}** of **{len(release_groups)}** (Page {r_page_num} of {r_total_pages})")

    for r_idx, rel in enumerate(page_releases):
        img_src = get_card_image_data_uri(rel["image_url"] if rel["image_url"] else DEFAULT_CARD_BACK_IMAGE)
        owned_cnt = rel["owned_variants"]
        total_cnt = rel["total_variants"]
        pct = rel["completion_pct"]
        prog_color = "#10b981" if owned_cnt == total_cnt and total_cnt > 0 else ("#34d399" if owned_cnt > 0 else "#8da693")

        # Build Language Chips
        lang_chips = []
        for l in rel["all_languages"]:
            if l in rel["owned_languages"]:
                chip = f'<span style="background: rgba(16, 185, 129, 0.22); color: #34d399; border: 1px solid #10b981; font-weight: 700; padding: 3px 10px; border-radius: 12px; font-size: 0.76rem; display: inline-flex; align-items: center; gap: 4px;">✅ {l}</span>'
            else:
                chip = f'<span style="background: #152618; color: #6b7280; border: 1px solid #23452b; padding: 3px 10px; border-radius: 12px; font-size: 0.76rem; display: inline-flex; align-items: center; opacity: 0.65;">{l}</span>'
            lang_chips.append(chip)
        lang_chips_html = " ".join(lang_chips)

        # Build Variant Chips
        var_chips = []
        for v in rel["variants"]:
            if v["is_owned"]:
                det = f' <span style="background: rgba(0,0,0,0.35); padding: 1px 6px; border-radius: 8px; font-size: 0.68rem; color: #a7f3d0;">{v["owned_details"]}</span>' if v["owned_details"] != "None" else ""
                chip = f'<span style="background: linear-gradient(135deg, rgba(6, 95, 70, 0.9), rgba(4, 120, 87, 0.9)); color: #ecfdf5; border: 1px solid #10b981; font-weight: 700; padding: 4px 10px; border-radius: 12px; font-size: 0.76rem; display: inline-flex; align-items: center; gap: 4px;">✅ {v["display_label"]}{det}</span>'
            else:
                chip = f'<span style="background: #112215; color: #7d9683; border: 1px solid #1c3623; padding: 4px 10px; border-radius: 12px; font-size: 0.76rem; display: inline-flex; align-items: center; opacity: 0.75;">{v["display_label"]}</span>'
            var_chips.append(chip)
        var_chips_html = " ".join(var_chips)

        raw_range = f"${rel['min_raw_price']:.2f}" if rel['min_raw_price'] == rel['max_raw_price'] and rel['min_raw_price'] > 0 else (f"${rel['min_raw_price']:.2f}–${rel['max_raw_price']:.2f}" if rel['max_raw_price'] > 0 else "—")
        g10_range = f"${rel['min_grade10_price']:.2f}" if rel['min_grade10_price'] == rel['max_grade10_price'] and rel['min_grade10_price'] > 0 else (f"${rel['min_grade10_price']:.2f}–${rel['max_grade10_price']:.2f}" if rel['max_grade10_price'] > 0 else "—")
        cnum_lbl = f"#{rel['card_number']}" if rel['card_number'] and str(rel['card_number']).lower() != "nan" else "(Promo)"
        cameo_pill = '<span style="background: rgba(99, 102, 241, 0.2); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.4); border-radius: 6px; padding: 2px 8px; font-size: 0.72rem; font-weight: 800; margin-left: 8px;">🎭 CAMEO</span>' if rel.get("is_cameo") else ""

        st.markdown(
            f"""
            <div class="slab-box" style="padding: 18px 22px; margin-bottom: 18px;">
                <div style="display: flex; gap: 24px; align-items: flex-start; flex-wrap: wrap;">
                    <div style="flex-shrink: 0; text-align: center; width: 130px;">
                        <img src="{img_src}" style="max-height: 180px; max-width: 130px; border-radius: 8px; box-shadow: 0 8px 18px rgba(0,0,0,0.5);" />
                        <div style="margin-top: 8px; font-size: 0.75rem; color: #8da693; font-weight: 700;">{rel['release_year']}</div>
                    </div>
                    <div style="flex: 1; min-width: 260px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; flex-wrap: wrap; gap: 8px;">
                            <div style="font-family: 'Fraunces', Georgia, serif; font-size: 1.35rem; font-weight: 700; color: #f5f2eb;">
                                {rel['card_name']}{cameo_pill}
                            </div>
                            <div style="font-family: 'Fraunces', Georgia, serif; font-size: 1.15rem; font-weight: 700; color: {prog_color};">
                                {owned_cnt} / {total_cnt} Variants Owned ({pct}%)
                            </div>
                        </div>
                        <div style="color: #9cb3a2; font-size: 0.88rem; margin-bottom: 12px;">
                            <strong>{rel['set_name']}</strong> • {cnum_lbl}
                        </div>
                        <div style="margin-bottom: 12px;">
                            <div style="font-size: 0.72rem; font-weight: 800; letter-spacing: 1px; color: #8da693; text-transform: uppercase; margin-bottom: 6px;">
                                🌐 Languages:
                            </div>
                            <div style="display: flex; gap: 6px; flex-wrap: wrap;">
                                {lang_chips_html}
                            </div>
                        </div>
                        <div style="margin-bottom: 14px;">
                            <div style="font-size: 0.72rem; font-weight: 800; letter-spacing: 1px; color: #8da693; text-transform: uppercase; margin-bottom: 6px;">
                                🏷️ Variants & Editions:
                            </div>
                            <div style="display: flex; gap: 6px; flex-wrap: wrap;">
                                {var_chips_html}
                            </div>
                        </div>
                        <div style="display: flex; gap: 20px; font-size: 0.82rem; color: #9cb3a2;">
                            <span>Est Raw: <strong style="color: #fde047;">{raw_range}</strong></span>
                            <span>Est PSA 10: <strong style="color: #d4af37;">{g10_range}</strong></span>
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander(f"🔍 View {len(rel['variants'])} Specific Variants & Comps for {rel['card_name']} ({rel['set_name']})"):
            for v in rel["variants"]:
                vc1, vc2, vc3, vc4, vc5 = st.columns([3, 1.2, 1.2, 1.2, 1.4])
                with vc1:
                    st.markdown(f"**{v['edition']}** ({v['language']}) — {v['rarity']}")
                    if v["is_owned"]:
                        st.caption(f"Status: ✅ {v['owned_details']}")
                    else:
                        st.caption("Status: ❌ Missing")
                with vc2:
                    st.metric("Raw", f"${v['est_raw_price']:.2f}" if v['est_raw_price'] > 0 else "—")
                with vc3:
                    st.metric("PSA 10", f"${v['est_grade10_price']:.2f}" if v['est_grade10_price'] > 0 else "—")
                with vc4:
                    raw_url = generate_ebay_search_url(
                        card_name=rel["card_name"],
                        set_name=rel["set_name"],
                        card_number=rel["card_number"],
                        edition=v["edition"],
                        language=v["language"],
                        is_raw=True,
                    )
                    st.markdown(f'<a href="{raw_url}" target="_blank" class="btn-ebay">🛒 eBay</a>', unsafe_allow_html=True)
                with vc5:
                    if v["is_owned"]:
                        if st.button("Unmark", key=f"unmark_{v['id']}", use_container_width=True):
                            unmark_card_as_owned(v["id"])
                            st.rerun()
                    else:
                        if st.button("Mark Owned", key=f"mark_{v['id']}", use_container_width=True):
                            add_card_to_collection(
                                card_name=rel["card_name"],
                                set_name=rel["set_name"],
                                card_number=rel["card_number"],
                                grading_company="RAW",
                                grade=0.0,
                                purchase_price=v["est_raw_price"] or 1.0,
                                purchase_date=datetime.now().strftime("%Y-%m-%d"),
                                edition=v["edition"],
                                language=v["language"],
                                master_card_id=v["id"],
                                image_url=rel["image_url"],
                            )
                            st.rerun()

# =========================================================
# Layout Mode 3: Table / List View
# =========================================================
else:
    with v_top1:
        st.markdown(f"**Found {len(filtered_master)} Cards in Catalog Table**")

    display_df = filtered_master.copy()
    display_df["Status"] = display_df["is_owned"].apply(lambda x: "✅ Owned" if x else "❌ Missing")
    display_df["Raw Price"] = display_df["est_raw_price"].apply(lambda x: f"${x:.2f}" if x > 0 else "—")
    display_df["PSA 10 Price"] = display_df["est_grade10_price"].apply(lambda x: f"${x:.2f}" if x > 0 else "—")
    display_df["Card #"] = display_df["card_number"].fillna("(No #)")
    display_df["Artist"] = display_df.get("artist", "Ken Sugimori")

    st.dataframe(
        display_df[["Status", "card_name", "set_name", "Card #", "release_year", "language", "edition", "Artist", "rarity", "Raw Price", "PSA 10 Price"]],
        use_container_width=True,
        hide_index=True,
    )
