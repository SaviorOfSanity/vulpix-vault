"""
The Vulpix Vault v2 — Unified FastAPI Backend & Static SPA Server.
Single process, single SQLite database, single canonical catalog, zero Streamlit hacks.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.catalog_builder import (
    TCGDEX_LANGUAGES,
    cache_images_locally,
    classify_variant,
    extract_base_number,
    refresh_pokecottage_remote,
    seed_canonical_catalog,
    slugify,
    sync_tcgdex_all_languages,
    translate_and_dedupe_existing_catalog,
)
from backend.db import (
    SCHEMA_VERSION,
    get_cached_cards_dir,
    get_conn,
    get_db_path,
    get_project_root,
    get_static_cards_dir,
    init_schema,
)
from backend.ebay_links import get_verification_links
from backend.ebay_radar import (
    dispatch_radar_alerts,
    evaluate_deal,
    expire_ended_listings,
    get_radar_config,
    run_ebay_radar_scan,
    save_radar_config,
    seed_default_radar_queries,
    track_single_ebay_url,
)
from backend.error_annotations import get_visual_callouts
from backend.migration import match_catalog_key, migrate_legacy_vault_if_needed
from backend.models import (
    CustomCardCreate,
    ListingActionUpdate,
    ListingWonRequest,
    PriceOverrideIn,
    RadarQueryCreate,
    RadarQueryToggle,
    RadarSettingsUpdate,
    SyncJobRequest,
    TrackAuctionRequest,
    VaultItemCreate,
    VaultItemUpdate,
)
from backend.notifier import send_alert
from backend.pricing import refresh_catalog_prices_batch, refresh_single_card_price

# In-memory job status registry for non-blocking background sync tasks
SYNC_STATE: Dict[str, Dict[str, Any]] = {
    "tcgdex": {"running": False, "progress": 0, "total": 0, "message": "Idle", "result": None, "finished_at": None},
    "prices": {"running": False, "progress": 0, "total": 0, "message": "Idle", "result": None, "finished_at": None},
    "cache_images": {"running": False, "progress": 0, "total": 0, "message": "Idle", "result": None, "finished_at": None},
    "pokecottage": {"running": False, "progress": 0, "total": 0, "message": "Idle", "result": None, "finished_at": None},
    "radar": {"running": False, "progress": 0, "total": 0, "message": "Idle", "result": None, "finished_at": None},
}


def bootstrap_database() -> None:
    """Runs once at server startup: init schema, seed canonical catalog, translate/dedupe, migrate legacy vault once."""
    init_schema()
    seed_canonical_catalog()
    translate_and_dedupe_existing_catalog()
    migrate_legacy_vault_if_needed()
    seed_default_radar_queries()


async def _radar_scheduler_loop() -> None:
    """Lightweight background scheduler for Phase 2 eBay Radar auto-scans & ending-soon alerts."""
    last_auto_scan = 0.0
    await asyncio.sleep(15)
    while True:
        try:
            expire_ended_listings()
            cfg = get_radar_config(mask_secrets=False)
            now_ts = asyncio.get_event_loop().time()
            interval_sec = max(300, int(cfg["auto_scan_interval_min"]) * 60)

            if cfg["ebay_configured"] and cfg["auto_scan_enabled"] and not SYNC_STATE["radar"]["running"]:
                if (now_ts - last_auto_scan) >= interval_sec:
                    last_auto_scan = now_ts
                    asyncio.create_task(_run_job("radar", lambda cb: run_ebay_radar_scan(progress_cb=cb)))
            else:
                # Still dispatch ending-soon alerts for manually watched auctions even without auto-scan!
                await dispatch_radar_alerts()
        except asyncio.CancelledError:
            break
        except Exception:
            pass
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap_database()
    scheduler = asyncio.create_task(_radar_scheduler_loop())
    try:
        yield
    finally:
        scheduler.cancel()
        try:
            await scheduler
        except asyncio.CancelledError:
            pass


app = FastAPI(title="The Vulpix Vault API", version="2.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _resolve_display_image(row: Dict[str, Any]) -> str:
    local_img = (row.get("local_image") or "").strip()
    if local_img:
        if local_img.startswith("cached/"):
            fname = local_img.split("/", 1)[1]
            if os.path.isfile(os.path.join(get_cached_cards_dir(), fname)):
                return f"/cached-cards/{fname}"
        elif os.path.isfile(os.path.join(get_static_cards_dir(), os.path.basename(local_img))):
            return f"/static/cards/{os.path.basename(local_img)}"

    img_url = (row.get("image_url") or "").strip()
    if img_url.startswith("dashboard/static/cards/"):
        return f"/static/cards/{os.path.basename(img_url)}"
    return img_url


def _format_vault_item(row: Dict[str, Any], cat: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    is_raw = bool(row.get("is_raw"))
    grade = float(row.get("grade") or 0.0)
    cost = float(row.get("purchase_price") or 0.0)
    grade_label = row.get("grade_label") or ("Raw Single" if is_raw else "Gem Mint")

    # Honest market valuation from linked catalog card (never fakes $45!)
    market_val: Optional[float] = None
    market_source: Optional[str] = None
    target_g10: Optional[float] = None

    if cat:
        p_raw = cat.get("price_raw")
        p_g9 = cat.get("price_grade9")
        p_g10 = cat.get("price_grade10")
        p_src = cat.get("price_source")
        target_g10 = p_g10

        if is_raw and p_raw is not None:
            market_val = p_raw
            market_source = p_src
        elif not is_raw and grade >= 10.0 and p_g10 is not None:
            mult = 1.35 if "pristine" in grade_label.lower() else (2.2 if "black label" in grade_label.lower() else 1.0)
            market_val = round(p_g10 * mult, 2)
            market_source = p_src
        elif not is_raw and grade >= 9.0 and p_g9 is not None:
            market_val = p_g9
            market_source = p_src
        elif not is_raw and p_raw is not None and p_g10 is None:
            market_val = p_raw
            market_source = f"{p_src} (Raw Ref)"

    gain = round(market_val - cost, 2) if (market_val is not None and cost > 0) else None
    roi = round((gain / cost) * 100, 1) if (gain is not None and cost > 0) else None
    needs_upgrade = bool(is_raw or grade < 10.0)

    img = (row.get("image_url") or "").strip()
    if img.startswith("dashboard/static/cards/"):
        img = f"/static/cards/{os.path.basename(img)}"
    if not img and cat:
        img = _resolve_display_image(cat)

    cert = (row.get("cert_number") or "").strip()
    clean_cert = re.sub(r"[^\d]", "", cert)
    grader = (row.get("grading_company") or ("RAW" if is_raw else "PSA")).upper()
    cert_url = ""
    if clean_cert:
        if grader == "PSA":
            cert_url = f"https://www.psacard.com/cert/{clean_cert}"
        elif grader == "CGC":
            cert_url = f"https://www.cgccards.com/certlookup/{clean_cert}/"

    return {
        "id": int(row["id"]),
        "catalog_key": row.get("catalog_key"),
        "card_name": row["card_name"],
        "set_name": row["set_name"],
        "card_number": row.get("card_number") or "",
        "language": row.get("language") or "English",
        "edition": row.get("edition") or "Unlimited",
        "is_raw": is_raw,
        "grading_company": grader,
        "grade": grade,
        "grade_label": grade_label,
        "cert_number": cert,
        "cert_url": cert_url,
        "purchase_price": round(cost, 2),
        "purchase_date": row.get("purchase_date") or "",
        "image_url": img,
        "notes": row.get("notes") or "",
        "market_value": market_val,
        "market_source": market_source,
        "unrealized_gain": gain,
        "roi_percent": roi,
        "needs_upgrade": needs_upgrade,
        "target_grade10_price": target_g10,
    }


@app.get("/api/health")
def api_health() -> Dict[str, Any]:
    db_path = get_db_path()
    size_kb = round(os.path.getsize(db_path) / 1024, 1) if os.path.isfile(db_path) else 0.0
    with get_conn() as conn:
        cat_count = conn.execute("SELECT COUNT(*) FROM catalog_cards;").fetchone()[0]
        vault_count = conn.execute("SELECT COUNT(*) FROM vault_items;").fetchone()[0]
        priced_count = conn.execute(
            "SELECT COUNT(*) FROM catalog_cards WHERE price_source IS NOT NULL AND price_source != '';"
        ).fetchone()[0]
    return {
        "status": "ok",
        "version": "2.1.0",
        "schema_version": SCHEMA_VERSION,
        "db_path": db_path,
        "db_size_kb": size_kb,
        "catalog_count": cat_count,
        "vault_count": vault_count,
        "priced_count": priced_count,
    }


@app.get("/api/catalog")
def api_get_catalog() -> Dict[str, Any]:
    """Returns full canonical catalog enriched with ownership, pricing, visual error callouts, and summary stats."""
    with get_conn() as conn:
        cat_rows = [
            dict(r) for r in conn.execute(
                "SELECT * FROM catalog_cards ORDER BY release_year ASC, set_name ASC, CAST(base_number AS INTEGER) ASC, card_number ASC, edition ASC;"
            ).fetchall()
        ]
        vault_rows = [dict(r) for r in conn.execute("SELECT * FROM vault_items ORDER BY purchase_date DESC;").fetchall()]

    cat_by_key = {r["catalog_key"]: r for r in cat_rows}
    owned_by_key: Dict[str, List[Dict[str, Any]]] = {}
    for vr in vault_rows:
        ck = vr.get("catalog_key")
        if ck:
            owned_by_key.setdefault(ck, []).append(_format_vault_item(vr, cat_by_key.get(ck)))

    cards_out: List[Dict[str, Any]] = []
    unique_groups = set()
    owned_groups = set()
    by_language: Dict[str, Dict[str, int]] = {}
    by_variant: Dict[str, int] = {}

    variants_owned = 0
    upgradeable_owned = 0
    cost_to_complete_raw = 0.0
    cost_to_complete_g10 = 0.0
    priced_missing_raw = 0
    priced_missing_g10 = 0
    priced_total = 0

    for row in cat_rows:
        ck = row["catalog_key"]
        owned_items = owned_by_key.get(ck, [])
        is_owned = len(owned_items) > 0

        highest_grade = 0.0
        best_badge = ""
        needs_upgrade = False
        if is_owned:
            variants_owned += 1
            owned_groups.add(row["card_group_key"])
            graded = [it for it in owned_items if not it["is_raw"]]
            if graded:
                best = max(graded, key=lambda x: (x["grade"], 1 if "pristine" in x["grade_label"].lower() else 0))
                highest_grade = best["grade"]
                g_num = int(best["grade"]) if best["grade"] == int(best["grade"]) else best["grade"]
                if "pristine" in best["grade_label"].lower():
                    best_badge = f"{best['grading_company']} 10 Pristine"
                elif "black label" in best["grade_label"].lower():
                    best_badge = "BGS 10 Black"
                else:
                    best_badge = f"{best['grading_company']} {g_num}"
                needs_upgrade = highest_grade < 10.0
            else:
                best_badge = "RAW"
                needs_upgrade = True
            if needs_upgrade:
                upgradeable_owned += 1

        unique_groups.add(row["card_group_key"])

        lang = row["language"]
        lang_stat = by_language.setdefault(lang, {"total": 0, "owned": 0})
        lang_stat["total"] += 1
        if is_owned:
            lang_stat["owned"] += 1

        vk = row["variant_key"]
        by_variant[vk] = by_variant.get(vk, 0) + 1

        p_raw = row.get("price_raw")
        p_g9 = row.get("price_grade9")
        p_g10 = row.get("price_grade10")
        if row.get("price_source"):
            priced_total += 1

        if not is_owned:
            if p_raw is not None:
                cost_to_complete_raw += float(p_raw)
                priced_missing_raw += 1
            if p_g10 is not None:
                cost_to_complete_g10 += float(p_g10)
                priced_missing_g10 += 1

        try:
            callouts = json.loads(row.get("visual_callouts") or "[]")
        except Exception:
            callouts = []

        links = get_verification_links(
            card_name=row["card_name"],
            set_name=row["set_name"],
            card_number=row["card_number"],
            edition=row["edition"],
            language=lang,
            pricecharting_url=row.get("pricecharting_url") or "",
            tcgplayer_url=row.get("tcgplayer_url") or "",
        )

        cards_out.append({
            "catalog_key": ck,
            "card_group_key": row["card_group_key"],
            "card_name": row["card_name"],
            "native_name": row.get("native_name") or "",
            "set_name": row["set_name"],
            "native_set_name": row.get("native_set_name") or "",
            "set_id": row.get("set_id") or "",
            "series": row.get("series") or "",
            "card_number": row.get("card_number") or "",
            "base_number": row.get("base_number") or "",
            "release_year": int(row.get("release_year") or 2000),
            "release_date": row.get("release_date") or "",
            "language": lang,
            "region": row.get("region") or "",
            "edition": row["edition"],
            "variant_key": vk,
            "rarity": row.get("rarity") or "Common",
            "artist": row.get("artist") or "",
            "is_error": bool(row.get("is_error")),
            "error_description": row.get("error_description") or "",
            "visual_callouts": callouts,
            "image_url": _resolve_display_image(row),
            "image_is_localized": bool(row.get("image_is_localized", 1)),
            "price_raw": p_raw,
            "price_grade9": p_g9,
            "price_grade10": p_g10,
            "price_source": row.get("price_source"),
            "price_updated_at": row.get("price_updated_at"),
            "price_manual_lock": bool(row.get("price_manual_lock")),
            "notes": row.get("notes") or "",
            "source": row.get("source") or "",
            "is_owned": is_owned,
            "owned_count": len(owned_items),
            "owned_items": owned_items,
            "highest_grade": highest_grade,
            "best_owned_badge": best_badge,
            "needs_upgrade": needs_upgrade,
            **links,
        })

    variants_total = len(cards_out)
    missing_total = variants_total - variants_owned
    unique_total = len(unique_groups)
    unique_owned = len(owned_groups)

    return {
        "cards": cards_out,
        "summary": {
            "unique_total": unique_total,
            "unique_owned": unique_owned,
            "unique_pct": round((unique_owned / unique_total) * 100, 1) if unique_total else 0.0,
            "variants_total": variants_total,
            "variants_owned": variants_owned,
            "variants_missing": missing_total,
            "variants_pct": round((variants_owned / variants_total) * 100, 1) if variants_total else 0.0,
            "upgradeable_owned": upgradeable_owned,
            "priced_total": priced_total,
            "priced_missing_raw": priced_missing_raw,
            "priced_missing_g10": priced_missing_g10,
            "cost_to_complete_raw": round(cost_to_complete_raw, 2),
            "cost_to_complete_g10": round(cost_to_complete_g10, 2),
            "by_language": by_language,
            "by_variant": by_variant,
        },
        "supported_languages": [
            {"code": code, "name": name, "region": region}
            for code, name, region, _ in TCGDEX_LANGUAGES
        ],
    }


@app.post("/api/catalog/custom")
def api_add_custom_card(payload: CustomCardCreate) -> Dict[str, Any]:
    ed_label, vk, auto_err, auto_desc = classify_variant(payload.edition, payload.rarity, payload.card_name)
    is_err = 1 if (payload.is_error or auto_err) else 0
    err_desc = payload.error_description or auto_desc
    bnum = extract_base_number(payload.card_number)
    ck = f"user:{slugify(payload.language)}:{slugify(payload.set_name)}-{bnum or '0'}:{slugify(ed_label)}-{slugify(payload.card_name)}"
    callouts = get_visual_callouts(
        set_name=payload.set_name,
        language=payload.language,
        edition=ed_label,
        variant_key=vk,
        is_error=bool(is_err),
        error_description=err_desc,
    )
    with get_conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO catalog_cards (
                catalog_key, card_group_key, card_name, set_name, card_number, base_number,
                release_year, release_date, language, edition, variant_key, rarity, artist,
                is_error, error_description, visual_callouts, image_url, image_is_localized, notes, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, 'user');
        """, (
            ck,
            f"{slugify(payload.set_name)}-{bnum}-{slugify(payload.language)}",
            payload.card_name.strip(),
            payload.set_name.strip(),
            payload.card_number.strip(),
            bnum,
            payload.release_year,
            payload.release_date or f"{payload.release_year}-01-01",
            payload.language,
            ed_label,
            vk,
            payload.rarity,
            payload.artist,
            is_err,
            err_desc,
            json.dumps(callouts),
            payload.image_url.strip(),
            payload.notes.strip(),
        ))
    return {"catalog_key": ck, "status": "created"}


