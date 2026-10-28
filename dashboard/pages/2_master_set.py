"""
The Vulpix Vault - Page 2: Master Set Checklist & Catalog
Curated collector catalog, 4x4 binder sheet grid, modern collector card inspection modal,
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
    clean_html,
    get_edition_badge_html,
    get_pop_badge_html,
    get_variant_graphic_badge_html,
    render_header,
)

apply_custom_styles()
render_header()

# Clear any legacy inspect URL query parameter immediately so it never forces modal open on page load
if "inspect" in st.query_params:
    try:
        del st.query_params["inspect"]
    except Exception:
        pass

# Ensure dialog state exists
if "dialog_card_id" not in st.session_state:
    st.session_state["dialog_card_id"] = None
if "dialog_open" not in st.session_state:
    st.session_state["dialog_open"] = False

# Top Controls Bar: Cameo Filter
c_top_title, c_top_opt = st.columns([3, 2])
with c_top_title:
    st.markdown("### 📜 Vulpix Master Set Checklist & Catalog")
with c_top_opt:
    exclude_cameos = st.checkbox(
        "🚫 Exclude Background Cameos Only (Rumble / Sapporo Pikachu)",
        value=True,
        help="When checked, non-Vulpix cards where Vulpix only appears as a small background cameo (e.g. Rumble Pikachu, Sapporo Pikachu) are hidden. Costume cards like Poncho-wearing Pikachu remain included in your core collection.",
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

try:
    owned_unique_count = df_count_base[df_count_base["is_owned"]].groupby(["card_name", "set_name", "card_number"]).ngroups
except Exception:
    owned_unique_count = int(master_metrics.get("owned_cards", 0))

owned_total_count = int(master_metrics.get("owned_cards", 0))
unique_pct = round(100.0 * owned_unique_count / max(1, unique_printings), 1)
additional_variants = max(0, len(df_count_base) - unique_printings)
total_master_count = len(df_count_base)

# =========================================================
# Editorial Header & Valuation Breakdown (Obsidian & Gold)
# =========================================================
cameo_sub_badge = ' <span style="font-size: 0.74rem; font-weight: 600; color: #94a3b8; background: #1a202c; padding: 2px 8px; border-radius: 6px; border: 1px solid #2d3748;">Background Cameos Excluded</span>' if exclude_cameos else ""

hero_html = clean_html(f"""
<div class="cottage-hero">
    <h2 class="cottage-hero-title">Vulpix Master Set Collection Progress</h2>
    <div class="cottage-stats-grid">
        <div class="cottage-stat-item" style="border: 1px solid rgba(16, 185, 129, 0.5); background: rgba(16, 185, 129, 0.08);">
            <div class="cottage-stat-label" style="color: #6ee7b7;">VAULT PROGRESS</div>
            <div class="cottage-stat-val" style="color: #34d399;">{owned_unique_count} / {unique_printings} Cards</div>
        </div>
        <div class="cottage-stat-item">
            <div class="cottage-stat-label">TOTAL VARIATIONS</div>
            <div class="cottage-stat-val">{owned_total_count} / {total_master_count} Cards</div>
        </div>
        <div class="cottage-stat-item"><div class="cottage-stat-label">ENGLISH</div><div class="cottage-stat-val">{english_count} cards</div></div>
        <div class="cottage-stat-item"><div class="cottage-stat-label">JAPANESE</div><div class="cottage-stat-val">{japanese_count} cards</div></div>
        <div class="cottage-stat-item"><div class="cottage-stat-label">S. CHINESE</div><div class="cottage-stat-val">{chinese_count} cards</div></div>
        <div class="cottage-stat-item"><div class="cottage-stat-label">PROMOS</div><div class="cottage-stat-val">{promo_count} cards</div></div>
    </div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
        <div style="font-family: 'Fraunces', 'Plus Jakarta Sans', Georgia, serif; font-size: 1.25rem; font-weight: 700; color: #f8fafc;">
            Master Set Progress: <span style="color: #34d399;">{owned_unique_count} / {unique_printings} Unique Cards ({unique_pct}%)</span>{cameo_sub_badge}
        </div>
        <div style="font-family: 'Fraunces', 'Plus Jakarta Sans', Georgia, serif; font-size: 1.4rem; font-weight: 700; color: #10b981;">{unique_pct}%</div>
    </div>
    <div class="progress-bar-bg"><div class="progress-bar-fill" style="width: {unique_pct}%;"></div></div>
    <div style="display: flex; justify-content: space-between; font-size: 0.85rem; color: #94a3b8; flex-wrap: wrap; gap: 8px; margin-top: 10px;">
        <span>Unique Cards Owned: <strong style="color: #34d399;">{owned_unique_count}</strong> / {unique_printings} ({unique_pct}%)</span>
        <span>Total Variations Owned: <strong style="color: #fbbf24;">{owned_total_count}</strong> / {total_master_count} ({master_metrics['completion_pct']}%)</span>
        <span>Missing: <strong style="color: #f87171;">{master_metrics['missing_cards']}</strong> cards</span>
        <span>Est. Cost to Complete: <strong style="color: #fbbf24;">${master_metrics['cost_to_complete_raw']:,.2f} Raw</strong> • <strong style="color: #f59e0b;">${master_metrics['cost_to_complete_grade10']:,.2f} PSA 10</strong></span>
        <span>Total Vault Value: <strong style="color: #34d399;">${master_metrics['total_raw_value']:,.2f} Raw</strong> • <strong style="color: #fbbf24;">${master_metrics['total_grade10_value']:,.2f} PSA 10</strong></span>
    </div>
    <div style="margin-top: 20px;">
        <div class="cottage-oval-banner">
            <span>How Many Cards Are in the Vulpix Master Set?</span>
            <span class="cottage-oval-pill">{total_master_count} Variations ({unique_printings} Unique Printings)</span>
        </div>
    </div>
