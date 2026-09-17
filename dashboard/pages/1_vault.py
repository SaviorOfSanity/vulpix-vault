"""
The Vulpix Vault - Page 1: My Vault & Portfolio
High-performance personal collection tracking, lazy image loading,
instant add/edit/delete operations, and fast multi-format importing.
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
    generate_ebay_search_url,
    get_card_image_data_uri,
    get_csv_template_bytes,
    get_master_set_metrics,
    get_portfolio_metrics,
    get_pricecharting_search_url,
    get_psa_cert_lookup_url,
    get_system_setting,
    load_collection_df,
    load_master_catalog_df,
    parse_ebay_link_to_card,
    parse_ebay_purchase_history_text,
    sync_ebay_user_account,
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

if "vault_flash_msg" in st.session_state:
    st.success(st.session_state.pop("vault_flash_msg"))
    st.balloons()

# Fast Data Loaders (Direct SQLite query executes in < 20ms)
df_col = load_collection_df()
port_metrics = get_portfolio_metrics()
master_metrics = get_master_set_metrics()

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
    df_m_lookup = load_master_catalog_df()
    master_card_labels = ["-- Type Manually / Custom Card --"]
    master_lookup_dict = {}
    if not df_m_lookup.empty:
        for _, m_r in df_m_lookup.iterrows():
            lbl = f"{m_r['card_name']} ({m_r['set_name']} #{m_r['card_number']}) - {m_r['language']} [{m_r['edition']}]"
            master_card_labels.append(lbl)
            master_lookup_dict[lbl] = m_r

    selected_master_lbl = st.selectbox(
        "⚡ Quick Autocomplete from Master Catalog (or choose manual entry):",
        master_card_labels,
        key="manual_add_master_autocomplete",
    )
    selected_m_data = master_lookup_dict.get(selected_master_lbl)

    init_name = str(selected_m_data["card_name"]) if selected_m_data is not None else "Vulpix"
    init_set = str(selected_m_data["set_name"]) if selected_m_data is not None else "Base Set"
    init_num = str(selected_m_data["card_number"]) if selected_m_data is not None else "68/102"
    init_ed = str(selected_m_data["edition"]) if (selected_m_data is not None and selected_m_data["edition"] in EDITION_OPTIONS) else EDITION_OPTIONS[0]
    init_lang = str(selected_m_data["language"]) if (selected_m_data is not None and selected_m_data["language"] in LANGUAGE_OPTIONS) else LANGUAGE_OPTIONS[0]
    init_img = str(selected_m_data["image_url"]) if selected_m_data is not None else ""
    init_price = float(selected_m_data["est_raw_price"] or 15.0) if selected_m_data is not None else 25.0
    init_master_id = int(selected_m_data["id"]) if selected_m_data is not None else None

    with st.form("manual_add_card_form", clear_on_submit=True):
        f_c1, f_c2 = st.columns(2)
        with f_c1:
            card_name = st.text_input("Card Name*", value=init_name)
            set_name = st.text_input("Set / Expansion*", value=init_set)
            card_num = st.text_input("Card Number", value=init_num)
            condition_type = st.radio("Condition Category*", ["Graded Slab", "Raw Single"], horizontal=True)
            grader = st.selectbox("Grading Company", ["RAW", "PSA", "CGC", "BGS", "ARS", "ACE"]) if condition_type == "Graded Slab" else "RAW"
            grade_num = st.number_input("Numerical Grade", min_value=0.0, max_value=10.0, value=10.0 if condition_type == "Graded Slab" else 0.0, step=0.5)
        with f_c2:
            grade_label = st.selectbox("Grade Label Tier", ["Raw Single", "Gem Mint", "Pristine 10", "Black Label 10", "Mint 9", "Near Mint 8", "Ungraded"])
            cert_num = st.text_input("Certification Number (Slab Cert #)", placeholder="e.g. 84729103")
            buy_price = st.number_input("Purchase Price ($)*", min_value=0.0, value=init_price, step=5.0)
            buy_date = st.date_input("Purchase Date", value=datetime.today())
            edition = st.selectbox("Edition / Rarity", EDITION_OPTIONS, index=EDITION_OPTIONS.index(init_ed) if init_ed in EDITION_OPTIONS else 0)
            language = st.selectbox("Language", LANGUAGE_OPTIONS, index=LANGUAGE_OPTIONS.index(init_lang) if init_lang in LANGUAGE_OPTIONS else 0)

        is_err = st.checkbox("Is Error / Misprint Card?")
        err_desc = st.text_input("Error Description", placeholder="e.g. Blue Ink Drop Error, HP 50 Error") if is_err else ""
        custom_img_url = st.text_input("Custom Image (Local Path or Web URL)", value=init_img)
        notes = st.text_area("Personal Notes / Provenance", placeholder="e.g. Won on eBay auction, pulled from pack...")
        submit_add = st.form_submit_button("💾 Save Card to Vault")

        if submit_add:
            if not card_name or not set_name:
                st.error("Card Name and Set Name are required.")
            else:
                add_card_to_collection({
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
                    "master_card_id": init_master_id,
                    "notes": notes,
                })
                st.success(f"Added {card_name} to your Vault!")
                st.rerun()

# Tab 2: 1-Click eBay Link Import & Account Sync
with imp_t2:
    with st.expander("⚡ 1-Click Auto-Sync Won Purchases from eBay API", expanded=False):
        st.markdown("Connect to your eBay account to automatically import all recently won auctions into your Vault:")
        if st.button("🚀 Sync Won Auctions Now", key="btn_sync_ebay_won_vault", type="primary"):
            user_tok = get_system_setting("EBAY_USER_TOKEN") or os.getenv("EBAY_USER_TOKEN", "")
            if not user_tok:
                st.warning("⚠️ eBay User Auth Token is not configured yet. Please enter your User Token in Settings to enable 1-click account sync.")
            else:
                with st.spinner("Connecting to eBay Trading API to pull your won list..."):
                    ok_s, msg_s, d_s = sync_ebay_user_account(user_token=user_tok)
                    if ok_s:
                        if d_s.get("won_added", 0) > 0:
                            st.session_state["vault_flash_msg"] = msg_s
                            st.rerun()
                        else:
                            st.info(f"ℹ️ {msg_s}")
                    else:
                        st.error(f"❌ {msg_s}")

    st.markdown("Or paste an individual eBay listing link or Item ID to auto-extract details:")
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
                    st.success(f"Added {el_name} from eBay Link to your Vault!")
                    st.rerun()

# Tab 3: Screenshot OCR Import (On-Demand & Cached to prevent CPU hangs)
with imp_t3:
    st.markdown("Upload or drop a screenshot of your eBay purchase history or order details:")
    uploaded_screenshot = st.file_uploader("Upload Screenshot", type=["png", "jpg", "jpeg", "webp"], key="screenshot_uploader")
    if uploaded_screenshot is not None:
        ocr_c1, ocr_c2 = st.columns([1, 2])
        with ocr_c1:
            st.image(uploaded_screenshot, caption="Screenshot Preview", width=220)
        with ocr_c2:
            st.info("Click the button below to extract text using local OCR.")
            if st.button("🔍 Extract Text & Cards with OCR", key="btn_run_ocr", type="primary"):
                with st.spinner("Extracting text via optimized OCR..."):
                    st.session_state["vault_ocr_text"] = extract_text_from_screenshot(uploaded_screenshot)

    if st.session_state.get("vault_ocr_text"):
        parsed_ocr_items = parse_ebay_purchase_history_text(st.session_state["vault_ocr_text"])
        if parsed_ocr_items:
            st.success(f"Extracted {len(parsed_ocr_items)} card(s) from screenshot!")
            df_ocr_preview = pd.DataFrame(parsed_ocr_items)[["card_name", "set_name", "card_number", "grading_company", "grade_label", "purchase_price", "purchase_date", "language"]]
            st.dataframe(df_ocr_preview, use_container_width=True)
            if st.button("🚀 Confirm Import All from Screenshot into Vault", key="btn_confirm_ocr_import"):
                cnt_ocr, msg_ocr = bulk_import_ebay_history(parsed_ocr_items)
                del st.session_state["vault_ocr_text"]
                st.success(msg_ocr)
                st.rerun()
        else:
            st.warning("Extracted text, but no Pokémon card order rows were matched. Raw text:")
            st.code(st.session_state["vault_ocr_text"])

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
                st.success(msg_imp)
                st.rerun()
        except Exception as e:
            st.error(f"Error reading CSV: {e}")

st.markdown("---")

# -------------------------------------------------------------
# Active Inline Edit Drawer (renders only when user clicks Edit)
# -------------------------------------------------------------
editing_id = st.session_state.get("editing_card_id")
if editing_id:
    edit_row_matches = df_col[df_col["id"] == editing_id]
    if not edit_row_matches.empty:
        erow = edit_row_matches.iloc[0]
        with st.expander(f"✏️ Editing: {erow['card_name']} ({erow['set_name']})", expanded=True):
            with st.form("active_edit_card_form"):
                ed_c1, ed_c2 = st.columns(2)
                with ed_c1:
                    e_name = st.text_input("Card Name", value=erow["card_name"])
                    e_set = st.text_input("Set Name", value=erow["set_name"])
                    e_num = st.text_input("Card #", value=erow["card_number"])
                    e_grader = st.selectbox("Grader", ["RAW", "PSA", "CGC", "BGS", "ARS", "ACE"], index=0 if erow["is_raw"] else 1)
                    e_grade = st.number_input("Grade", min_value=0.0, max_value=10.0, value=float(erow["grade"]), step=0.5)
                    e_label = st.selectbox("Grade Label", ["Raw Single", "Gem Mint", "Pristine 10", "Black Label 10", "Mint 9", "Near Mint 8"])
                with ed_c2:
                    e_cert = st.text_input("Cert #", value=erow["cert_number"] or "")
                    e_cost = st.number_input("Purchase Price ($)", min_value=0.0, value=float(erow["purchase_price"]), step=5.0)
                    e_date = st.text_input("Purchase Date", value=str(erow["purchase_date"]))
                    ed_idx = EDITION_OPTIONS.index(erow["edition"]) if erow["edition"] in EDITION_OPTIONS else 0
                    e_ed = st.selectbox("Edition / Rarity", EDITION_OPTIONS, index=ed_idx)
                    lang_idx = LANGUAGE_OPTIONS.index(erow["language"]) if erow["language"] in LANGUAGE_OPTIONS else 0
                    e_lang = st.selectbox("Language", LANGUAGE_OPTIONS, index=lang_idx)

                e_img = st.text_input("Image URL (Custom/Scan)", value=erow["image_url"] or "")
                e_notes = st.text_area("Notes", value=erow["notes"] or "")

                btn_c1, btn_c2 = st.columns(2)
                with btn_c1:
                    if st.form_submit_button("💾 Save Changes", type="primary"):
                        update_collection_card(editing_id, {
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
                            "is_error": erow["is_error"],
                            "error_type": erow["error_type"],
                            "is_raw": 1 if e_grader == "RAW" else 0,
                            "image_url": e_img,
                            "notes": e_notes,
                        })
                        del st.session_state["editing_card_id"]
                        st.success("Card updated!")
                        st.rerun()
                with btn_c2:
                    if st.form_submit_button("Cancel"):
                        del st.session_state["editing_card_id"]
                        st.rerun()

# -------------------------------------------------------------
# Active Delete Confirmation Banner
# -------------------------------------------------------------
deleting_id = st.session_state.get("deleting_card_id")
if deleting_id:
    del_matches = df_col[df_col["id"] == deleting_id]
    if not del_matches.empty:
        drow = del_matches.iloc[0]
        st.warning(f"⚠️ Are you sure you want to remove **{drow['card_name']}** ({drow['set_name']} #{drow['card_number']}) from your Vault?")
        del_c1, del_c2, _ = st.columns([1, 1, 3])
        with del_c1:
            if st.button("🗑️ Yes, Delete Card", type="primary", key="confirm_delete_btn"):
                delete_card_from_collection(deleting_id)
                del st.session_state["deleting_card_id"]
                st.success("Removed card from Vault!")
                st.rerun()
        with del_c2:
            if st.button("Cancel", key="cancel_delete_btn"):
                del st.session_state["deleting_card_id"]
                st.rerun()

# -------------------------------------------------------------
# Collection Cards Display with Instant Pagination
# -------------------------------------------------------------
if df_col.empty:
    st.info("💡 Your Vault is currently empty. Use any of the import tools above to add cards!")
else:
    v_top1, v_top2 = st.columns([2, 3])
    with v_top1:
        st.markdown(f"#### 🏆 Your Collection ({len(df_col)} Items)")
    with v_top2:
        v_search_query = st.text_input("🔍 Search Vault", placeholder="Search card name, set, #, or cert...", key="vault_search_box")

    f_col1, f_col2, f_col3 = st.columns([2, 1.2, 1.2])
    with f_col1:
        status_filter = st.selectbox(
            "Filter by Collection Status:",
            [
                "All Cards in Vault",
                "🔄 Upgrade Candidates (Raw or Sub-10)",
                "👑 Peak Grade 10s (Gem Mint & Pristine 10)",
                "Raw Singles Only",
                "Graded Slabs Only",
            ],
            key="vault_status_filter",
        )
    with f_col2:
        per_page_choice = st.selectbox("Cards per page:", [12, 24, 48, "All"], index=0, key="vault_per_page")
    with f_col3:
        view_mode = st.radio("Display Layout:", ["🃏 Card Grid View", "📋 Table / List View"], horizontal=True, key="vault_v_mode")

    df_filtered = df_col.copy()
    if status_filter == "🔄 Upgrade Candidates (Raw or Sub-10)":
        df_filtered = df_filtered[df_filtered["is_upgrade_candidate"] == 1]
        st.info(f"💡 Showing **{len(df_filtered)} Upgrade Candidates** in your Vault (cards owned as Raw or Sub-10 ready to be upgraded to a Pristine 10 / PSA 10).")
    elif status_filter == "👑 Peak Grade 10s (Gem Mint & Pristine 10)":
        df_filtered = df_filtered[(df_filtered["is_raw"] == 0) & (df_filtered["grade"] >= 10.0)]
        st.success(f"👑 Showing **{len(df_filtered)} Peak Grade 10 Slabs** (Gem Mint & Pristine 10).")
    elif status_filter == "Raw Singles Only":
        df_filtered = df_filtered[df_filtered["is_raw"] == 1]
    elif status_filter == "Graded Slabs Only":
        df_filtered = df_filtered[df_filtered["is_raw"] == 0]

    if v_search_query:
        sq = v_search_query.strip().lower()
        df_filtered = df_filtered[
            df_filtered["card_name"].str.lower().str.contains(sq, na=False) |
            df_filtered["set_name"].str.lower().str.contains(sq, na=False) |
            df_filtered["card_number"].astype(str).str.lower().str.contains(sq, na=False) |
            df_filtered["cert_number"].astype(str).str.lower().str.contains(sq, na=False) |
            df_filtered["grade_label"].astype(str).str.lower().str.contains(sq, na=False)
        ]

    per_page = len(df_filtered) if per_page_choice == "All" or len(df_filtered) == 0 else int(per_page_choice)
    total_pages = max(1, (len(df_filtered) + per_page - 1) // per_page) if per_page > 0 else 1

    if total_pages > 1:
        pg_c1, pg_c2, pg_c3 = st.columns([1, 2, 1])
        with pg_c2:
            page_num = st.number_input(f"Page (1 to {total_pages})", min_value=1, max_value=total_pages, value=1, step=1, key="v_page_num")
    else:
        page_num = 1

    start_idx = (page_num - 1) * per_page
    end_idx = min(start_idx + per_page, len(df_filtered))
    page_col_df = df_filtered.iloc[start_idx:end_idx]

    if total_pages > 1:
        st.caption(f"Showing cards **{start_idx + 1}–{end_idx}** of **{len(df_filtered)}** (Page {page_num} of {total_pages})")

    if "Card Grid" in view_mode:
        grid_cols = st.columns(3)
        for idx, (_, row) in enumerate(page_col_df.iterrows()):
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

                # Lightweight Action Buttons (Zero DOM form bloat)
                b1, b2, b3 = st.columns(3)
                with b1:
                    if st.button("✏️ Edit", key=f"btn_edit_{row['id']}", use_container_width=True):
                        st.session_state["editing_card_id"] = row["id"]
                        st.rerun()

                with b2:
                    if st.button("🗑️ Del", key=f"btn_del_{row['id']}", use_container_width=True):
                        st.session_state["deleting_card_id"] = row["id"]
                        st.rerun()

                with b3:
                    with st.popover("ℹ️ Info"):
                        st.markdown(f"#### 🔍 {row['card_name']}")
                        st.markdown(f"**Set:** {row['set_name']} • **Number:** `{card_num_str}`")
                        st.markdown(f"**Edition:** {row['edition']} • **Language:** {row['language']}")
                        if row["is_error"] == 1 and row.get("error_type"):
                            st.error(f"**⚠️ Known Card Errors & Misprints:**\n\n{row['error_type']}")

                        # Upgrade Intelligence in Popover
                        if row.get("is_upgrade_candidate"):
                            target_val = float(row.get("est_grade10_target") or 0.0)
                            u_delta = float(row.get("upgrade_value_delta") or 0.0)
                            st.markdown(f"""
                            <div style="background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 8px; padding: 8px 12px; margin: 8px 0;">
                                <div style="font-weight: 700; color: #f59e0b; font-size: 0.85rem;">🔄 Upgrade Candidate</div>
                                <div style="font-size: 0.82rem; color: #cbd5e1;">Target: <strong>CGC Pristine 10 / PSA 10</strong></div>
                                <div style="font-size: 0.82rem; color: #ffd591;">Est. Pristine Value: <strong>${target_val:,.2f}</strong> (+${u_delta:,.2f} gain)</div>
                            </div>
                            """, unsafe_allow_html=True)
                        elif int(row.get("is_raw") or 0) == 0 and float(row.get("grade") or 0) >= 10.0:
                            st.markdown(f"""
                            <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 8px; padding: 8px 12px; margin: 8px 0;">
                                <div style="font-weight: 700; color: #10b981; font-size: 0.85rem;">👑 Peak Grade Achieved</div>
                                <div style="font-size: 0.82rem; color: #cbd5e1;">{row['grading_company']} {row['grade_label']} Slab</div>
                            </div>
                            """, unsafe_allow_html=True)

                        p_g10 = int(row.get("pop_grade10") or 0)
                        p_p10 = int(row.get("pop_pristine10") or 0)
                        if p_g10 > 0 or p_p10 > 0:
                            st.markdown(f"**📊 Population:** PSA 10: `{p_g10}` | Pristine 10: `{p_p10}`")

                        st.markdown(f"- **Purchase Price:** `${row['purchase_price']:,.2f}` on {row['purchase_date']}")
                        st.markdown(f"- **Est. Market Value:** `${row['current_market_value']:,.2f}` ({gain_sign}${row['unrealized_gain']:,.2f})")
                        if row.get("cert_number"):
                            st.markdown(f"- **Cert #:** `{row['cert_number']}` ({row['grading_company']} {row['grade_label']})")
                        if row.get("notes"):
                            st.markdown(f"- **Notes:** {row['notes']}")

                        # Quick Comps Search Links
                        c_raw_url = generate_ebay_search_url(row["card_name"], row["set_name"], row["card_number"], is_raw=True)
                        c_g10_url = generate_ebay_search_url(row["card_name"], row["set_name"], row["card_number"], grade_tier="PSA 10")
                        c_pc_url = get_pricecharting_search_url(row["card_name"], row["set_name"], row["card_number"])
                        st.markdown(f"""
                        <div style="display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap;">
                            <a href="{c_raw_url}" target="_blank" style="font-size: 0.75rem; color: #60a5fa; text-decoration: none; background: #181920; padding: 3px 8px; border-radius: 4px; border: 1px solid #334155;">🔍 Raw Comps ↗</a>
                            <a href="{c_g10_url}" target="_blank" style="font-size: 0.75rem; color: #f59e0b; text-decoration: none; background: #181920; padding: 3px 8px; border-radius: 4px; border: 1px solid #334155;">💎 PSA 10 Comps ↗</a>
                            <a href="{c_pc_url}" target="_blank" style="font-size: 0.75rem; color: #10b981; text-decoration: none; background: #181920; padding: 3px 8px; border-radius: 4px; border: 1px solid #334155;">📊 Charting ↗</a>
                        </div>
                        """, unsafe_allow_html=True)
    else:
        # Table / List View
        df_display_tbl = page_col_df.copy()
        df_display_tbl["Status"] = df_display_tbl.apply(
            lambda r: "👑 Peak 10" if (r["is_raw"] == 0 and r["grade"] >= 10.0) else ("🔄 Upgrade" if r["is_upgrade_candidate"] == 1 else "Standard"),
            axis=1
        )
        st.dataframe(
            df_display_tbl[[
                "card_name", "set_name", "card_number", "grading_company",
                "grade_label", "Status", "cert_number", "edition", "language",
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
