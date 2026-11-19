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
from backend.error_annotations import get_visual_callouts
from backend.migration import match_catalog_key, migrate_legacy_vault_if_needed
from backend.models import CustomCardCreate, PriceOverrideIn, SyncJobRequest, VaultItemCreate, VaultItemUpdate
from backend.pricing import refresh_catalog_prices_batch, refresh_single_card_price

# In-memory job status registry for non-blocking background sync tasks
SYNC_STATE: Dict[str, Dict[str, Any]] = {
    "tcgdex": {"running": False, "progress": 0, "total": 0, "message": "Idle", "result": None, "finished_at": None},
    "prices": {"running": False, "progress": 0, "total": 0, "message": "Idle", "result": None, "finished_at": None},
    "cache_images": {"running": False, "progress": 0, "total": 0, "message": "Idle", "result": None, "finished_at": None},
    "pokecottage": {"running": False, "progress": 0, "total": 0, "message": "Idle", "result": None, "finished_at": None},
}


def bootstrap_database() -> None:
    """Runs once at server startup: init schema, seed canonical catalog, translate/dedupe, migrate legacy vault once."""
    init_schema()
    seed_canonical_catalog()
    translate_and_dedupe_existing_catalog()
    migrate_legacy_vault_if_needed()


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap_database()
    yield


app = FastAPI(title="The Vulpix Vault API", version="2.0.0", lifespan=lifespan)

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
        "version": "2.0.0",
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
