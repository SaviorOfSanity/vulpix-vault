"""
The Vulpix Vault - Page 2: Master Set Checklist & Catalog
Curated 240+ cards catalog, smart filtering, fast pagination, 1-click owned toggle,
and Google Sheets sync.
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

master_metrics = get_master_set_metrics()
df_master = load_master_catalog_df()

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
en_col1, en_col2, en_col3 = st.columns([2, 1.2, 1.2])
with en_col1:
    st.markdown(
        "💡 *Card name missing or showing wrong artwork? Click to resolve exact names and download verified official card scans directly to your local server.*"
    )
with en_col2:
    if st.button("✨ Auto-Enrich Names & Images", key="btn_auto_enrich_master", use_container_width=True):
        with st.spinner("Resolving card names and fetching official scans..."):
            cnt, msg = auto_enrich_master_catalog(force_all=True)
            st.success(msg)
            st.rerun()
with en_col3:
    if st.button("⚡ Cache Scans Locally", key="btn_download_images_local", use_container_width=True):
        with st.spinner("Downloading high-res images to server for instant offline loading..."):
            d_cnt, d_msg = download_all_card_images_locally()
            st.success(d_msg)
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

# Pagination & Layout Header
m_top1, m_top2, m_top3 = st.columns([2.2, 1.3, 2.5])
with m_top3:
    master_view_mode = st.radio(
        "Display Layout:",
        ["🗂️ Consolidated Release Matrix", "🃏 Full Individual Cards Grid", "📋 Table / List View"],
        horizontal=True,
        key="master_v_mode",
    )

if "Consolidated" in master_view_mode:
    release_groups = get_consolidated_release_groups(filtered_master)
    with m_top1:
        st.markdown(f"**Found {len(release_groups)} Releases ({len(filtered_master)} Total Variants)**")
    with m_top2:
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
                chip = f'<span style="background: rgba(16, 185, 129, 0.22); color: #34d399; border: 1px solid #10b981; font-weight: 700; padding: 3px 10px; border-radius: 12px; font-size: 0.76rem; display: inline-flex; align-items: center; gap: 4px; box-shadow: 0 0 8px rgba(16, 185, 129, 0.25);">✅ {l}</span>'
            else:
                chip = f'<span style="background: #181b23; color: #6b7280; border: 1px solid #2d3748; padding: 3px 10px; border-radius: 12px; font-size: 0.76rem; display: inline-flex; align-items: center; opacity: 0.65;">{l}</span>'
            lang_chips.append(chip)
        lang_chips_html = " ".join(lang_chips)

        # Build Variant Chips
        var_chips = []
        for v in rel["variants"]:
            if v["is_owned"]:
                det = f' <span style="background: rgba(0,0,0,0.35); padding: 1px 6px; border-radius: 8px; font-size: 0.68rem; color: #a7f3d0;">{v["owned_details"]}</span>' if v["owned_details"] != "None" else ""
                chip = f'<span style="background: linear-gradient(135deg, rgba(6, 95, 70, 0.9), rgba(4, 120, 87, 0.9)); color: #ecfdf5; border: 1px solid #10b981; font-weight: 700; padding: 4px 10px; border-radius: 12px; font-size: 0.76rem; display: inline-flex; align-items: center; gap: 4px; box-shadow: 0 2px 6px rgba(16, 185, 129, 0.3);">✅ {v["display_label"]}{det}</span>'
            else:
                chip = f'<span style="background: #131722; color: #71717a; border: 1px solid #232936; padding: 4px 10px; border-radius: 12px; font-size: 0.76rem; display: inline-flex; align-items: center; opacity: 0.75;">{v["display_label"]}</span>'
            var_chips.append(chip)
        var_chips_html = " ".join(var_chips)

        raw_range = f"${rel['min_raw_price']:.2f}" if rel['min_raw_price'] == rel['max_raw_price'] and rel['min_raw_price'] > 0 else (f"${rel['min_raw_price']:.2f}–${rel['max_raw_price']:.2f}" if rel['max_raw_price'] > 0 else "—")
        g10_range = f"${rel['min_grade10_price']:.2f}" if rel['min_grade10_price'] == rel['max_grade10_price'] and rel['min_grade10_price'] > 0 else (f"${rel['min_grade10_price']:.2f}–${rel['max_grade10_price']:.2f}" if rel['max_grade10_price'] > 0 else "—")

        card_num_str = f"#{rel['card_number']}" if rel['card_number'] and str(rel['card_number']).lower() != "nan" else "(Promo / No #)"

        rel_html = f"""<div class="slab-box" style="padding: 16px; margin-bottom: 12px; border-radius: 12px; background: #131722; border: 1px solid #232936;">
