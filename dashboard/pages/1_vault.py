"""
The Vulpix Vault - Page 1: My Vault & Portfolio
Personal collection tracking, multi-tier importing (Manual, eBay Link, Screenshot OCR, Text Paste, CSV),
valuation calculation, and cert lookups.
"""

import io
import os
from datetime import datetime
import pandas as pd
import streamlit as st

from db_utils import (
    EDITION_OPTIONS,
    LANGUAGE_OPTIONS,
    add_card_to_collection,
    auto_enrich_master_catalog,
    bulk_import_collection_from_df,
    bulk_import_ebay_history,
    delete_card_from_collection,
    extract_text_from_screenshot,
    get_card_image_data_uri,
    get_csv_template_bytes,
    get_master_set_metrics,
    get_portfolio_metrics,
    get_psa_cert_lookup_url,
    load_collection_df,
    parse_ebay_link_to_card,
    parse_ebay_purchase_history_text,
    update_collection_card,
)
from metadata_resolver import DEFAULT_CARD_BACK_IMAGE
from styles import (
    apply_custom_styles,
    get_edition_badge_html,
    get_grading_badge_html,
    get_pop_badge_html,
    render_header,
)

apply_custom_styles()
render_header()

# Fast In-Memory Cached Loaders
@st.cache_data(ttl=60)
def get_cached_collection_df():
    return load_collection_df()

@st.cache_data(ttl=60)
def get_cached_portfolio_metrics():
    return get_portfolio_metrics()

@st.cache_data(ttl=60)
def get_cached_master_set_metrics():
    return get_master_set_metrics()

def clear_dashboard_cache():
    st.cache_data.clear()

port_metrics = get_cached_portfolio_metrics()
master_metrics = get_cached_master_set_metrics()
df_col = get_cached_collection_df()

st.markdown("### 💼 Personal Vault Overview")

# KPI Metric Cards
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">Total Portfolio Value</div>
        <div class="kpi-value">${port_metrics['total_value']:,.2f}</div>
        <div class="kpi-delta-pos">Market Value</div>
    </div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">Total Invested Cost</div>
        <div class="kpi-value">${port_metrics['total_cost']:,.2f}</div>
        <div style="color: #94a3b8; font-size: 0.85rem;">Purchase Basis</div>
    </div>""", unsafe_allow_html=True)
with c3:
    gain_cls = "kpi-delta-pos" if port_metrics["net_gain"] >= 0 else "kpi-delta-neg"
    sign = "+" if port_metrics["net_gain"] >= 0 else ""
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">Unrealized Gain / ROI</div>
        <div class="kpi-value">{sign}${port_metrics['net_gain']:,.2f}</div>
        <div class="{gain_cls}">{sign}{port_metrics['roi_percent']}% ROI</div>
    </div>""", unsafe_allow_html=True)