@app.post("/api/catalog/{catalog_key}/refresh-price")
async def api_refresh_card_price(catalog_key: str) -> Dict[str, Any]:
    return await refresh_single_card_price(catalog_key, force=True)


@app.put("/api/catalog/{catalog_key}/price")
def api_override_card_price(catalog_key: str, payload: PriceOverrideIn) -> Dict[str, Any]:
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    with get_conn() as conn:
        exists = conn.execute("SELECT 1 FROM catalog_cards WHERE catalog_key = ?;", (catalog_key,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Card not found")

        if payload.unlock_auto_pricing:
            conn.execute(
                "UPDATE catalog_cards SET price_manual_lock = 0 WHERE catalog_key = ?;",
                (catalog_key,),
            )
            return {"status": "unlocked", "catalog_key": catalog_key}

        conn.execute("""
            UPDATE catalog_cards
            SET price_raw = :raw,
                price_grade9 = :g9,
                price_grade10 = :g10,
                price_source = 'Manual',
                price_updated_at = :ts,
                price_manual_lock = 1,
                pricecharting_url = COALESCE(NULLIF(:pcurl, ''), pricecharting_url),
                tcgplayer_url = COALESCE(NULLIF(:tcgurl, ''), tcgplayer_url)
            WHERE catalog_key = :ck;
        """, {
            "raw": payload.price_raw,
            "g9": payload.price_grade9,
            "g10": payload.price_grade10,
            "ts": now_iso,
            "pcurl": (payload.pricecharting_url or "").strip(),
            "tcgurl": (payload.tcgplayer_url or "").strip(),
            "ck": catalog_key,
        })
        conn.execute("""
            INSERT INTO price_history (catalog_key, price_raw, price_grade9, price_grade10, source)
            VALUES (?, ?, ?, ?, 'Manual');
        """, (catalog_key, payload.price_raw, payload.price_grade9, payload.price_grade10))

    return {"status": "updated", "catalog_key": catalog_key, "price_source": "Manual", "price_updated_at": now_iso}


# =============================================================
# Personal Vault Endpoints
# =============================================================

@app.get("/api/vault")
def api_get_vault() -> Dict[str, Any]:
    with get_conn() as conn:
        vault_rows = [dict(r) for r in conn.execute("SELECT * FROM vault_items ORDER BY purchase_date DESC, id DESC;").fetchall()]
        cat_rows = [dict(r) for r in conn.execute("SELECT * FROM catalog_cards;").fetchall()]

    cat_by_key = {r["catalog_key"]: r for r in cat_rows}
    items = [_format_vault_item(vr, cat_by_key.get(vr.get("catalog_key"))) for vr in vault_rows]

    total_invested = round(sum(i["purchase_price"] for i in items), 2)
    # Use verified market value when present; fall back to purchase cost for unpriced cards so portfolio total stays sane,
    # while explicitly reporting how many items have live verified market prices.
    priced_items = [i for i in items if i["market_value"] is not None]
    total_market = round(sum((i["market_value"] if i["market_value"] is not None else i["purchase_price"]) for i in items), 2)
    net_gain = round(total_market - total_invested, 2)
    roi_pct = round((net_gain / total_invested) * 100, 1) if total_invested > 0 else 0.0

    return {
        "items": items,
        "metrics": {
            "total_items": len(items),
            "graded_count": sum(1 for i in items if not i["is_raw"]),
            "raw_count": sum(1 for i in items if i["is_raw"]),
            "peak_10_count": sum(1 for i in items if (not i["is_raw"] and i["grade"] >= 10.0)),
            "upgrade_candidates": sum(1 for i in items if i["needs_upgrade"]),
            "total_invested": total_invested,
            "total_market_value": total_market,
            "priced_items_count": len(priced_items),
            "net_gain": net_gain,
            "roi_percent": roi_pct,
        },
    }


@app.post("/api/vault")
def api_add_vault_item(payload: VaultItemCreate) -> Dict[str, Any]:
    with get_conn() as conn:
        ck = payload.catalog_key
        cat_row = None
        if ck:
            r = conn.execute("SELECT * FROM catalog_cards WHERE catalog_key = ?;", (ck,)).fetchone()
            if r:
                cat_row = dict(r)
            else:
                ck = None
        if not ck:
            all_cats = [dict(r) for r in conn.execute("SELECT * FROM catalog_cards;").fetchall()]
            ck = match_catalog_key(payload.model_dump(), all_cats)
            if ck:
                cat_row = next((x for x in all_cats if x["catalog_key"] == ck), None)

        img = payload.image_url or (_resolve_display_image(cat_row) if cat_row else "")
        is_raw = 1 if (payload.is_raw or payload.grading_company.upper() == "RAW") else 0
        grader = "RAW" if is_raw else payload.grading_company.upper()
        grade = 0.0 if is_raw else float(payload.grade)
        grade_label = "Raw Single" if is_raw else (payload.grade_label or "Gem Mint")
        p_date = payload.purchase_date or datetime.now().strftime("%Y-%m-%d")

        cur = conn.execute("""
            INSERT INTO vault_items (
                catalog_key, card_name, set_name, card_number, language, edition,
                is_raw, grading_company, grade, grade_label, cert_number,
                purchase_price, purchase_date, image_url, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            ck,
            payload.card_name.strip(),
            payload.set_name.strip(),
            payload.card_number.strip(),
            payload.language.strip(),
            payload.edition.strip(),
            is_raw,
            grader,
            grade,
            grade_label,
            payload.cert_number.strip(),
            float(payload.purchase_price),
            p_date,
            img,
            payload.notes.strip(),
        ))
        new_id = cur.lastrowid
        new_row = dict(conn.execute("SELECT * FROM vault_items WHERE id = ?;", (new_id,)).fetchone())

    return {"item": _format_vault_item(new_row, cat_row)}


@app.put("/api/vault/{item_id}")
def api_update_vault_item(item_id: int, payload: VaultItemUpdate) -> Dict[str, Any]:
    with get_conn() as conn:
        existing = conn.execute("SELECT * FROM vault_items WHERE id = ?;", (item_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Vault item not found")

        merged = dict(existing)
        updates = payload.model_dump(exclude_unset=True)
        for k, v in updates.items():
            if k == "catalog_key" or v is not None:
                merged[k] = v

        is_raw = 1 if (merged.get("is_raw") or str(merged.get("grading_company", "")).upper() == "RAW") else 0
        merged["is_raw"] = is_raw
        merged["grading_company"] = "RAW" if is_raw else str(merged.get("grading_company") or "PSA").upper()
        merged["grade"] = 0.0 if is_raw else float(merged.get("grade") or 0.0)
        if is_raw:
            merged["grade_label"] = "Raw Single"

        conn.execute("""
            UPDATE vault_items
            SET catalog_key = :catalog_key,
                card_name = :card_name,
                set_name = :set_name,
                card_number = :card_number,
                language = :language,
                edition = :edition,
                is_raw = :is_raw,
                grading_company = :grading_company,
                grade = :grade,
                grade_label = :grade_label,
                cert_number = :cert_number,
                purchase_price = :purchase_price,
                purchase_date = :purchase_date,
                image_url = :image_url,
                notes = :notes
            WHERE id = :id;
        """, merged)

        cat_row = None
        if merged.get("catalog_key"):
            r = conn.execute("SELECT * FROM catalog_cards WHERE catalog_key = ?;", (merged["catalog_key"],)).fetchone()
            cat_row = dict(r) if r else None

    return {"item": _format_vault_item(merged, cat_row)}


@app.delete("/api/vault/{item_id}")
def api_delete_vault_item(item_id: int) -> Dict[str, Any]:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM vault_items WHERE id = ?;", (item_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Vault item not found")
    return {"deleted": True, "id": item_id}


# =============================================================
# Live Sync & Background Jobs
# =============================================================

@app.get("/api/sync/status")
def api_sync_status() -> Dict[str, Any]:
    return SYNC_STATE


async def _run_job(job_name: str, coro_factory) -> None:
    state = SYNC_STATE[job_name]
    state["running"] = True
    state["progress"] = 0
    state["total"] = 0
    state["message"] = "Starting..."
    state["result"] = None

    def on_progress(done: int, total: int, msg: str) -> None:
        state["progress"] = done
        state["total"] = total
        state["message"] = msg

    try:
        res = await coro_factory(on_progress)
        state["result"] = res
        state["message"] = state["message"] if state["message"] != "Starting..." else "Completed."
    except Exception as exc:
        state["result"] = {"error": str(exc)}
        state["message"] = f"Error: {exc}"
    finally:
        state["running"] = False
        state["finished_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


@app.post("/api/sync/tcgdex")
async def api_start_tcgdex_sync(req: Optional[SyncJobRequest] = None) -> Dict[str, Any]:
    if SYNC_STATE["tcgdex"]["running"]:
        return {"started": False, "message": "TCGdex multi-language sync is already running."}
    langs = req.languages if req else None
    asyncio.create_task(_run_job("tcgdex", lambda cb: sync_tcgdex_all_languages(languages=langs, progress_cb=cb)))
    return {"started": True, "message": "Started TCGdex 14-language sync."}


@app.post("/api/sync/prices")
async def api_start_price_sync(req: Optional[SyncJobRequest] = None) -> Dict[str, Any]:
    if SYNC_STATE["prices"]["running"]:
        return {"started": False, "message": "Live price refresh is already running."}
    only_unpriced = req.only_unpriced if req else True
    limit = req.limit if req else None
    asyncio.create_task(_run_job("prices", lambda cb: refresh_catalog_prices_batch(only_unpriced=only_unpriced, limit=limit, progress_cb=cb)))
    return {"started": True, "message": "Started live market price refresh."}


@app.post("/api/sync/cache-images")
async def api_start_image_cache() -> Dict[str, Any]:
    if SYNC_STATE["cache_images"]["running"]:
        return {"started": False, "message": "Image caching is already running."}
    asyncio.create_task(_run_job("cache_images", lambda cb: cache_images_locally(progress_cb=cb)))
    return {"started": True, "message": "Started local card scan caching."}


@app.post("/api/sync/pokecottage")
async def api_start_pokecottage_sync() -> Dict[str, Any]:
    if SYNC_STATE["pokecottage"]["running"]:
        return {"started": False, "message": "PokeCottage sync is already running."}
    asyncio.create_task(_run_job("pokecottage", lambda cb: refresh_pokecottage_remote(progress_cb=cb)))
    return {"started": True, "message": "Started PokeCottage remote refresh."}


# =============================================================
# Phase 2: eBay Auction Radar & Sniper Alerts Endpoints
# =============================================================

@app.get("/api/radar")
def api_get_radar(include_dismissed: bool = False) -> Dict[str, Any]:
    """Returns active eBay listings enriched with Master Set ownership, live comps, and Radar config."""
    expire_ended_listings()
    now_utc = datetime.now(timezone.utc)

    with get_conn() as conn:
        where_clause = "is_active = 1" if include_dismissed else "is_active = 1 AND is_dismissed = 0"
        listing_rows = [
            dict(r) for r in conn.execute(
                f"""SELECT * FROM ebay_listings
                    WHERE {where_clause}
                    ORDER BY CASE WHEN end_time = '' THEN 1 ELSE 0 END ASC, end_time ASC, total_cost ASC;"""
            ).fetchall()
        ]
        cat_rows = [dict(r) for r in conn.execute("SELECT * FROM catalog_cards;").fetchall()]
        vault_rows = [dict(r) for r in conn.execute("SELECT * FROM vault_items WHERE catalog_key IS NOT NULL;").fetchall()]
        query_rows = [dict(r) for r in conn.execute("SELECT * FROM radar_queries ORDER BY id ASC;").fetchall()]

    cat_by_key = {r["catalog_key"]: r for r in cat_rows}
    vault_by_key: Dict[str, List[Dict[str, Any]]] = {}
    for vr in vault_rows:
        vault_by_key.setdefault(vr["catalog_key"], []).append(vr)

    listings_out: List[Dict[str, Any]] = []
    needed_matches = 0
    hot_deals = 0
    ending_under_1h = 0
    watched_count = 0
    auctions_count = 0
    bin_count = 0

    for lr in listing_rows:
        ck = lr.get("catalog_key")
        cat = cat_by_key.get(ck) if ck else None

        # Always re-evaluate deal tier against latest catalog prices so manual price edits reflect instantly
        comp, deal_tier, discount_pct = evaluate_deal(
            float(lr.get("total_cost") or 0.0),
            lr.get("detected_grader") or "RAW",
            float(lr.get("detected_grade") or 0.0),
            lr.get("detected_grade_label") or "Raw Single",
            cat,
        )

        # Ownership status relative to user's Personal Vault
        ownership_status = "UNMATCHED"
        best_owned_badge = ""
        if cat:
            owned_list = vault_by_key.get(ck, [])
            if not owned_list:
                ownership_status = "MISSING"
            else:
                graded = [v for v in owned_list if not v["is_raw"]]
                if graded:
                    best = max(graded, key=lambda x: float(x["grade"] or 0.0))
                    g = float(best["grade"] or 0.0)
                    g_txt = int(g) if g == int(g) else g
                    best_owned_badge = f"{best['grading_company']} {g_txt}"
                    ownership_status = "OWNED_10" if g >= 10.0 else "UPGRADE"
                else:
                    best_owned_badge = "RAW"
                    ownership_status = "UPGRADE"

        secs_left: Optional[int] = None
        if lr.get("end_time"):
            try:
                et = datetime.fromisoformat(lr["end_time"].replace("Z", "+00:00"))
                secs_left = max(0, int((et - now_utc).total_seconds()))
            except Exception:
                secs_left = None

        is_needed = ownership_status in ("MISSING", "UPGRADE")
        if is_needed:
            needed_matches += 1
        if deal_tier in ("SNIPE", "GOOD") and (is_needed or lr.get("is_watched")):
            hot_deals += 1
        if secs_left is not None and 0 < secs_left <= 3600:
            ending_under_1h += 1
        if lr.get("is_watched"):
            watched_count += 1
        if "AUCTION" in (lr.get("buying_option") or ""):
            auctions_count += 1
        else:
            bin_count += 1

        listings_out.append({
            "ebay_item_id": lr["ebay_item_id"],
            "title": lr["title"],
            "url": lr["url"],
            "image_url": lr.get("image_url") or (_resolve_display_image(cat) if cat else ""),
            "buying_option": lr.get("buying_option") or "AUCTION",
            "current_price": round(float(lr.get("current_price") or 0.0), 2),
            "shipping_cost": round(float(lr.get("shipping_cost") or 0.0), 2),
            "total_cost": round(float(lr.get("total_cost") or 0.0), 2),
            "bid_count": int(lr.get("bid_count") or 0),
            "end_time": lr.get("end_time") or "",
            "seconds_remaining": secs_left,
            "seller_username": lr.get("seller_username") or "",
            "seller_feedback_pct": lr.get("seller_feedback_pct"),
            "condition": lr.get("condition") or "",
            "detected_grader": lr.get("detected_grader") or "RAW",
            "detected_grade": float(lr.get("detected_grade") or 0.0),
            "detected_grade_label": lr.get("detected_grade_label") or "Raw Single",
            "catalog_key": ck,
            "match_confidence": int(lr.get("match_confidence") or 0),
            "market_comp": comp,
            "deal_tier": deal_tier,
            "discount_pct": discount_pct,
            "is_watched": bool(lr.get("is_watched")),
            "is_dismissed": bool(lr.get("is_dismissed")),
            "source_query": lr.get("source_query") or "",
            "ownership_status": ownership_status,
            "best_owned_badge": best_owned_badge,
            "matched_card_name": cat["card_name"] if cat else "",
            "matched_set_name": cat["set_name"] if cat else "",
            "matched_card_number": cat["card_number"] if cat else "",
            "matched_language": cat["language"] if cat else "",
            "matched_edition": cat["edition"] if cat else "",
            "matched_variant_key": cat["variant_key"] if cat else "",
            "matched_is_error": bool(cat["is_error"]) if cat else False,
            "matched_image_url": _resolve_display_image(cat) if cat else "",
        })

    return {
        "listings": listings_out,
        "summary": {
            "total_active": len(listings_out),
            "needed_matches": needed_matches,
            "hot_deals": hot_deals,
            "ending_under_1h": ending_under_1h,
            "watched_count": watched_count,
            "auctions_count": auctions_count,
            "bin_count": bin_count,
        },
        "config": get_radar_config(mask_secrets=True),
        "queries": [
            {
                "id": int(q["id"]),
                "query": q["query"],
                "label": q["label"],
                "buying_filter": q["buying_filter"],
                "enabled": bool(q["enabled"]),
            }
            for q in query_rows
        ],
        "scan_state": SYNC_STATE["radar"],
    }


@app.post("/api/radar/scan")
async def api_start_radar_scan() -> Dict[str, Any]:
    if SYNC_STATE["radar"]["running"]:
        return {"started": False, "message": "eBay Auction Radar scan is already running."}
    cfg = get_radar_config(mask_secrets=False)
    if not cfg["ebay_configured"]:
        raise HTTPException(
            status_code=400,
            detail="Add your free eBay Client ID & Secret in Radar Setup first (or use + Track Auction URL manually).",
        )
    asyncio.create_task(_run_job("radar", lambda cb: run_ebay_radar_scan(progress_cb=cb)))
    return {"started": True, "message": "Started live eBay Auction Radar scan."}


@app.post("/api/radar/track")
async def api_track_auction(payload: TrackAuctionRequest) -> Dict[str, Any]:
    try:
        saved = await track_single_ebay_url(
            payload.url,
            title=payload.title,
            current_price=payload.current_price,
            shipping_cost=payload.shipping_cost,
            end_time=payload.end_time,
            minutes_remaining=payload.minutes_remaining,
            buying_option=payload.buying_option,
            catalog_key=payload.catalog_key,
        )
        return {"status": "tracked", "listing": saved}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.put("/api/radar/listings/{item_id}")
def api_update_radar_listing(item_id: str, payload: ListingActionUpdate) -> Dict[str, Any]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM ebay_listings WHERE ebay_item_id = ?;", (item_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Listing not found")
        cur_data = dict(row)
        updates = payload.model_dump(exclude_unset=True)

        if "is_watched" in updates and updates["is_watched"] is not None:
            cur_data["is_watched"] = 1 if updates["is_watched"] else 0
        if "is_dismissed" in updates and updates["is_dismissed"] is not None:
            cur_data["is_dismissed"] = 1 if updates["is_dismissed"] else 0
        if "current_price" in updates and updates["current_price"] is not None:
            cur_data["current_price"] = round(float(updates["current_price"]), 2)
        if "shipping_cost" in updates and updates["shipping_cost"] is not None:
            cur_data["shipping_cost"] = round(float(updates["shipping_cost"]), 2)
        cur_data["total_cost"] = round(float(cur_data["current_price"]) + float(cur_data["shipping_cost"]), 2)
        if "end_time" in updates and updates["end_time"] is not None:
            cur_data["end_time"] = str(updates["end_time"]).strip()

        if "catalog_key" in updates:
            new_ck = updates["catalog_key"] or None
            cur_data["catalog_key"] = new_ck
            cur_data["match_confidence"] = 100 if new_ck else 0

        cat = None
        if cur_data.get("catalog_key"):
            c_row = conn.execute("SELECT * FROM catalog_cards WHERE catalog_key = ?;", (cur_data["catalog_key"],)).fetchone()
            cat = dict(c_row) if c_row else None

        comp, tier, disc = evaluate_deal(
            cur_data["total_cost"],
            cur_data["detected_grader"],
            float(cur_data["detected_grade"] or 0.0),
            cur_data["detected_grade_label"],
            cat,
        )
        cur_data["market_comp"] = comp
        cur_data["deal_tier"] = tier
        cur_data["discount_pct"] = disc

        conn.execute("""
            UPDATE ebay_listings
            SET is_watched = :is_watched,
                is_dismissed = :is_dismissed,
                catalog_key = :catalog_key,
                match_confidence = :match_confidence,
                current_price = :current_price,
                shipping_cost = :shipping_cost,
                total_cost = :total_cost,
                end_time = :end_time,
                market_comp = :market_comp,
                deal_tier = :deal_tier,
                discount_pct = :discount_pct
            WHERE ebay_item_id = :ebay_item_id;
        """, cur_data)

    return {"status": "updated", "ebay_item_id": item_id}


@app.post("/api/radar/listings/{item_id}/won")
def api_mark_listing_won(item_id: str, payload: Optional[ListingWonRequest] = None) -> Dict[str, Any]:
    """1-click 'Won It -> Add to Personal Vault' from any Auction Radar card."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM ebay_listings WHERE ebay_item_id = ?;", (item_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Listing not found")
        lr = dict(row)
        cat = None
        if lr.get("catalog_key"):
            cr = conn.execute("SELECT * FROM catalog_cards WHERE catalog_key = ?;", (lr["catalog_key"],)).fetchone()
            cat = dict(cr) if cr else None

        grader = (lr.get("detected_grader") or "RAW").upper()
        is_raw = 1 if grader == "RAW" else 0
        grade = 0.0 if is_raw else float(lr.get("detected_grade") or 0.0)
        grade_label = "Raw Single" if is_raw else (lr.get("detected_grade_label") or "Gem Mint")
        paid = float(payload.purchase_price) if (payload and payload.purchase_price is not None) else float(lr.get("total_cost") or 0.0)
        cert = payload.cert_number.strip() if payload else ""
        extra_note = payload.notes.strip() if payload else ""
        note_text = f"Won on eBay: {lr['url']}" + (f" | {extra_note}" if extra_note else "")

        cur = conn.execute("""
            INSERT INTO vault_items (
                catalog_key, card_name, set_name, card_number, language, edition,
                is_raw, grading_company, grade, grade_label, cert_number,
                purchase_price, purchase_date, image_url, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            cat["catalog_key"] if cat else None,
            cat["card_name"] if cat else lr["title"][:80],
            cat["set_name"] if cat else "eBay Purchase",
            cat["card_number"] if cat else "",
            cat["language"] if cat else "English",
            cat["edition"] if cat else "Unlimited",
            is_raw,
            grader,
            grade,
            grade_label,
            cert,
            round(paid, 2),
            datetime.now().strftime("%Y-%m-%d"),
            _resolve_display_image(cat) if cat else (lr.get("image_url") or ""),
            note_text,
        ))
        new_vid = cur.lastrowid
        conn.execute("UPDATE ebay_listings SET is_active = 0, is_watched = 0 WHERE ebay_item_id = ?;", (item_id,))

    return {"status": "moved_to_vault", "vault_item_id": new_vid}


@app.delete("/api/radar/listings/{item_id}")
def api_delete_radar_listing(item_id: str) -> Dict[str, Any]:
    with get_conn() as conn:
        conn.execute("DELETE FROM ebay_listings WHERE ebay_item_id = ?;", (item_id,))
    return {"deleted": True, "ebay_item_id": item_id}


@app.put("/api/radar/settings")
def api_update_radar_settings(payload: RadarSettingsUpdate) -> Dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True)
    cfg = save_radar_config(updates)
    return {"status": "saved", "config": cfg}


@app.post("/api/radar/test-alert")
async def api_test_radar_alert() -> Dict[str, Any]:
    return await send_alert(
        title="🦊 Vulpix Vault Radar — Test Alert",
        message="Your Auction Radar alerts are connected and ready for the last 10 minutes of your next eBay snipe!",
        url="https://www.ebay.com/sch/i.html?_nkw=Vulpix+Pokemon+Card&_sop=1",
        priority=6,
    )


@app.post("/api/radar/queries")
def api_add_radar_query(payload: RadarQueryCreate) -> Dict[str, Any]:
    q = payload.query.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Search query cannot be empty.")
    bf = payload.buying_filter.upper() if payload.buying_filter.upper() in ("ALL", "AUCTION", "FIXED_PRICE") else "ALL"
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO radar_queries (query, label, buying_filter, enabled) VALUES (?, ?, ?, 1);",
            (q, payload.label.strip() or q, bf),
        )
        qid = cur.lastrowid
    return {"status": "created", "id": qid}


@app.put("/api/radar/queries/{query_id}")
def api_toggle_radar_query(query_id: int, payload: RadarQueryToggle) -> Dict[str, Any]:
    with get_conn() as conn:
        conn.execute("UPDATE radar_queries SET enabled = ? WHERE id = ?;", (1 if payload.enabled else 0, query_id))
    return {"status": "updated", "id": query_id, "enabled": payload.enabled}


@app.delete("/api/radar/queries/{query_id}")
def api_delete_radar_query(query_id: int) -> Dict[str, Any]:
    with get_conn() as conn:
        conn.execute("DELETE FROM radar_queries WHERE id = ?;", (query_id,))
    return {"deleted": True, "id": query_id}


# =============================================================
# CSV Exports (Wantlist for Card Shows & Vault Backup)
# =============================================================

@app.get("/api/export/wantlist.csv")
def api_export_wantlist():
    data = api_get_catalog()
    missing = [c for c in data["cards"] if not c["is_owned"]]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Year", "Language", "Card Name", "Set", "Number", "Edition", "Error", "Raw ($)", "PSA 10 ($)", "Price Source"])
    for c in missing:
        w.writerow([
            c["release_year"], c["language"], c["card_name"], c["set_name"], c["card_number"],
            c["edition"], c["error_description"] if c["is_error"] else "",
            c["price_raw"] or "", c["price_grade10"] or "", c["price_source"] or "Unpriced",
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="vulpix_wantlist.csv"'},
    )


@app.get("/api/export/vault.csv")
def api_export_vault():
    data = api_get_vault()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Card Name", "Set", "Number", "Language", "Edition", "Grader", "Grade", "Grade Label", "Cert #", "Paid ($)", "Market ($)", "Date", "Notes"])
    for it in data["items"]:
        w.writerow([
            it["card_name"], it["set_name"], it["card_number"], it["language"], it["edition"],
            it["grading_company"], it["grade"], it["grade_label"], it["cert_number"],
            it["purchase_price"], it["market_value"] or "", it["purchase_date"], it["notes"],
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="vulpix_vault_backup.csv"'},
    )


# =============================================================
# Static Assets & SPA Entrypoint
# =============================================================

frontend_dir = os.path.join(get_project_root(), "frontend")
static_cards_dir = get_static_cards_dir()
cached_cards_dir = get_cached_cards_dir()

if os.path.isdir(static_cards_dir):
    app.mount("/static/cards", StaticFiles(directory=static_cards_dir), name="static_cards")
if os.path.isdir(cached_cards_dir):
    app.mount("/cached-cards", StaticFiles(directory=cached_cards_dir), name="cached_cards")
if os.path.isdir(frontend_dir):
    app.mount("/assets", StaticFiles(directory=frontend_dir), name="frontend_assets")


@app.get("/")
def serve_index():
    index_path = os.path.join(frontend_dir, "index.html")
    if not os.path.isfile(index_path):
        raise HTTPException(status_code=404, detail="Frontend index.html not found")
    return FileResponse(index_path)