<div style="display: flex; gap: 18px; align-items: flex-start;">
<div style="flex: 0 0 100px; text-align: center;">
<img src="{img_src}" loading="lazy" decoding="async" style="max-height: 140px; max-width: 100%; border-radius: 6px; box-shadow: 0 4px 10px rgba(0,0,0,0.5);" />
<div style="margin-top: 6px; font-size: 0.75rem; font-weight: 700; color: #8c8d9a;">{rel['release_year']}</div>
</div>
<div style="flex: 1; min-width: 0;">
<div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 6px; margin-bottom: 6px;">
<div>
<span style="font-size: 1.15rem; font-weight: 800; color: #ffffff;">{rel['card_name']}</span>
<span style="color: #94a3b8; font-size: 0.88rem; margin-left: 8px;">{rel['set_name']} • {card_num_str}</span>
</div>
<div style="text-align: right;">
<span style="font-size: 0.84rem; font-weight: 700; color: {prog_color};">{owned_cnt} / {total_cnt} Variants Owned ({pct}%)</span>
</div>
</div>
<div style="height: 6px; background: #1e293b; border-radius: 4px; overflow: hidden; margin-bottom: 12px;">
<div style="width: {pct}%; height: 100%; background: linear-gradient(90deg, #10b981, #34d399); border-radius: 4px;"></div>
</div>
<div style="margin-bottom: 10px;">
<div style="font-size: 0.72rem; font-weight: 700; color: #8c8d9a; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px;">
🌐 Languages:
</div>
<div style="display: flex; gap: 5px; flex-wrap: wrap; align-items: center;">
{lang_chips_html}
</div>
</div>
<div style="margin-bottom: 8px;">
<div style="font-size: 0.72rem; font-weight: 700; color: #8c8d9a; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px;">
🏷️ Variants & Editions:
</div>
<div style="display: flex; gap: 5px; flex-wrap: wrap; align-items: center;">
{var_chips_html}
</div>
</div>
<div style="display: flex; gap: 16px; font-size: 0.78rem; color: #8c8d9a; margin-top: 6px;">
<span>Est Raw: <strong style="color: #ffd591;">{raw_range}</strong></span>
<span>Est PSA 10: <strong style="color: #f59e0b;">{g10_range}</strong></span>
</div>
</div>
</div>
</div>"""

        st.markdown(rel_html, unsafe_allow_html=True)

        with st.expander(f"🔍 View {len(rel['variants'])} Specific Variants & Comps for {rel['card_name']} ({rel['set_name']})", expanded=False):
            sub_cols = st.columns(min(3, max(1, len(rel["variants"]))))
            for v_i, var in enumerate(rel["variants"]):
                with sub_cols[v_i % len(sub_cols)]:
                    var_owned = var["is_owned"]
                    v_raw_display = f"${var['est_raw_price']:,.2f}" if var['est_raw_price'] > 0 else "—"
                    v_g10_display = f"${var['est_grade10_price']:,.2f}" if var['est_grade10_price'] > 0 else "—"
                    v_g9_display = f"${var['pricecharting_grade9']:,.2f}" if var['pricecharting_grade9'] > 0 else None

                    st.markdown(f"""<div style="background: #0d1017; border: 1px solid {'#10b981' if var_owned else '#1f2937'}; border-radius: 8px; padding: 10px; margin-bottom: 8px;">