with c4:
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">Vault Slabs & Singles</div>
        <div class="kpi-value">{port_metrics['total_slabs'] + port_metrics['total_raw']} Items</div>
        <div style="color: #60a5fa; font-size: 0.85rem;">{port_metrics['total_slabs']} Graded • {port_metrics['total_raw']} Raw</div>
    </div>""", unsafe_allow_html=True)
with c5:
    st.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">Master Set Progress</div>
        <div class="kpi-value">{master_metrics['completion_pct']}%</div>
        <div style="color: #10b981; font-size: 0.85rem;">{master_metrics['owned_cards']} / {master_metrics['total_cards']} Unique</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# -------------------------------------------------------------
# Card Importers (5 Multi-Format Options)
# -------------------------------------------------------------
imp_t1, imp_t2, imp_t3, imp_t4, imp_t5 = st.tabs([
    "➕ Manual Add",
    "🔗 eBay Link",
    "📸 Screenshot OCR",
    "📦 eBay Order Text",
    "📥 CSV Import",
])

# Tab 1: Manual Add Form
with imp_t1:
    with st.form("manual_add_card_form", clear_on_submit=True):
        f_c1, f_c2 = st.columns(2)
        with f_c1:
            card_name = st.text_input("Card Name*", value="Vulpix")
            set_name = st.text_input("Set / Expansion*", value="Base Set")
            card_num = st.text_input("Card Number", value="68/102")
            condition_type = st.radio("Condition Category*", ["Graded Slab", "Raw Single"], horizontal=True)
            grader = st.selectbox("Grading Company", ["RAW", "PSA", "CGC", "BGS", "ARS", "ACE"]) if condition_type == "Graded Slab" else "RAW"
            grade_num = st.number_input("Numerical Grade", min_value=0.0, max_value=10.0, value=10.0 if condition_type == "Graded Slab" else 0.0, step=0.5)
        with f_c2:
            grade_label = st.selectbox("Grade Label Tier", ["Raw Single", "Gem Mint", "Pristine 10", "Black Label 10", "Mint 9", "Near Mint 8", "Ungraded"])
            cert_num = st.text_input("Certification Number (Slab Cert #)", placeholder="e.g. 84729103")
            buy_price = st.number_input("Purchase Price ($)*", min_value=0.0, value=25.0, step=5.0)
            buy_date = st.date_input("Purchase Date", value=datetime.today())
            edition = st.selectbox("Edition / Rarity", EDITION_OPTIONS)
            language = st.selectbox("Language", LANGUAGE_OPTIONS)

        is_err = st.checkbox("Is Error / Misprint Card?")
        err_desc = st.text_input("Error Description", placeholder="e.g. Blue Ink Drop Error, HP 50 Error") if is_err else ""
        custom_img_url = st.text_input("Custom Image URL (Optional)", placeholder="e.g. eBay image link or uploaded scan")
        notes = st.text_area("Personal Notes / Provenance", placeholder="e.g. Won on eBay auction, subgrade details...")
        submit_add = st.form_submit_button("💾 Save Card to Vault")

        if submit_add:
            if not card_name or not set_name:
                st.error("Card Name and Set Name are required.")
            else:
                new_id = add_card_to_collection({
                    "card_name": card_name,
                    "set_name": set_name,
                    "card_number": card_num,
                    "grading_company": grader,
                    "grade": grade_num,
                    "grade_label": grade_label,
                    "cert_number": cert_num,
                    "purchase_price": buy_price,
                    "purchase_date": str(buy_date),
                    "edition": edition,
                    "language": language,
                    "is_error": 1 if is_err else 0,
                    "error_type": err_desc if is_err else None,
                    "is_raw": 1 if condition_type == "Raw Single" else 0,
                    "image_url": custom_img_url if custom_img_url else None,
                    "notes": notes,
                })
                clear_dashboard_cache()
                st.success(f"Added {card_name} to your Vault!")
                st.rerun()

# Tab 2: 1-Click eBay Link Import
with imp_t2:
    st.markdown("Paste an eBay listing link or Item ID to auto-extract details and authentic artwork:")
    ebay_url_input = st.text_input(
        "eBay Listing Link or Item ID",
        placeholder="e.g. https://www.ebay.com/itm/2019-POKEMON-SUN-MOON-ALOLAN-VULPIX-PSA-10/161422818572",
        key="link_import_input"
    )
    if ebay_url_input:
        parsed_link_card = parse_ebay_link_to_card(ebay_url_input)
        st.markdown(f"**Detected Card:** `{parsed_link_card['card_name']}` • **Set:** `{parsed_link_card['set_name']}` • **Grade:** `{parsed_link_card['grading_company']} {parsed_link_card['grade_label']}`")
        
        lp_col1, lp_col2 = st.columns([1, 2])
        with lp_col1:
            prev_img = get_card_image_data_uri(parsed_link_card["image_url"])
            st.markdown(f'<img src="{prev_img}" style="max-height: 180px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.4);" />', unsafe_allow_html=True)
        with lp_col2:
            with st.form("confirm_ebay_link_form"):
                el_name = st.text_input("Card Name", value=parsed_link_card["card_name"])
                el_set = st.text_input("Set Name", value=parsed_link_card["set_name"])
                el_num = st.text_input("Card #", value=parsed_link_card["card_number"])
                el_price = st.number_input("Purchase Price ($)*", min_value=0.0, value=45.0, step=5.0)
                el_grader = st.selectbox("Grader", ["RAW", "PSA", "CGC", "BGS", "ARS", "ACE"], index=1 if parsed_link_card["grading_company"] == "PSA" else 0)
                el_tier = st.selectbox("Grade Tier", ["Gem Mint", "Pristine 10", "Raw Single", "Mint 9", "Near Mint 8"])
                el_ed = st.selectbox("Edition", EDITION_OPTIONS, index=EDITION_OPTIONS.index(parsed_link_card["edition"]) if parsed_link_card["edition"] in EDITION_OPTIONS else 0)
                el_lang = st.selectbox("Language", LANGUAGE_OPTIONS, index=LANGUAGE_OPTIONS.index(parsed_link_card["language"]) if parsed_link_card["language"] in LANGUAGE_OPTIONS else 0)
                
                if st.form_submit_button("🚀 Confirm & Add to Vault"):
                    add_card_to_collection({
                        "card_name": el_name,
                        "set_name": el_set,
                        "card_number": el_num,
                        "grading_company": el_grader,
                        "grade": 10.0 if el_grader != "RAW" else 0.0,
                        "grade_label": el_tier,
                        "cert_number": "",
                        "purchase_price": el_price,
                        "purchase_date": datetime.today().strftime("%Y-%m-%d"),
                        "edition": el_ed,
                        "language": el_lang,
                        "is_error": 0,
                        "is_raw": 1 if el_grader == "RAW" else 0,
                        "image_url": parsed_link_card["image_url"],
                        "notes": parsed_link_card["notes"],
                    })
                    clear_dashboard_cache()
                    st.success(f"Added {el_name} from eBay Link to your Vault!")
                    st.rerun()

# Tab 3: Screenshot OCR Import
with imp_t3:
    st.markdown("Upload or drop a screenshot of your eBay purchase history or order details:")
    uploaded_screenshot = st.file_uploader("Upload Screenshot", type=["png", "jpg", "jpeg", "webp"], key="screenshot_uploader")
    if uploaded_screenshot is not None:
        with st.spinner("Extracting card and order text using OCR..."):
            extracted_ocr_text = extract_text_from_screenshot(uploaded_screenshot)
        if extracted_ocr_text:
            parsed_ocr_items = parse_ebay_purchase_history_text(extracted_ocr_text)
            if parsed_ocr_items:
                st.success(f"Extracted {len(parsed_ocr_items)} card(s) from screenshot!")
                df_ocr_preview = pd.DataFrame(parsed_ocr_items)[["card_name", "set_name", "card_number", "grading_company", "grade_label", "purchase_price", "purchase_date", "language"]]
                st.dataframe(df_ocr_preview, use_container_width=True)
                if st.button("🚀 Confirm Import All from Screenshot into Vault", key="btn_confirm_ocr_import"):
                    cnt_ocr, msg_ocr = bulk_import_ebay_history(parsed_ocr_items)
                    clear_dashboard_cache()
                    st.success(msg_ocr)
                    st.rerun()
            else:
                st.info("Extracted text from image, but no standard Pokémon card order patterns were matched. You can inspect or copy the raw text below:")
                st.code(extracted_ocr_text)
        else:
            st.warning("Could not extract readable text from image. Make sure the screenshot is legible, or configure an optional Gemini API key in Settings.")

# Tab 4: eBay Purchase History Raw Text
with imp_t4:
    st.markdown("Paste raw text copied directly from your eBay order history or confirmation email:")
    ebay_paste_text = st.text_area(
        "Paste eBay Order History Text",
        placeholder="e.g.\nDelivered on Thu, Feb 19\n2019 POKEMON SUN & MOON ALOLAN VULPIX - HOLO GEM MT HIDDEN FATES PSA 10\nUS $45.05\nOrder number: 16-14228-18572",
        height=120,
        key="vault_ebay_paste_input",
    )
    if ebay_paste_text:
        parsed_ebay_items = parse_ebay_purchase_history_text(ebay_paste_text)
        if parsed_ebay_items:
            st.markdown(f"**Found {len(parsed_ebay_items)} Card(s) in Text:**")
            df_preview_ebay = pd.DataFrame(parsed_ebay_items)[["card_name", "set_name", "card_number", "grading_company", "grade_label", "purchase_price", "purchase_date", "language"]]
            st.dataframe(df_preview_ebay, use_container_width=True)
            if st.button("🚀 Confirm Add All eBay Cards to Vault", key="btn_confirm_ebay_text_import"):
                cnt_eb, msg_eb = bulk_import_ebay_history(parsed_ebay_items)
                clear_dashboard_cache()
                st.success(msg_eb)
                st.rerun()
        else:
            st.warning("Could not find card order patterns in the pasted text. Make sure the title and price lines are included.")

# Tab 5: CSV Import
with imp_t5:
    st.markdown("Import cards from a CSV file directly into your Vault:")
    st.download_button(
        "📥 Download Starter CSV Template",
        data=get_csv_template_bytes(),
        file_name="vulpix_collection_starter_template.csv",
        mime="text/csv",
    )
    col_csv_file = st.file_uploader("Upload Collection CSV", type=["csv"], key="vault_csv_uploader")
    if col_csv_file is not None:
        try:
            df_up_col = pd.read_csv(col_csv_file)
            st.dataframe(df_up_col.head(3), use_container_width=True)
            if st.button("🚀 Confirm Bulk Import into Vault"):
                count_imp, msg_imp = bulk_import_collection_from_df(df_up_col)
                clear_dashboard_cache()
                st.success(msg_imp)
                st.rerun()
        except Exception as e:
            st.error(f"Error reading CSV: {e}")

st.markdown("---")

# -------------------------------------------------------------
# Collection Cards Display
# -------------------------------------------------------------
if df_col.empty:
    st.info("💡 Your Vault is currently empty. Use any of the import tools above to add cards!")
else:
    v_col1, v_col2, v_col3 = st.columns([2, 1.2, 1.2])
    with v_col1:
        st.markdown(f"#### 🏆 Your Collection ({len(df_col)} Items)")
    with v_col2:
        if st.button("✨ Auto-Enrich Vault", key="btn_enrich_vault", use_container_width=True):
            count_enr, msg_enr = auto_enrich_master_catalog(force_all=True)
            clear_dashboard_cache()
            st.success(msg_enr)
            st.rerun()
    with v_col3:
        view_mode = st.radio("Display Layout:", ["🃏 Card Grid View", "📋 Table / List View"], horizontal=True, key="vault_v_mode")

    if "Card Grid" in view_mode:
        grid_cols = st.columns(3)
        for idx, row in df_col.iterrows():
            target_col = grid_cols[idx % 3]
            with target_col:
                grade_badge = get_grading_badge_html(
                    company=row["grading_company"],
                    grade=row["grade"],
                    grade_label=row.get("grade_label", "Gem Mint"),
                    is_raw=row.get("is_raw", 0),
                )
                ed_badge = get_edition_badge_html(row.get("edition", "Unlimited"))
                err_badge = '<span class="badge-error">⚠️ ERROR</span>' if row["is_error"] == 1 else ""
                pop_badge = get_pop_badge_html(int(row.get("pop_grade10") or 0), int(row.get("pop_pristine10") or 0))

                img_src = get_card_image_data_uri(row["image_url"] if row["image_url"] else DEFAULT_CARD_BACK_IMAGE)
                psa_link = get_psa_cert_lookup_url(row["cert_number"]) if row["cert_number"] else None
                cert_display = f'<a href="{psa_link}" target="_blank" style="color: #60a5fa; text-decoration: none; font-weight: 700;">#{row["cert_number"]} ↗</a>' if psa_link else (f'#{row["cert_number"]}' if row["cert_number"] else 'Raw Single')

                # Format Bought & Market cleanly with unrecorded / unappraised fallback
                if row["purchase_price"] > 0:
                    bought_display = f"${row['purchase_price']:,.2f} ({row['purchase_date']})"
                else:
                    bought_display = '<span style="color: #64748b; font-style: italic;">— (Unrecorded)</span>'

                if row["current_market_value"] > 0:
                    market_display = f"${row['current_market_value']:,.2f}"
                    gain_sign = "+" if row["unrealized_gain"] >= 0 else ""
                    gain_color = "#4ade80" if row["unrealized_gain"] >= 0 else "#f87171"
                    roi_display = f'<span style="color: {gain_color}; font-weight: 700;">{gain_sign}${row["unrealized_gain"]:,.2f} ({gain_sign}{row["roi_percent"]}%)</span>'
                else:
                    market_display = '<span style="color: #64748b; font-style: italic;">— (Unappraised)</span>'
                    roi_display = '<span style="color: #64748b;">—</span>'

                card_num_str = f"#{row['card_number']}" if row['card_number'] and str(row['card_number']).lower() != "nan" else "(Promo / No #)"

                card_box_html = f"""<div class="slab-box">