</div>
""")
st.markdown(hero_html, unsafe_allow_html=True)

# Admin & Sync Tools in a clean, non-intrusive collapsed expander
with st.expander("⚙️ Catalog Management & Offline Scans", expanded=False):
    st.markdown("💡 *Synchronize with the official PokeCottage Grand Master Set or download verified high-res scans for instant offline browsing.*")
    ac1, ac2, ac3 = st.columns(3)
    with ac1:
        if st.button("✨ Auto-Enrich Names", key="btn_auto_enrich_master", use_container_width=True):
            with st.spinner("Resolving card names and fetching official scans..."):
                cnt, msg = auto_enrich_master_catalog(force_all=True)
                st.success(msg)
                st.rerun()
    with ac2:
        if st.button("⚡ Cache Scans Locally", key="btn_download_images_local", use_container_width=True):
            with st.spinner("Downloading high-res images to server for instant offline loading..."):
                d_cnt, d_msg = download_all_card_images_locally()
                st.success(d_msg)
                st.rerun()
    with ac3:
        if st.button("🏡 Sync PokeCottage", key="btn_sync_pokecottage", use_container_width=True):
            with st.spinner("Fetching latest PokeCottage Grand Master Set checklist & scans..."):
                s_ok, s_msg = sync_pokecottage_catalog()
                if s_ok:
                    st.success(s_msg)
                else:
                    st.warning(s_msg)
                st.rerun()

# =========================================================
# Streamlined Filter Controls Bar
# =========================================================
f_col1, f_col2, f_col3, f_col4 = st.columns([1.8, 1.2, 1.2, 1.2])
with f_col1:
    m_search = st.text_input("Search Cards", placeholder="🔍 Search card name, set, or #...", label_visibility="collapsed")
with f_col2:
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
        label_visibility="collapsed"
    )
with f_col3:
    m_langs = ["All Languages"] + sorted(df_master["language"].dropna().unique().tolist())
    m_sel_lang = st.selectbox("Language Filter", m_langs, label_visibility="collapsed")
with f_col4:
    m_eds = ["All Editions"] + sorted(df_master["edition"].dropna().unique().tolist())
    m_sel_ed = st.selectbox("Edition Filter", m_eds, label_visibility="collapsed")

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
# Collector Showcase Card Detail Dialog
# =========================================================
dialog_fn = getattr(st, "dialog", getattr(st, "experimental_dialog", None))


def render_sketchbook_modal_content(card_id: int, active_df: pd.DataFrame):
    """Renders the sleek obsidian collector showcase card detail dialog."""
    matches = active_df[active_df["id"] == card_id]
    if matches.empty:
        # Fallback to df_master if active filter doesn't have it
        matches = df_master[df_master["id"] == card_id]
        if matches.empty:
            st.warning("Card not found.")
            return

    row = matches.iloc[0]
    id_list = active_df["id"].tolist()
    if card_id in id_list:
        curr_idx = id_list.index(card_id)
        total_in_view = len(id_list)
    else:
        curr_idx = 0
        total_in_view = len(id_list) if len(id_list) > 0 else 1

    # Top Navigation Row (< 1 / 251 >)
    nav_c1, nav_c2, nav_c3 = st.columns([1, 2, 1])
    with nav_c1:
        if curr_idx > 0:
            prev_id = id_list[curr_idx - 1]
            if st.button("⬅ Previous", key=f"btn_prev_{card_id}", use_container_width=True):
                st.session_state["dialog_card_id"] = prev_id
                st.session_state["dialog_open"] = True
                st.rerun()
        else:
            st.caption("First Card")
    with nav_c2:
        top_title_html = clean_html(f"""
        <div style="text-align: center;">
            <div style="font-family: 'Fraunces', 'Plus Jakarta Sans', Georgia, serif; font-style: italic; font-size: 1.7rem; font-weight: 700; color: #f8fafc; margin: 0;">
                {row['card_name']}
            </div>
            <div style="font-size: 0.76rem; font-weight: 800; letter-spacing: 1.5px; text-transform: uppercase; color: #f59e0b;">
                {row['set_name']} • {row['language']} • ({curr_idx + 1} / {total_in_view})
            </div>
        </div>
        """)
        st.markdown(top_title_html, unsafe_allow_html=True)
    with nav_c3:
        if curr_idx < total_in_view - 1:
            next_id = id_list[curr_idx + 1]
            if st.button("Next ➡", key=f"btn_next_{card_id}", use_container_width=True):
                st.session_state["dialog_card_id"] = next_id
                st.session_state["dialog_open"] = True
                st.rerun()
        else:
            st.caption("Last Card")

    # Sanitize artist name
    artist_raw = str(row.get("artist") or "").strip()
    if not artist_raw or artist_raw.lower() in ("nan", "none", ""):
        artist_name = "Ken Sugimori"
    else:
        artist_name = artist_raw

    # Sanitize card number
    cnum_raw = str(row.get("card_number") or "").strip()
    if not cnum_raw or cnum_raw.lower() in ("nan", "none", "no number", "nan/nan", ""):
        if "japanese" in str(row.get("language", "")).lower() and ("base" in str(row.get("set_name", "")).lower() or "expansion" in str(row.get("set_name", "")).lower()):
            cnum_display = "No. 015"
        elif "darkness" in str(row.get("set_name", "")).lower() or "neo destiny" in str(row.get("set_name", "")).lower():
            cnum_display = "No. 037"
        else:
            cnum_display = "Promo / Unnumbered"
    elif not cnum_raw.startswith("#") and not cnum_raw.startswith("No."):
        cnum_display = f"#{cnum_raw}"
    else:
        cnum_display = cnum_raw

    # Sanitize release year
    ryear = row.get("release_year")
    if not ryear or str(ryear).lower() in ("nan", "none", "0"):
        if "darkness" in str(row.get("set_name", "")).lower():
            ryear = 2001
        elif "expansion" in str(row.get("set_name", "")).lower() or "japanese base" in str(row.get("set_name", "")).lower():
            ryear = 1996
        else:
            ryear = 1999

    # Sanitize image URL
    row_img = row.get("image_url")
    if "darkness" in str(row.get("set_name", "")).lower():
        row_img = "dashboard/static/cards/vulpix-darkness-and-to-light-no-014.jpg"
    elif "japanese" in str(row.get("language", "")).lower() and ("base" in str(row.get("set_name", "")).lower() or "expansion" in str(row.get("set_name", "")).lower()):
        if not row_img or "vulpix_base_set_68_102" in str(row_img) or "vulpix-base-expansion-pack-006-128" in str(row_img):
            row_img = "dashboard/static/cards/vulpix-expansion-pack-no-015.jpg"

    img_src = get_card_image_data_uri(row_img if row_img else DEFAULT_CARD_BACK_IMAGE)
    finish_style = row.get("finish") or row.get("edition") or "Standard"
    rarity_name = row.get("rarity") or "Common"

    # Variant graphic badge
    variant_badge_html = get_variant_graphic_badge_html(finish_style, row.get("edition"))

    # Dynamic educational collector's note (strip awkward 'Variant: ...' strings)
    raw_note = str(row.get("notes") or "").strip()
    for prefix in ("Variant:", "variant:", "PokeCottage:"):
        if prefix in raw_note:
            raw_note = raw_note.replace(prefix, "").strip()

    if raw_note and len(raw_note) > 4 and raw_note.lower() not in ("none", "nan", "standard", "non-holo", "holo"):
        collector_note = raw_note
    else:
        collector_note = f"Authentic {row['language']} printing from the {row['set_name']} expansion ({ryear}) illustrated by {artist_name}."

    st.markdown('<div class="sketchbook-modal">', unsafe_allow_html=True)
    b_col1, b_col2, b_col3 = st.columns([1, 1.4, 1.2])

    with b_col1:
        col1_html = clean_html(f"""
        <div style="padding: 10px 0;">
            <div class="sketchbook-annot-label">CARD NUMBER</div>
            <div class="sketchbook-annot-val">{cnum_display}</div>
            <div class="sketchbook-annot-label">ILLUSTRATOR</div>
            <div class="sketchbook-annot-val">{artist_name}</div>
            <div class="sketchbook-annot-label">RELEASE YEAR</div>
            <div class="sketchbook-annot-val">{ryear}</div>
            <div class="sketchbook-annot-label">LANGUAGE</div>
            <div class="sketchbook-annot-val">{row['language']}</div>
        </div>
        """)
        st.markdown(col1_html, unsafe_allow_html=True)

    with b_col2:
        col2_html = clean_html(f"""
        <div style="text-align: center; padding: 6px 0;">
            <img src="{img_src}" style="max-height: 380px; max-width: 100%; border-radius: 12px; box-shadow: 0 16px 36px rgba(0,0,0,0.6); border: 1px solid rgba(255,255,255,0.08);" />
            <div style="font-size: 0.72rem; color: #94a3b8; font-style: italic; margin-top: 8px;">
                Verified Pokémon TCG master scan
            </div>
        </div>
        """)
        st.markdown(col2_html, unsafe_allow_html=True)

    with b_col3:
        col3_html = clean_html(f"""
        <div style="padding: 10px 0;">
            <div class="sketchbook-annot-label">RARITY</div>
            <div class="sketchbook-annot-val">{rarity_name}</div>
            <div class="sketchbook-annot-label">CARD VARIANT / FINISH</div>
            <div style="margin-bottom: 14px;">{variant_badge_html}</div>
            <div class="sketchbook-annot-label">COLLECTOR'S NOTE</div>
            <div class="sketchbook-note-card">
                "{collector_note}"
            </div>
        </div>
        """)
        st.markdown(col3_html, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # Bottom Sleek Bar: Set, Valuation & Direct Links
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

    footer_html = clean_html(f"""
    <div class="sketchbook-footer-bar">
        <div>
            <div style="font-size: 0.68rem; font-weight: 800; letter-spacing: 1px; text-transform: uppercase; color: #94a3b8;">SET</div>
            <div style="font-family: 'Fraunces', 'Plus Jakarta Sans', Georgia, serif; font-style: italic; font-size: 1.15rem; font-weight: 700; color: #f8fafc;">{row['set_name']}</div>
        </div>
        <div>
            <div style="font-size: 0.68rem; font-weight: 800; letter-spacing: 1px; text-transform: uppercase; color: #94a3b8;">MARKET PRICE</div>
            <div style="font-family: 'Fraunces', 'Plus Jakarta Sans', Georgia, serif; font-size: 1.2rem; font-weight: 700; color: #fbbf24;">
                Raw: ${row['est_raw_price']:,.2f} • PSA 10: ${row['est_grade10_price']:,.2f}
            </div>
        </div>
        <div style="display: flex; gap: 8px;">
            <a href="{raw_ebay_url}" target="_blank" class="btn-ebay">🛒 Buy on eBay</a>
            <a href="{tcg_url}" target="_blank" class="btn-tcg">📦 Buy on TCGPlayer</a>
            <a href="{pc_url}" target="_blank" class="btn-pc">📊 Comps</a>
        </div>
    </div>
    """)
    st.markdown(footer_html, unsafe_allow_html=True)

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
                st.session_state["dialog_open"] = True
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
                st.session_state["dialog_open"] = True
                st.rerun()
    with act_c3:
        if st.button("✕ Close", key=f"modal_close_{card_id}", use_container_width=True):
            st.session_state["dialog_card_id"] = None
            st.session_state["dialog_open"] = False
            st.rerun()


if dialog_fn:
    @dialog_fn("Vulpix Collector's Showcase", width="large")
    def show_card_dialog(card_id: int, active_df: pd.DataFrame):
        render_sketchbook_modal_content(card_id, active_df)
else:
    def show_card_dialog(card_id: int, active_df: pd.DataFrame):
        with st.container():
            render_sketchbook_modal_content(card_id, active_df)


# Only launch dialog if dialog_open flag was actively set by a user button click
if st.session_state.get("dialog_open") and st.session_state.get("dialog_card_id") is not None:
    st.session_state["dialog_open"] = False  # Reset immediately so refresh / close NEVER reopens it!
    show_card_dialog(st.session_state["dialog_card_id"], filtered_master)

# =========================================================
# Layout Mode 1: 4x4 Collector Binder (Default)
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
                '<span style="background: rgba(16, 185, 129, 0.18); border: 1px solid #10b981; color: #6ee7b7; padding: 2px 8px; border-radius: 12px; font-weight: 700; font-size: 0.72rem;">✅ OWNED</span>'
                if is_owned
                else '<span style="background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; color: #fca5a5; padding: 2px 8px; border-radius: 12px; font-weight: 700; font-size: 0.72rem;">❌ MISSING</span>'
            )
            ed_badge = get_edition_badge_html(row.get("edition", "Unlimited"))
            err_badge = '<span class="badge-error">⚠️ ERROR</span>' if row.get("is_error") == 1 else ""
            img_src = get_card_image_data_uri(row["image_url"] if row["image_url"] else DEFAULT_CARD_BACK_IMAGE)

            reg_val = str(row.get("region") or "International")
            reg_icon = "🇯🇵" if "japan" in reg_val.lower() else ("🇨🇳" if "china" in reg_val.lower() else "🌐")
            
            cnum_raw_item = str(row.get("card_number") or "").strip()
            if not cnum_raw_item or cnum_raw_item.lower() in ("nan", "none", "no number", ""):
                card_num_display = "(No #)"
            elif not cnum_raw_item.startswith("#") and not cnum_raw_item.startswith("No."):
                card_num_display = f"#{cnum_raw_item}"
            else:
                card_num_display = cnum_raw_item

            cameo_badge = '<span style="background: rgba(99, 102, 241, 0.2); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.4); border-radius: 4px; padding: 1px 6px; font-size: 0.68rem; font-weight: 700;">🎭 Cameo</span>' if row.get("is_cameo") == 1 else ""

            ryear_item = row.get("release_year") or 2000

            card_sleeve_html = clean_html(f"""
            <div class="binder-card-sleeve {owned_cls}">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span style="font-size: 0.76rem; font-weight: 700; color: #94a3b8;">{reg_icon} {ryear_item}</span>
                    <div style="display: flex; gap: 4px; align-items: center;">{err_badge} {cameo_badge} {status_badge}</div>
                </div>
                <div style="text-align: center; margin: 6px 0;">
                    <img src="{img_src}" class="binder-card-img" />
                </div>
                <div style="font-family: 'Fraunces', 'Plus Jakarta Sans', Georgia, serif; font-weight: 700; font-size: 0.95rem; color: #f8fafc; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 4px;">
                    {row['card_name']}
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span style="color: #94a3b8; font-size: 0.74rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 60%;">{row['set_name']} • {card_num_display}</span>
                    <div>{ed_badge}</div>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 0.74rem; background: rgba(0,0,0,0.3); padding: 4px 8px; border-radius: 6px; margin-bottom: 8px;">
                    <span style="color: #94a3b8;">Raw: <strong style="color: #fbbf24;">${row['est_raw_price']:,.2f}</strong></span>
                    <span style="color: #94a3b8;">PSA 10: <strong style="color: #f59e0b;">${row['est_grade10_price']:,.2f}</strong></span>
                </div>
            </div>
            """)
            st.markdown(card_sleeve_html, unsafe_allow_html=True)

            # Direct Button to Inspect Card
            if st.button("🔍 Inspect Details", key=f"binder_btn_{row['id']}", use_container_width=True):
                st.session_state["dialog_card_id"] = int(row["id"])
                st.session_state["dialog_open"] = True
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
        prog_color = "#10b981" if owned_cnt == total_cnt and total_cnt > 0 else ("#34d399" if owned_cnt > 0 else "#94a3b8")

        # Build Language Chips
        lang_chips = []
        for l in rel["all_languages"]:
            if l in rel["owned_languages"]:
                chip = f'<span style="background: rgba(16, 185, 129, 0.18); color: #34d399; border: 1px solid #10b981; font-weight: 700; padding: 3px 10px; border-radius: 12px; font-size: 0.76rem; display: inline-flex; align-items: center; gap: 4px;">✅ {l}</span>'
            else:
                chip = f'<span style="background: #1a202e; color: #64748b; border: 1px solid #283347; padding: 3px 10px; border-radius: 12px; font-size: 0.76rem; display: inline-flex; align-items: center; opacity: 0.7;">{l}</span>'
            lang_chips.append(chip)
        lang_chips_html = " ".join(lang_chips)

        # Build Variant Chips
        var_chips = []
        for v in rel["variants"]:
            if v["is_owned"]:
                det = f' <span style="background: rgba(0,0,0,0.35); padding: 1px 6px; border-radius: 8px; font-size: 0.68rem; color: #a7f3d0;">{v["owned_details"]}</span>' if v["owned_details"] != "None" else ""
                chip = f'<span style="background: linear-gradient(135deg, rgba(16, 185, 129, 0.8), rgba(5, 150, 105, 0.8)); color: #ecfdf5; border: 1px solid #10b981; font-weight: 700; padding: 4px 10px; border-radius: 12px; font-size: 0.76rem; display: inline-flex; align-items: center; gap: 4px;">✅ {v["display_label"]}{det}</span>'
            else:
                chip = f'<span style="background: #161b26; color: #94a3b8; border: 1px solid #242c3d; padding: 4px 10px; border-radius: 12px; font-size: 0.76rem; display: inline-flex; align-items: center; opacity: 0.8;">{v["display_label"]}</span>'
            var_chips.append(chip)
        var_chips_html = " ".join(var_chips)

        raw_range = f"${rel['min_raw_price']:.2f}" if rel['min_raw_price'] == rel['max_raw_price'] and rel['min_raw_price'] > 0 else (f"${rel['min_raw_price']:.2f}–${rel['max_raw_price']:.2f}" if rel['max_raw_price'] > 0 else "—")
        g10_range = f"${rel['min_grade10_price']:.2f}" if rel['min_grade10_price'] == rel['max_grade10_price'] and rel['min_grade10_price'] > 0 else (f"${rel['min_grade10_price']:.2f}–${rel['max_grade10_price']:.2f}" if rel['max_grade10_price'] > 0 else "—")
        cnum_lbl = f"#{rel['card_number']}" if rel['card_number'] and str(rel['card_number']).lower() != "nan" else "(Promo)"
        cameo_pill = '<span style="background: rgba(99, 102, 241, 0.2); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.4); border-radius: 6px; padding: 2px 8px; font-size: 0.72rem; font-weight: 800; margin-left: 8px;">🎭 CAMEO</span>' if rel.get("is_cameo") else ""

        rel_box_html = clean_html(f"""
        <div class="slab-box" style="padding: 18px 22px; margin-bottom: 18px;">
            <div style="display: flex; gap: 24px; align-items: flex-start; flex-wrap: wrap;">
                <div style="flex-shrink: 0; text-align: center; width: 130px;">
                    <img src="{img_src}" style="max-height: 180px; max-width: 130px; border-radius: 8px; box-shadow: 0 8px 18px rgba(0,0,0,0.5); border: 1px solid rgba(255,255,255,0.08);" />
                    <div style="margin-top: 8px; font-size: 0.75rem; color: #94a3b8; font-weight: 700;">{rel['release_year']}</div>
                </div>
                <div style="flex: 1; min-width: 260px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; flex-wrap: wrap; gap: 8px;">
                        <div style="font-family: 'Fraunces', 'Plus Jakarta Sans', Georgia, serif; font-size: 1.35rem; font-weight: 700; color: #f8fafc;">
                            {rel['card_name']}{cameo_pill}
                        </div>
                        <div style="font-family: 'Fraunces', 'Plus Jakarta Sans', Georgia, serif; font-size: 1.15rem; font-weight: 700; color: {prog_color};">
                            {owned_cnt} / {total_cnt} Variants Owned ({pct}%)
                        </div>
                    </div>
                    <div style="color: #94a3b8; font-size: 0.88rem; margin-bottom: 12px;">
                        <strong>{rel['set_name']}</strong> • {cnum_lbl}
                    </div>
                    <div style="margin-bottom: 12px;">
                        <div style="font-size: 0.72rem; font-weight: 800; letter-spacing: 1px; color: #94a3b8; text-transform: uppercase; margin-bottom: 6px;">
                            🌐 Languages:
                        </div>
                        <div style="display: flex; gap: 6px; flex-wrap: wrap;">
                            {lang_chips_html}
                        </div>
                    </div>
                    <div style="margin-bottom: 14px;">
                        <div style="font-size: 0.72rem; font-weight: 800; letter-spacing: 1px; color: #94a3b8; text-transform: uppercase; margin-bottom: 6px;">
                            🏷️ Variants & Editions:
                        </div>
                        <div style="display: flex; gap: 6px; flex-wrap: wrap;">
                            {var_chips_html}
                        </div>
                    </div>
                    <div style="display: flex; gap: 20px; font-size: 0.82rem; color: #94a3b8;">
                        <span>Est Raw: <strong style="color: #fbbf24;">{raw_range}</strong></span>
                        <span>Est PSA 10: <strong style="color: #f59e0b;">{g10_range}</strong></span>
                    </div>
                </div>
            </div>
        </div>
        """)
        st.markdown(rel_box_html, unsafe_allow_html=True)

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