<div style="font-weight: 700; font-size: 0.85rem; color: #ffffff;">{'✅ ' if var_owned else ''}{var['display_label']}</div>
<div style="font-size: 0.75rem; color: #8c8d9a; margin-bottom: 4px;">Language: {var['language']} • #{var['card_number']}</div>
<div style="font-size: 0.75rem; color: #ffd591;">Raw: <strong>{v_raw_display}</strong> • PSA 10: <strong style="color: #f59e0b;">{v_g10_display}</strong></div>
{f'<div style="font-size: 0.75rem; color: #60a5fa;">PriceCharting Grade 9: <strong>{v_g9_display}</strong></div>' if v_g9_display else ''}
{f'<div style="font-size: 0.72rem; color: #34d399; margin-top: 3px;">In Vault: {var["owned_details"]}</div>' if var_owned else ''}
</div>""", unsafe_allow_html=True)

                    raw_ebay_url = generate_ebay_search_url(
                        card_name=var["card_name"],
                        set_name=var["set_name"],
                        card_number=var["card_number"],
                        edition=var["edition"],
                        language=var["language"],
                        is_raw=True,
                    )
                    g10_ebay_url = generate_ebay_search_url(
                        card_name=var["card_name"],
                        set_name=var["set_name"],
                        card_number=var["card_number"],
                        edition=var["edition"],
                        language=var["language"],
                        grade_tier="Gem Mint 10",
                    )
                    pc_url = var["pricecharting_url"] or get_pricecharting_search_url(var["card_name"], var["set_name"], var["card_number"])

                    b_c1, b_c2, b_c3 = st.columns(3)
                    with b_c1:
                        st.markdown(f'<a href="{raw_ebay_url}" target="_blank" class="btn-ebay" style="display: block; text-align: center; font-size: 0.7rem; padding: 3px;">🔍 Raw</a>', unsafe_allow_html=True)
                    with b_c2:
                        st.markdown(f'<a href="{g10_ebay_url}" target="_blank" class="btn-ebay" style="display: block; text-align: center; font-size: 0.7rem; padding: 3px; background: linear-gradient(135deg, #f59e0b, #d97706);">💎 PSA 10</a>', unsafe_allow_html=True)
                    with b_c3:
                        st.markdown(f'<a href="{pc_url}" target="_blank" class="btn-pc" style="display: block; text-align: center; font-size: 0.7rem; padding: 3px;">📊 Comps</a>', unsafe_allow_html=True)

                    if var_owned:
                        if st.button("❌ Remove from Vault", key=f"mat_unmark_{var['id']}", type="secondary"):
                            unmark_card_as_owned(var["id"], var["card_name"], var["set_name"])
                            st.success(f"Removed {var['display_label']} from Vault!")
                            st.rerun()
                    else:
                        with st.popover("📥 Add to Vault"):
                            with st.form(f"mat_add_{var['id']}"):
                                q_cond = st.radio("Condition", ["Raw Single", "Graded Slab"], horizontal=True)
                                q_co = st.selectbox("Grader", ["RAW", "PSA", "CGC", "BGS", "ARS", "ACE"]) if q_cond == "Graded Slab" else "RAW"
                                q_tier = st.selectbox("Grade Label", ["Raw Single", "Gem Mint", "Pristine 10", "Black Label 10", "Mint 9", "Near Mint 8"])
                                q_price = st.number_input("Purchase Price ($)", min_value=0.0, value=float(var["est_raw_price"] or 10.0))
                                if st.form_submit_button("Confirm Add"):
                                    add_card_to_collection({
                                        "card_name": var["card_name"],
                                        "set_name": var["set_name"],
                                        "card_number": var["card_number"],
                                        "grading_company": q_co,
                                        "grade": 10.0 if q_cond == "Graded Slab" else 0.0,
                                        "grade_label": q_tier,
                                        "cert_number": "",
                                        "purchase_price": q_price,
                                        "purchase_date": datetime.today().strftime("%Y-%m-%d"),
                                        "edition": var["edition"],
                                        "language": var["language"],
                                        "is_error": var["is_error"],
                                        "error_type": var.get("error_description"),
                                        "is_raw": 1 if q_cond == "Raw Single" else 0,
                                        "pop_grade10": 0,
                                        "master_card_id": var["id"],
                                        "image_url": var["image_url"],
                                        "notes": "Added from Master Set Matrix.",
                                    })
                                    st.success("Added to Vault!")
                                    st.rerun()

elif "Card Grid" in master_view_mode:
    with m_top1:
        st.markdown(f"**Found {len(filtered_master)} Cards Matching Filters**")
    with m_top2:
        page_size_options = [24, 48, 96, "All"]
        per_page_choice = st.selectbox("Cards per page:", page_size_options, index=0, key="m_per_page")

    per_page = len(filtered_master) if per_page_choice == "All" or len(filtered_master) == 0 else int(per_page_choice)
    total_pages = max(1, (len(filtered_master) + per_page - 1) // per_page) if per_page > 0 else 1

    if total_pages > 1:
        pg_c1, pg_c2, pg_c3 = st.columns([1, 2, 1])
        with pg_c2:
            page_num = st.number_input(f"Page (1 to {total_pages})", min_value=1, max_value=total_pages, value=1, step=1, key="m_page_num")
    else:
        page_num = 1

    start_idx = (page_num - 1) * per_page
    end_idx = min(start_idx + per_page, len(filtered_master))
    page_df = filtered_master.iloc[start_idx:end_idx]

    if total_pages > 1:
        st.caption(f"Showing cards **{start_idx + 1}–{end_idx}** of **{len(filtered_master)}** (Page {page_num} of {total_pages})")

    m_cols = st.columns(4)
    for idx, (_, row) in enumerate(page_df.iterrows()):
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
            img_src = get_card_image_data_uri(row["image_url"] if row["image_url"] else DEFAULT_CARD_BACK_IMAGE)

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
            est_raw_display = f"${row['est_raw_price']:,.2f}" if row['est_raw_price'] > 0 else '<span style="color: #64748b; font-style: italic;">—</span>'
            est_g10_display = f"${row['est_grade10_price']:,.2f}" if row['est_grade10_price'] > 0 else '<span style="color: #64748b; font-style: italic;">—</span>'

            master_card_html = f"""<div class="slab-box" style="padding: 12px; margin-bottom: 14px;">