<div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
<div style="display: flex; gap: 4px; align-items: center; flex-wrap: wrap;">{grade_badge} {ed_badge} {err_badge}</div>
<div>{pop_badge}</div>
</div>
<div style="text-align: center; margin: 10px 0;">
<img src="{img_src}" loading="lazy" decoding="async" style="max-height: 175px; max-width: 100%; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.5);" />
</div>
<div style="font-weight: 800; font-size: 1.05rem; color: #ffffff;">{row['card_name']}</div>
<div style="color: #8c8d9a; font-size: 0.82rem; margin-bottom: 8px;">{row['set_name']} • {card_num_str}</div>
<div style="background: #111217; padding: 8px 10px; border-radius: 8px; font-size: 0.82rem; margin-bottom: 8px;">
<div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
<span style="color: #8c8d9a;">Bought:</span>
<span style="color: #fff; font-weight: 600;">{bought_display}</span>
</div>
<div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
<span style="color: #8c8d9a;">Est. Market:</span>
<span style="color: #ffd591; font-weight: 700;">{market_display}</span>
</div>
<div style="display: flex; justify-content: space-between;">
<span style="color: #8c8d9a;">Gain / ROI:</span>
{roi_display}
</div>
</div>
<div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.78rem; color: #8c8d9a;">
<span>Cert: {cert_display}</span>
<span>{row['language']}</span>
</div>
</div>"""
                st.markdown(card_box_html, unsafe_allow_html=True)

                # Action buttons
                b1, b2, b3 = st.columns(3)
                with b1:
                    with st.popover("✏️ Edit"):
                        with st.form(f"edit_form_{row['id']}"):
                            e_name = st.text_input("Card Name", value=row["card_name"])
                            e_set = st.text_input("Set Name", value=row["set_name"])
                            e_num = st.text_input("Card #", value=row["card_number"])
                            e_grader = st.selectbox("Grader", ["RAW", "PSA", "CGC", "BGS", "ARS", "ACE"], index=0 if row["is_raw"] else 1)
                            e_grade = st.number_input("Grade", min_value=0.0, max_value=10.0, value=float(row["grade"]), step=0.5)
                            e_label = st.selectbox("Grade Label", ["Raw Single", "Gem Mint", "Pristine 10", "Black Label 10", "Mint 9", "Near Mint 8"])
                            e_cert = st.text_input("Cert #", value=row["cert_number"] or "")
                            e_cost = st.number_input("Purchase Price ($)", min_value=0.0, value=float(row["purchase_price"]), step=5.0)
                            e_date = st.text_input("Purchase Date", value=str(row["purchase_date"]))
                            ed_idx = EDITION_OPTIONS.index(row["edition"]) if row["edition"] in EDITION_OPTIONS else 0
                            e_ed = st.selectbox("Edition / Rarity", EDITION_OPTIONS, index=ed_idx)
                            lang_idx = LANGUAGE_OPTIONS.index(row["language"]) if row["language"] in LANGUAGE_OPTIONS else 0
                            e_lang = st.selectbox("Language", LANGUAGE_OPTIONS, index=lang_idx)
                            e_err = st.checkbox("Error Card?", value=bool(row["is_error"]))
                            e_err_type = st.text_input("Error Type", value=row["error_type"] or "") if e_err else ""
                            e_img = st.text_input("Image URL (Custom/Scan)", value=row["image_url"] or "")
                            e_notes = st.text_area("Notes", value=row["notes"] or "")

                            if st.form_submit_button("Save Changes"):
                                update_collection_card(row["id"], {
                                    "card_name": e_name,
                                    "set_name": e_set,
                                    "card_number": e_num,
                                    "grading_company": e_grader,
                                    "grade": e_grade,
                                    "grade_label": e_label,
                                    "cert_number": e_cert,
                                    "purchase_price": e_cost,
                                    "purchase_date": e_date,
                                    "edition": e_ed,
                                    "language": e_lang,
                                    "is_error": 1 if e_err else 0,
                                    "error_type": e_err_type if e_err else None,
                                    "is_raw": 1 if e_grader == "RAW" else 0,
                                    "image_url": e_img,
                                    "notes": e_notes,
                                })
                                clear_dashboard_cache()
                                st.success("Card updated!")
                                st.rerun()

                with b2:
                    with st.popover("🗑️ Remove"):
                        st.write(f"Remove **{row['card_name']}** ({row['set_name']}) from your Vault?")
                        if st.button("Confirm Delete", key=f"del_{row['id']}", type="primary"):
                            delete_card_from_collection(row["id"])
                            clear_dashboard_cache()
                            st.success("Removed from Vault!")
                            st.rerun()

                with b3:
                    with st.popover("ℹ️ Info"):
                        st.markdown(f"#### 🔍 {row['card_name']}")
                        st.markdown(f"**Set:** {row['set_name']} • **Number:** `{card_num_str}`")
                        st.markdown(f"**Edition:** {row['edition']} • **Language:** {row['language']}")
                        if row["is_error"] == 1 and row.get("error_type"):
                            st.error(f"**⚠️ Known Card Errors & Misprints:**\n\n{row['error_type']}")
                        st.markdown(f"- **Purchase Price:** `${row['purchase_price']:,.2f}` on {row['purchase_date']}")
                        st.markdown(f"- **Est. Market Value:** `${row['current_market_value']:,.2f}` ({gain_sign}${row['unrealized_gain']:,.2f})")
                        if row.get("cert_number"):
                            st.markdown(f"- **Cert #:** `{row['cert_number']}` ({row['grading_company']} {row['grade_label']})")
                        if row.get("notes"):
                            st.markdown(f"- **Notes:** {row['notes']}")
    else:
        st.dataframe(
            df_col[[
                "card_name", "set_name", "card_number", "grading_company",
                "grade_label", "cert_number", "edition", "language",
                "purchase_price", "current_market_value", "unrealized_gain", "roi_percent", "notes"
            ]].rename(columns={
                "card_name": "Card Name",
                "set_name": "Set",
                "card_number": "#",
                "grading_company": "Grader",
                "grade_label": "Grade / Slab",
                "cert_number": "Cert #",
                "edition": "Edition",
                "language": "Language",
                "purchase_price": "Bought ($)",
                "current_market_value": "Market ($)",
                "unrealized_gain": "Gain ($)",
                "roi_percent": "ROI (%)",
                "notes": "Notes",
            }),
            use_container_width=True,
            hide_index=True,
        )