<div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px;">
<div style="font-size: 0.78rem; font-weight: 700; color: #94a3b8;">{row['release_year']} • {row['language']}</div>
<div style="display: flex; gap: 3px; align-items: center; flex-wrap: wrap;">{ed_badge} {err_badge} {status_badge}</div>
</div>
<div style="text-align: center; margin: 8px 0;">
<img src="{img_src}" loading="lazy" decoding="async" style="max-height: 155px; max-width: 100%; border-radius: 6px; box-shadow: 0 4px 10px rgba(0,0,0,0.5);" />
</div>
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px;">
<div style="font-weight: 800; font-size: 0.92rem; color: #ffffff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{row['card_name']}</div>
{pop_badge}
</div>
<div style="color: #8c8d9a; font-size: 0.78rem; margin-bottom: 8px;">{row['set_name']} • {card_num_display}</div>
<div style="background: #111217; padding: 6px 8px; border-radius: 6px; font-size: 0.78rem; margin-bottom: 8px;">
<div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
<span style="color: #8c8d9a;">Est Raw:</span>
<span style="color: #ffd591; font-weight: 700;">{est_raw_display}</span>
</div>
<div style="display: flex; justify-content: space-between;">
<span style="color: #8c8d9a;">Est PSA 10:</span>
<span style="color: #f59e0b; font-weight: 700;">{est_g10_display}</span>
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
                pop_label = "✅ Owned" if row["is_owned"] else "📥 Add"
                with st.popover(pop_label):
                    if row["is_owned"]:
                        st.markdown(f"**Status:** Marked as Owned in Vault (`{row['owned_copies']} copy`).")
                        st.caption(f"Details: {row['owned_details']}")
                        if st.button("❌ Remove from Vault", key=f"unmark_{row['id']}", type="primary"):
                            unmark_card_as_owned(row["id"], row["card_name"], row["set_name"])
                            st.success("Unmarked card from Vault!")
                            st.rerun()
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
                        ed_idx_m = EDITION_OPTIONS.index(row["edition"]) if row["edition"] in EDITION_OPTIONS else 0
                        em_ed = st.selectbox("Edition / Rarity", EDITION_OPTIONS, index=ed_idx_m)
                        lang_idx_m = LANGUAGE_OPTIONS.index(row["language"]) if row["language"] in LANGUAGE_OPTIONS else 0
                        em_lang = st.selectbox("Language", LANGUAGE_OPTIONS, index=lang_idx_m)
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
else:
    st.dataframe(
        filtered_master[[
            "release_year", "card_name", "set_name", "card_number", "rarity",
            "edition", "language", "is_owned", "owned_copies", "est_raw_price", "est_grade10_price"
        ]].rename(columns={
            "release_year": "Year",
            "card_name": "Card Name",
            "set_name": "Set",
            "card_number": "#",
            "rarity": "Rarity",
            "edition": "Edition",
            "language": "Language",
            "is_owned": "Owned?",
            "owned_copies": "Copies",
            "est_raw_price": "Est Raw ($)",
            "est_grade10_price": "Est PSA 10 ($)",
        }),
        use_container_width=True,
        hide_index=True,
    )

st.markdown("---")
with st.expander("☁️ Sync Master Checklist from Google Sheets", expanded=False):
    sheet_url_input = st.text_input(
        "Google Sheets Shareable URL",
        value="https://docs.google.com/spreadsheets/d/12RkRdPNwbFly1SXmCS7DQkB5Q5zQZcPAnLX-P8M_vNA/edit?usp=sharing",
    )
    if st.button("🔄 Sync Master Set from Google Sheets", key="btn_sync_sheets"):
        with st.spinner("Syncing catalog with Google Sheets..."):
            count, msg, _ = sync_from_google_sheets_url(sheet_url_input)
            st.success(msg)
            st.rerun()
