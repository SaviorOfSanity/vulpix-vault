"""
Phase 2: Official eBay Browse API Radar, Smart Listing Parser, Master Set Auto-Matcher,
Deal Tier Evaluator, and Background Alert Runner.
- Zero fragile HTML scraping (uses official eBay OAuth2 + Buy Browse API).
- Also supports manual URL/item tracking immediately even before eBay API keys are added.
"""

from __future__ import annotations

import base64
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import httpx

from backend.db import get_conn, get_setting, set_setting
from backend.notifier import get_alert_config, send_alert

EBAY_TCG_SINGLE_CATEGORY = "183454"  # Collectible Card Games -> CCG Individual Cards

DEFAULT_RADAR_QUERIES: List[Tuple[str, str, str]] = [
    ("Vulpix PSA 10", "PSA 10 Slabs", "ALL"),
    ("Vulpix CGC 10", "CGC 10 & Pristine", "ALL"),
    ("Vulpix 1st Edition Pokemon", "Vintage 1st Edition", "ALL"),
    ("Vulpix Base Set Shadowless OR Error", "Base Set & Errors", "ALL"),
    ("Brock's Vulpix OR Blaine's Vulpix", "Gym Heroes / Challenge", "ALL"),
    ("Alolan Vulpix Pokemon", "Alolan Vulpix", "ALL"),
    ("Vulpix Master Ball OR Poncho Pikachu", "Japanese 151 & Ponchos", "ALL"),
    ("Vulpix Pokemon Card", "Ending Soonest Auctions", "AUCTION"),
]

# In-memory OAuth token cache: (env, client_id) -> (access_token, expires_epoch)
_TOKEN_CACHE: Dict[Tuple[str, str], Tuple[str, float]] = {}

JUNK_KEYWORDS = (
    "proxy", "orica", "custom card", "fan art", "metal card", "gold metal",
    "repack", "mystery pack", "mystery box", "booster box", "booster pack",
    "empty tin", "empty box", "plush", "plushie", "figure", "figurine", "funko",
    "sticker", "decal", "sleeve", "sleeves", "deck box", "playmat", "coin",
    "enamel pin", "binder", "portfolio", "code card", "ptcg live", "tcg live",
    "digital code", "choose your", "pick your", "you pick", "complete your set",
    "lot of ", "card lot", "bulk lot", "evolution line", "evolutions lot",
    "keychain", "t-shirt", "shirt", "hat", "mug", "poster", "art print",
)

VULPIX_TITLE_TOKENS = (
    "vulpix", "goupix", "ロコン", "식스테일", "六尾", "โรคอน",
)


def seed_default_radar_queries(db_path: Optional[str] = None) -> None:
    """Seeds default Vulpix eBay Radar search queries once if table is empty."""
    with get_conn(db_path) as conn:
        cnt = conn.execute("SELECT COUNT(*) FROM radar_queries;").fetchone()[0]
        if cnt == 0:
            conn.executemany(
                "INSERT OR IGNORE INTO radar_queries (query, label, buying_filter, enabled) VALUES (?, ?, ?, 1);",
                DEFAULT_RADAR_QUERIES,
            )


def get_radar_config(db_path: Optional[str] = None, mask_secrets: bool = False) -> Dict[str, Any]:
    """Reads Radar & Alert settings from SQLite app_settings with clean .env fallback."""
    client_id = (get_setting("ebay_client_id", "", db_path) or os.getenv("EBAY_CLIENT_ID", "")).strip()
    client_secret = (get_setting("ebay_client_secret", "", db_path) or os.getenv("EBAY_CLIENT_SECRET", "")).strip()
    ebay_env = (get_setting("ebay_env", "", db_path) or os.getenv("EBAY_ENV", "production")).strip().lower()
    if ebay_env not in ("production", "sandbox"):
        ebay_env = "production"
    marketplace = (get_setting("ebay_marketplace", "", db_path) or os.getenv("EBAY_MARKETPLACE", "EBAY_US")).strip() or "EBAY_US"

    auto_enabled_raw = get_setting("auto_scan_enabled", "1", db_path)
    auto_enabled = auto_enabled_raw not in ("0", "false", "False", "")
    try:
        interval_min = max(5, int(get_setting("auto_scan_interval_min", "15", db_path) or 15))
    except ValueError:
        interval_min = 15
    try:
        min_disc = int(get_setting("alert_min_discount_pct", "15", db_path) or 15)
    except ValueError:
        min_disc = 15
    try:
        ending_min = max(5, int(get_setting("alert_ending_soon_min", "20", db_path) or 20))
    except ValueError:
        ending_min = 20
    needed_only = get_setting("alert_needed_only", "1", db_path) not in ("0", "false", "False")

    alert_cfg = get_alert_config(db_path)

    def _mask(val: str) -> str:
        if not val:
            return ""
        if len(val) <= 8:
            return "••••"
        return f"{val[:4]}••••{val[-4:]}"

    return {
        "ebay_configured": bool(client_id and client_secret),
        "ebay_client_id": _mask(client_id) if mask_secrets else client_id,
        "ebay_client_secret_set": bool(client_secret),
        "ebay_client_secret": "" if mask_secrets else client_secret,
        "ebay_env": ebay_env,
        "ebay_marketplace": marketplace,
        "auto_scan_enabled": auto_enabled,
        "auto_scan_interval_min": interval_min,
        "alert_min_discount_pct": min_disc,
        "alert_ending_soon_min": ending_min,
        "alert_needed_only": needed_only,
        "gotify_url": alert_cfg["gotify_url"],
        "gotify_token_set": bool(alert_cfg["gotify_token"]),
        "gotify_token": "" if mask_secrets else alert_cfg["gotify_token"],
        "discord_webhook_set": bool(alert_cfg["discord_webhook_url"]),
        "discord_webhook_url": _mask(alert_cfg["discord_webhook_url"]) if mask_secrets else alert_cfg["discord_webhook_url"],
        "ntfy_url": alert_cfg["ntfy_url"],
        "last_scan_at": get_setting("radar_last_scan_at", "", db_path),
        "last_scan_summary": get_setting("radar_last_scan_summary", "", db_path),
    }


def save_radar_config(updates: Dict[str, Any], db_path: Optional[str] = None) -> Dict[str, Any]:
    """Persists non-empty Radar & Alert config fields safely into app_settings."""
    secret_fields = {"ebay_client_id", "ebay_client_secret", "gotify_token", "discord_webhook_url"}
    for key, val in updates.items():
        if val is None:
            continue
        if isinstance(val, bool):
            set_setting(key, "1" if val else "0", db_path)
        elif key in secret_fields:
            s = str(val).strip()
            # Never overwrite real secret with masked placeholder string from UI
            if "••••" in s:
                continue
            if s == "" and key in ("ebay_client_secret", "gotify_token"):
                continue
            set_setting(key, s, db_path)
        else:
            set_setting(key, str(val).strip(), db_path)
    _TOKEN_CACHE.clear()
    return get_radar_config(db_path, mask_secrets=True)


# =============================================================
# Listing Filtering, Attribute Parsing & Master Set Auto-Matcher
# =============================================================

def is_junk_listing(title: str) -> bool:
    """Filters out proxies, repacks, lots, toys, sleeves, and non-Vulpix noise."""
    t = (title or "").strip()
    low = t.lower()
    if not t:
        return True
    if any(bad in low for bad in JUNK_KEYWORDS):
        return True
    # Must explicitly mention Vulpix (or localized Vulpix name)
    if not any(tok in low or tok in t for tok in VULPIX_TITLE_TOKENS):
        return True
    # Reject listings whose primary subject is Ninetales (unless it's clearly a Vulpix card)
    if "ninetales" in low and not re.search(r"\bvulpix\b", low.split("ninetales")[0]):
        # Allow e.g. "Vulpix & Ninetales" only if Vulpix leads; drop "Ninetales (evolves from Vulpix)"
        return True
    return False


def extract_ebay_item_id(url_or_id: str) -> str:
    """Extracts the numeric legacy eBay item ID from a full URL, Browse API ID, or raw ID."""
    s = (url_or_id or "").strip()
    m_v1 = re.search(r"v1\|(\d{8,15})\|", s)
    if m_v1:
        return m_v1.group(1)
    m_itm = re.search(r"/itm/(?:[^/?#]+/)?(\d{8,15})", s)
    if m_itm:
        return m_itm.group(1)
    m_q = re.search(r"[?&]item=(\d{8,15})", s)
    if m_q:
        return m_q.group(1)
    if re.fullmatch(r"\d{8,15}", s):
        return s
    return ""


def parse_listing_attributes(title: str) -> Dict[str, Any]:
    """Parses grader, numerical grade, language, subject, card numbers, and print variants from an eBay title."""
    t = (title or "").strip()
    low = t.lower()

    # 1. Grader & Grade
    grader = "RAW"
    grade = 0.0
    grade_label = "Raw Single"

    grader_match = re.search(r"\b(PSA|CGC|BGS|BECKETT|ARS|ACE|SGC)\b[\s\-:#]*(?:GEM\s*MINT\s*|PRISTINE\s*|BLACK\s*LABEL\s*|MINT\s*)?(10(?:\.0)?|9\.5|9(?:\.0)?|8\.5|8(?:\.0)?|7\.5|7(?:\.0)?|6|5|4|3|2|1)\b", t, re.I)
    if not grader_match:
        # Also match reversed order like "Gem Mint 10 PSA" or "Pristine 10 CGC"
        grader_match = re.search(r"\b(10(?:\.0)?|9\.5|9(?:\.0)?|8\.5|8(?:\.0)?)\s+(PSA|CGC|BGS|BECKETT|ARS|ACE|SGC)\b", t, re.I)
        if grader_match:
            g_str, comp_raw = grader_match.group(1), grader_match.group(2)
        else:
            g_str, comp_raw = None, None
    else:
        comp_raw, g_str = grader_match.group(1), grader_match.group(2)

    if comp_raw and g_str:
        grader = "BGS" if comp_raw.upper() == "BECKETT" else comp_raw.upper()
        grade = float(g_str)
        if grade >= 10.0:
            if "black label" in low:
                grade_label = "Black Label 10"
            elif "pristine" in low:
                grade_label = "Pristine 10"
            else:
                grade_label = "Gem Mint 10"
        elif grade >= 9.5:
            grade_label = "Gem Mint 9.5"
        elif grade >= 9.0:
            grade_label = "Mint 9"
        elif grade >= 8.0:
            grade_label = f"NM-MT {int(grade) if grade.is_integer() else grade}"
        else:
            grade_label = f"Grade {int(grade) if grade.is_integer() else grade}"

    # 2. Language detection
    language = "English"
    if any(k in low for k in ("japanese", " jpn", "jpn ", " jp ", "pokemon jp", "s-p ", "sm-p", "sv-p", "xy-p", "m1l", "sv2a", "s11a", "cp6", "poncho", "no rarity")) or "ロコン" in t or "ポンチョ" in t:
        language = "Japanese"
    elif any(k in low for k in ("s-cn", "s-chinese", "simplified chinese", "chinese 151", "gem pack", "c-bb", "scn")):
        language = "S. Chinese"
    elif any(k in low for k in ("t-cn", "traditional chinese", "taiwan")):
        language = "T. Chinese"
    elif "chinese" in low or "六尾" in t:
        language = "S. Chinese"
    elif any(k in low for k in ("korean", " kr ")) or "식스테일" in t:
        language = "Korean"
    elif any(k in low for k in ("french", "goupix", "français", "francais", " fr ")):
        language = "French"
    elif any(k in low for k in ("german", "deutsch", "rockos", "pyros", "grundset")):
        language = "German"
    elif any(k in low for k in ("italian", "italiano", "di alola", "di brock")):
        language = "Italian"
    elif any(k in low for k in ("spanish", "español", "espanol", "de alola", "v-astro")):
        language = "Spanish"
    elif any(k in low for k in ("portuguese", "português", "coleção")):
        language = "Portuguese"
    elif any(k in low for k in ("dutch", "nederlands")):
        language = "Dutch"
    elif any(k in low for k in ("indonesian", "bahasa")):
        language = "Indonesian"
    elif any(k in low for k in ("thai",)) or "โรคอน" in t:
        language = "Thai"
    elif any(k in low for k in ("polish", "polski")):
        language = "Polish"

    # 3. Subject (Vulpix form / trainer)
    if "poncho" in low or "ポンチョ" in t:
        subject = "poncho_alolan" if ("alolan" in low or "alola" in low or "037" in low or "アローラ" in t) else "poncho_vulpix"
    elif any(k in low for k in ("brock", "pierre", "rocko")) or "タケシ" in t:
        subject = "brock"
    elif any(k in low for k in ("blaine", "auguste", "pyro")) or "カツラ" in t:
        subject = "blaine"
    elif any(k in low for k in ("alolan", "alola")) or any(k in t for k in ("アローラ", "알로라", "阿羅拉", "阿罗拉", "อโลลา")):
        if "vstar" in low or "v-star" in low or "v-astro" in low:
            subject = "alolan_vstar"
        elif re.search(r"\bv\b", low):
            subject = "alolan_v"
        else:
            subject = "alolan"
    else:
        subject = "vulpix"

    # 4. Card numbers (explicit fractions & promo codes & standalone #num)
    fractions: List[str] = []
    base_nums: List[str] = []
    for m in re.finditer(r"\b([A-Za-z]{0,3}\d{1,3})\s*/\s*([A-Za-z0-9\-]{2,6})\b", t):
        left, right = m.group(1), m.group(2)
        fractions.append(f"{left.lstrip('0') or '0'}/{right.lstrip('0') or '0'}".lower())
        b = left.lstrip("0") or "0"
        if b.lower() not in base_nums:
            base_nums.append(b.lower())

    for m in re.finditer(r"(?:#|no\.?\s*)([A-Za-z]{0,3}\d{1,3})\b", t, re.I):
        b = m.group(1).lstrip("0") or "0"
        if b.lower() not in base_nums:
            base_nums.append(b.lower())

    # 5. Variant signals
    variants: Set[str] = set()
    if "blue dot" in low:
        variants.add("blue_dot")
    if "water symbol" in low:
        variants.add("water_symbol")
    if "ink error" in low:
        variants.add("ink_error")
    if "grey stamp" in low or "gray stamp" in low:
        variants.add("grey_stamp")
    if "no rarity" in low:
        variants.add("no_rarity")
    if "w stamp" in low or "w-stamp" in low or "wizards stamp" in low or "topdeck" in low:
        variants.add("w_stamp")
    if "4th print" in low or "fourth print" in low or "1999-2000" in low or "50 hp" in low:
        variants.add("4th_print")
    if "1st ed" in low or "first ed" in low or "1st edition" in low:
        variants.add("1st_edition")
    if "shadowless" in low:
        variants.add("shadowless")
    if "master ball" in low or "masterball" in low:
        variants.add("master_ball")
    if "poke ball" in low or "pokeball" in low or "poké ball" in low:
        variants.add("poke_ball")
    if "reverse holo" in low or "rev holo" in low or "reverse foil" in low:
        variants.add("reverse_holo")
    elif "holo" in low and "non-holo" not in low and "non holo" not in low:
        variants.add("holo")
    if "rainbow" in low or "hyper rare" in low or "secret" in low:
        variants.add("rainbow")
    if "art rare" in low or " ar " in f" {low} " or "illustration rare" in low:
        variants.add("art_rare")
    if "snowflake" in low or "holiday calendar" in low or "advent" in low:
        variants.add("snowflake")
    if "play! pokemon" in low or "play pokemon" in low or "prize pack" in low:
        variants.add("play_pokemon")
    if "build-a-bear" in low or "build a bear" in low:
        variants.add("build_a_bear")
    if "toys r us" in low:
        variants.add("toys_r_us")
    if "staff" in low:
        variants.add("staff")
    if "stamped" in low or "stamp" in low:
        variants.add("stamp")

    return {
        "grader": grader,
        "grade": grade,
        "grade_label": grade_label,
        "language": language,
        "subject": subject,
        "fractions": fractions,
        "base_nums": base_nums,
        "variants": variants,
    }


def _card_subject(card: Dict[str, Any]) -> str:
    n = (card.get("card_name") or "").lower()
    if "poncho" in n:
        return "poncho_alolan" if "alolan" in n else "poncho_vulpix"
    if "brock" in n:
        return "brock"
    if "blaine" in n:
        return "blaine"
    if "alolan" in n:
        if "vstar" in n:
            return "alolan_vstar"
        if re.search(r"\bv\b", n):
            return "alolan_v"
        return "alolan"
    return "vulpix"


def match_listing_to_catalog(
    title: str,
    attrs: Dict[str, Any],
    catalog_cards: List[Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], int]:
    """
    Scores all Master Set cards against a parsed eBay listing.
    Returns (best_catalog_card, confidence_0_to_100) or (None, 0) if uncertain.
    """
    low = (title or "").lower()
    best_card: Optional[Dict[str, Any]] = None
    best_score = 0

    for card in catalog_cards:
        score = 0
        # 1. Subject check (hard gate)
        c_subj = _card_subject(card)
        if c_subj != attrs["subject"]:
            continue
        score += 20

        # 2. Language check
        c_lang = card.get("language") or "English"
        if c_lang == attrs["language"]:
            score += 22
        else:
            score -= 45
            continue

        # 3. Card number & fraction check
        c_num_raw = (card.get("card_number") or "").lower().strip()
        c_base = (card.get("base_number") or "").lower().strip()
        c_norm_frac = ""
        if "/" in c_num_raw:
            p1, p2 = c_num_raw.split("/", 1)
            c_norm_frac = f"{p1.lstrip('0') or '0'}/{p2.lstrip('0') or '0'}"

        num_matched = False
        if c_norm_frac and c_norm_frac in attrs["fractions"]:
            score += 38
            num_matched = True
        elif c_base and c_base in attrs["base_nums"]:
            score += 26
            num_matched = True
        elif attrs["fractions"] and c_norm_frac and c_norm_frac not in attrs["fractions"]:
            # Listing explicitly gave a DIFFERENT fraction like 68/102 vs 81/101
            score -= 35

        # 4. Set name & year match
        c_set = (card.get("set_name") or "").lower()
        c_native_set = (card.get("native_set_name") or "").lower()
        c_set_id = (card.get("set_id") or "").lower()
        c_year = str(card.get("release_year") or "")

        set_words = [
            w for w in re.findall(r"[a-z0-9]+", c_set)
            if len(w) > 2 and w not in ("the", "and", "set", "pack", "pokemon", "pok", "mon", "card", "base", "promo", "promos")
        ]
        # Special handling for Base Set vs Base Set 2
        if c_set == "base set":
            if "base set 2" in low or "base 2" in low:
                score -= 50
            elif "base set" in low or ("1999" in low and ("68/102" in low or "shadowless" in low or "hp 50" in low)):
                score += 28
        elif c_set == "base set 2":
            if "base set 2" in low or "base 2" in low or "99/130" in low:
                score += 30
            elif "base set" in low:
                score -= 40
        else:
            hits = sum(1 for w in set_words if w in low)
            if set_words and hits == len(set_words):
                score += 28
            elif hits >= 1:
                score += 15
            elif c_native_set and c_native_set in low:
                score += 28
            elif c_set_id and len(c_set_id) >= 3 and re.search(rf"\b{re.escape(c_set_id)}\b", low):
                score += 22

        if c_year and c_year in low:
            score += 6

        # 5. Variant / Error precision scoring
        vk = (card.get("variant_key") or "unlimited").lower()
        ed_low = (card.get("edition") or "").lower()
        vs = attrs["variants"]

        if "blue dot" in ed_low:
            score += 35 if "blue_dot" in vs else -45
        elif "water symbol" in ed_low:
            score += 35 if "water_symbol" in vs else -45
        elif "ink error" in ed_low:
            score += 35 if "ink_error" in vs else -45
        elif "grey stamp" in ed_low:
            score += 35 if "grey_stamp" in vs else -45
        elif vk == "no_rarity":
            score += 35 if "no_rarity" in vs else -40
        elif vk == "w_stamp":
            score += 35 if "w_stamp" in vs else -40
        elif vk == "4th_print":
            score += 30 if "4th_print" in vs else -35
        elif vk == "master_ball":
            score += 32 if "master_ball" in vs else -40
        elif vk == "poke_ball":
            if "master_ball" in vs:
                score -= 40
            elif "poke_ball" in vs:
                score += 28
            else:
                score -= 20
        elif vk == "1st_edition":
            score += 28 if "1st_edition" in vs else -35
        elif vk == "shadowless":
            if "1st_edition" in vs:
                score -= 35
            elif "shadowless" in vs:
                score += 28
            else:
                score -= 30
        elif vk == "reverse_holo":
            score += 22 if "reverse_holo" in vs else -22
        elif vk == "rainbow":
            score += 24 if "rainbow" in vs else -25
        elif vk == "art_rare":
            score += 24 if ("art_rare" in vs or num_matched) else -10
        elif vk == "stamp":
            if "snowflake" in ed_low:
                score += 28 if "snowflake" in vs else -30
            elif "play" in ed_low:
                score += 28 if "play_pokemon" in vs else -30
            elif "build-a-bear" in ed_low:
                score += 28 if "build_a_bear" in vs else -30
            elif "toys r us" in ed_low:
                score += 28 if "toys_r_us" in vs else -30
            elif "stamp" in vs or "reverse_holo" in vs:
                score += 14
            else:
                score -= 18
        elif vk == "unlimited":
            # Penalize matching Unlimited if listing explicitly claims a rare print
            rare_claims = {"1st_edition", "shadowless", "4th_print", "w_stamp", "no_rarity", "master_ball", "poke_ball", "reverse_holo", "blue_dot", "water_symbol", "ink_error", "grey_stamp"}
            if vs & rare_claims:
                score -= 30
            else:
                score += 10

        if score > best_score:
            best_score = score
            best_card = card

    if best_card and best_score >= 48:
        confidence = min(99, max(45, int(best_score)))
        return best_card, confidence
    return None, 0


def evaluate_deal(
    total_cost: float,
    grader: str,
    grade: float,
    grade_label: str,
    matched_card: Optional[Dict[str, Any]],
) -> Tuple[Optional[float], str, Optional[float]]:
    """Computes (market_comp, deal_tier, discount_pct) using real catalog comps only."""
    if not matched_card:
        return None, "UNPRICED", None

    p_raw = matched_card.get("price_raw")
    p_g9 = matched_card.get("price_grade9")
    p_g10 = matched_card.get("price_grade10")

    comp: Optional[float] = None
    if grader == "RAW" or grade <= 0:
        comp = float(p_raw) if p_raw is not None else None
    elif grade >= 10.0 and p_g10 is not None:
        lbl = (grade_label or "").lower()
        mult = 2.2 if "black label" in lbl else (1.35 if "pristine" in lbl else 1.0)
        comp = round(float(p_g10) * mult, 2)
    elif grade >= 9.0 and p_g9 is not None:
        comp = float(p_g9)
    elif p_raw is not None and grade < 8.5:
        comp = float(p_raw)

    if comp is None or comp <= 0:
        return None, "UNPRICED", None

    discount_pct = round(((comp - total_cost) / comp) * 100, 1)
    if discount_pct >= 30.0:
        tier = "SNIPE"
    elif discount_pct >= 15.0:
        tier = "GOOD"
    elif discount_pct >= 0.0:
        tier = "FAIR"
    else:
        tier = "OVERPRICED"
    return comp, tier, discount_pct


# =============================================================
# Official eBay Browse API Client
# =============================================================

def _ebay_api_base(env: str) -> str:
    return "https://api.sandbox.ebay.com" if env == "sandbox" else "https://api.ebay.com"


async def get_ebay_access_token(client: httpx.AsyncClient, cfg: Dict[str, Any]) -> str:
    """Fetches & caches an eBay OAuth2 application token using Client Credentials Grant."""
    client_id = cfg["ebay_client_id"]
    client_secret = cfg["ebay_client_secret"]
    env = cfg["ebay_env"]
    if not client_id or not client_secret:
        raise ValueError("eBay API credentials are not configured yet.")

    cache_key = (env, client_id)
    cached = _TOKEN_CACHE.get(cache_key)
    if cached and cached[1] > time.time() + 60:
        return cached[0]

    basic = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    token_url = f"{_ebay_api_base(env)}/identity/v1/oauth2/token"
    resp = await client.post(
        token_url,
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "client_credentials",
            "scope": "https://api.ebay.com/oauth/api_scope",
        },
    )
    if resp.status_code != 200:
        raise ValueError(f"eBay OAuth failed ({resp.status_code}): {resp.text[:220]}")
    body = resp.json()
    token = body["access_token"]
    expires_in = int(body.get("expires_in") or 7200)
    _TOKEN_CACHE[cache_key] = (token, time.time() + expires_in)
    return token


def _parse_browse_item_summary(item: Dict[str, Any], source_query: str = "") -> Optional[Dict[str, Any]]:
    """Normalizes an eBay Browse API itemSummary or full Item payload into our DB schema."""
    title = str(item.get("title") or "").strip()
    if not title:
        return None

    item_id = str(item.get("itemId") or "").strip()
    if not item_id:
        legacy = str(item.get("legacyItemId") or "").strip()
        item_id = f"v1|{legacy}|0" if legacy else ""
    if not item_id:
        return None

    options = [str(o).upper() for o in (item.get("buyingOptions") or [])]
    if "AUCTION" in options and "FIXED_PRICE" in options:
        buying_opt = "AUCTION_BIN"
    elif "AUCTION" in options:
        buying_opt = "AUCTION"
    else:
        buying_opt = "FIXED_PRICE"

    # For auctions, prefer currentBidPrice; otherwise price
    price_obj = item.get("currentBidPrice") if ("AUCTION" in options and item.get("currentBidPrice")) else item.get("price")
    try:
        current_price = float((price_obj or {}).get("value") or 0.0)
    except (TypeError, ValueError):
        current_price = 0.0

    shipping_cost = 0.0
    ship_opts = item.get("shippingOptions") or []
    if ship_opts and isinstance(ship_opts, list):
        sc = (ship_opts[0].get("shippingCost") or {}).get("value")
        try:
            shipping_cost = float(sc or 0.0)
        except (TypeError, ValueError):
            shipping_cost = 0.0

    img = ""
    if isinstance(item.get("image"), dict):
        img = str(item["image"].get("imageUrl") or "")
    elif isinstance(item.get("thumbnailImages"), list) and item["thumbnailImages"]:
        img = str(item["thumbnailImages"][0].get("imageUrl") or "")

    seller = item.get("seller") or {}
    fb_pct = None
    try:
        if seller.get("feedbackPercentage") is not None:
            fb_pct = float(seller["feedbackPercentage"])
    except (TypeError, ValueError):
        fb_pct = None

    return {
        "ebay_item_id": item_id,
        "title": title,
        "url": str(item.get("itemWebUrl") or f"https://www.ebay.com/itm/{extract_ebay_item_id(item_id)}"),
        "image_url": img,
        "buying_option": buying_opt,
        "current_price": round(current_price, 2),
        "shipping_cost": round(shipping_cost, 2),
        "total_cost": round(current_price + shipping_cost, 2),
        "bid_count": int(item.get("bidCount") or 0),
        "end_time": str(item.get("itemEndDate") or ""),
        "seller_username": str(seller.get("username") or ""),
        "seller_feedback_pct": fb_pct,
        "condition": str(item.get("condition") or ""),
        "source_query": source_query,
    }


def _upsert_radar_listing(
    cursor,
    raw_item: Dict[str, Any],
    catalog_cards: List[Dict[str, Any]],
    force_watched: Optional[bool] = None,
    override_catalog_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Parses, auto-matches, evaluates deal tier, and upserts a listing preserving user watch/dismiss state."""
    attrs = parse_listing_attributes(raw_item["title"])

    existing = cursor.execute(
        "SELECT catalog_key, match_confidence, is_watched, is_dismissed, alert_sent FROM ebay_listings WHERE ebay_item_id = ?;",
        (raw_item["ebay_item_id"],),
    ).fetchone()

    cat_by_key = {c["catalog_key"]: c for c in catalog_cards}
    matched_card: Optional[Dict[str, Any]] = None
    confidence = 0

    if override_catalog_key and override_catalog_key in cat_by_key:
        matched_card = cat_by_key[override_catalog_key]
        confidence = 100
    elif existing and existing["catalog_key"] and existing["match_confidence"] == 100 and existing["catalog_key"] in cat_by_key:
        # Preserve explicit manual card link chosen by the user
        matched_card = cat_by_key[existing["catalog_key"]]
        confidence = 100
    else:
        matched_card, confidence = match_listing_to_catalog(raw_item["title"], attrs, catalog_cards)

    comp, tier, disc = evaluate_deal(
        raw_item["total_cost"],
        attrs["grader"],
        attrs["grade"],
        attrs["grade_label"],
        matched_card,
    )

    is_watched = 1 if force_watched else (int(existing["is_watched"]) if existing else 0)
    is_dismissed = 0 if force_watched else (int(existing["is_dismissed"]) if existing else 0)
    alert_sent = int(existing["alert_sent"]) if existing else 0

    record = {
        **raw_item,
        "detected_grader": attrs["grader"],
        "detected_grade": attrs["grade"],
        "detected_grade_label": attrs["grade_label"],
        "catalog_key": matched_card["catalog_key"] if matched_card else None,
        "match_confidence": confidence,
        "market_comp": comp,
        "deal_tier": tier,
        "discount_pct": disc,
        "is_watched": is_watched,
        "is_dismissed": is_dismissed,
        "alert_sent": alert_sent,
    }

    cursor.execute("""
        INSERT INTO ebay_listings (
            ebay_item_id, title, url, image_url, buying_option,
            current_price, shipping_cost, total_cost, bid_count, end_time,
            seller_username, seller_feedback_pct, condition,
            detected_grader, detected_grade, detected_grade_label,
            catalog_key, match_confidence, market_comp, deal_tier, discount_pct,
            is_watched, is_dismissed, alert_sent, is_active, source_query, last_seen_at
        ) VALUES (
            :ebay_item_id, :title, :url, :image_url, :buying_option,
            :current_price, :shipping_cost, :total_cost, :bid_count, :end_time,
            :seller_username, :seller_feedback_pct, :condition,
            :detected_grader, :detected_grade, :detected_grade_label,
            :catalog_key, :match_confidence, :market_comp, :deal_tier, :discount_pct,
            :is_watched, :is_dismissed, :alert_sent, 1, :source_query, CURRENT_TIMESTAMP
        )
        ON CONFLICT(ebay_item_id) DO UPDATE SET
            title = excluded.title,
            url = excluded.url,
            image_url = CASE WHEN excluded.image_url != '' THEN excluded.image_url ELSE ebay_listings.image_url END,
            buying_option = excluded.buying_option,
            current_price = excluded.current_price,
            shipping_cost = excluded.shipping_cost,
            total_cost = excluded.total_cost,
            bid_count = excluded.bid_count,
            end_time = CASE WHEN excluded.end_time != '' THEN excluded.end_time ELSE ebay_listings.end_time END,
            seller_username = CASE WHEN excluded.seller_username != '' THEN excluded.seller_username ELSE ebay_listings.seller_username END,
            seller_feedback_pct = COALESCE(excluded.seller_feedback_pct, ebay_listings.seller_feedback_pct),
            detected_grader = excluded.detected_grader,
            detected_grade = excluded.detected_grade,
            detected_grade_label = excluded.detected_grade_label,
            catalog_key = excluded.catalog_key,
            match_confidence = excluded.match_confidence,
            market_comp = excluded.market_comp,
            deal_tier = excluded.deal_tier,
            discount_pct = excluded.discount_pct,
            is_watched = MAX(ebay_listings.is_watched, excluded.is_watched),
            is_active = 1,
            last_seen_at = CURRENT_TIMESTAMP;
    """, record)
    return record


def expire_ended_listings(db_path: Optional[str] = None) -> int:
    """Marks auctions whose end_time has passed as inactive."""
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with get_conn(db_path) as conn:
        cur = conn.execute("""
            UPDATE ebay_listings
            SET is_active = 0
            WHERE is_active = 1 AND end_time != '' AND end_time < ?;
        """, (now_iso,))
        return cur.rowcount


async def track_single_ebay_url(
    url: str,
    *,
    title: str = "",
    current_price: Optional[float] = None,
    shipping_cost: Optional[float] = None,
    end_time: str = "",
    minutes_remaining: Optional[int] = None,
    buying_option: str = "AUCTION",
    catalog_key: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Adds any eBay listing to your Watchlist.
    - If eBay Browse API keys are configured, fetches live title, photo, bid, shipping, and exact end time automatically!
    - Works even WITHOUT API keys when you supply title/price/minutes remaining.
    """
    legacy_id = extract_ebay_item_id(url)
    item_id = f"v1|{legacy_id}|0" if legacy_id else f"manual|{abs(hash(url)) % 10**10}"
    clean_url = url.strip() if url.strip().startswith("http") else (f"https://www.ebay.com/itm/{legacy_id}" if legacy_id else url.strip())

    raw_item: Optional[Dict[str, Any]] = None
    cfg = get_radar_config(db_path, mask_secrets=False)

    if cfg["ebay_configured"] and legacy_id:
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                token = await get_ebay_access_token(client, cfg)
                headers = {
                    "Authorization": f"Bearer {token}",
                    "X-EBAY-C-MARKETPLACE-ID": cfg["ebay_marketplace"],
                }
                resp = await client.get(f"{_ebay_api_base(cfg['ebay_env'])}/buy/browse/v1/item/v1|{legacy_id}|0", headers=headers)
                if resp.status_code != 200:
                    resp = await client.get(
                        f"{_ebay_api_base(cfg['ebay_env'])}/buy/browse/v1/item/get_item_by_legacy_id",
                        params={"legacy_item_id": legacy_id},
                        headers=headers,
                    )
                if resp.status_code == 200:
                    raw_item = _parse_browse_item_summary(resp.json(), source_query="watched_url")
        except Exception:
            raw_item = None

    if not raw_item:
        if not title.strip():
            if cfg["ebay_configured"]:
                raise ValueError("Could not fetch that item from eBay API — enter a Listing Title manually to track it.")
            raise ValueError("Enter a Listing Title (or connect free eBay API keys in Radar Setup to auto-fill from URL).")
        resolved_end = end_time.strip()
        if not resolved_end and minutes_remaining and minutes_remaining > 0:
            resolved_end = (datetime.now(timezone.utc) + timedelta(minutes=int(minutes_remaining))).strftime("%Y-%m-%dT%H:%M:%SZ")
        cp = round(float(current_price or 0.0), 2)
        sc = round(float(shipping_cost or 0.0), 2)
        raw_item = {
            "ebay_item_id": item_id,
            "title": title.strip(),
            "url": clean_url,
            "image_url": "",
            "buying_option": buying_option.upper() if buying_option else "AUCTION",
            "current_price": cp,
            "shipping_cost": sc,
            "total_cost": round(cp + sc, 2),
            "bid_count": 0,
            "end_time": resolved_end,
            "seller_username": "",
            "seller_feedback_pct": None,
            "condition": "",
            "source_query": "manual_watch",
        }
    else:
        # Allow optional user overrides on top of API result
        if current_price is not None:
            raw_item["current_price"] = round(float(current_price), 2)
            raw_item["total_cost"] = round(raw_item["current_price"] + raw_item["shipping_cost"], 2)
        if shipping_cost is not None:
            raw_item["shipping_cost"] = round(float(shipping_cost), 2)
            raw_item["total_cost"] = round(raw_item["current_price"] + raw_item["shipping_cost"], 2)

    with get_conn(db_path) as conn:
        catalog_cards = [dict(r) for r in conn.execute("SELECT * FROM catalog_cards;").fetchall()]
        saved = _upsert_radar_listing(
            conn.cursor(),
            raw_item,
            catalog_cards,
            force_watched=True,
            override_catalog_key=catalog_key,
        )

    return saved


async def dispatch_radar_alerts(db_path: Optional[str] = None) -> int:
    """Sends push alerts for un-alerted Snipe/Good Deals and Watched Ending-Soon auctions."""
    cfg = get_radar_config(db_path, mask_secrets=False)
    alert_cfg = get_alert_config(db_path)
    if not any((alert_cfg["gotify_url"] and alert_cfg["gotify_token"], alert_cfg["discord_webhook_url"], alert_cfg["ntfy_url"])):
        return 0

    min_disc = cfg["alert_min_discount_pct"]
    ending_window_min = cfg["alert_ending_soon_min"]
    needed_only = cfg["alert_needed_only"]
    now_utc = datetime.now(timezone.utc)

    with get_conn(db_path) as conn:
        candidates = [dict(r) for r in conn.execute("""
            SELECT l.*, c.card_name AS matched_card_name, c.set_name AS matched_set_name,
                   c.card_number AS matched_card_number, c.edition AS matched_edition
            FROM ebay_listings l
            LEFT JOIN catalog_cards c ON c.catalog_key = l.catalog_key
            WHERE l.is_active = 1 AND l.is_dismissed = 0 AND l.alert_sent = 0;
        """).fetchall()]

        vault_rows = conn.execute("SELECT catalog_key, is_raw, grade FROM vault_items WHERE catalog_key IS NOT NULL;").fetchall()

    best_owned: Dict[str, float] = {}
    for vr in vault_rows:
        ck = vr["catalog_key"]
        g = 0.0 if vr["is_raw"] else float(vr["grade"] or 0.0)
        best_owned[ck] = max(best_owned.get(ck, -1.0), g)

    sent_count = 0
    for item in candidates:
        ck = item.get("catalog_key")
        is_watched = bool(item.get("is_watched"))
        is_missing = bool(ck and ck not in best_owned)
        needs_upgrade = bool(ck and ck in best_owned and best_owned[ck] < 10.0)
        is_needed = is_missing or needs_upgrade

        if needed_only and not is_needed and not is_watched:
            continue

        # Check countdown
        mins_left: Optional[float] = None
        if item.get("end_time"):
            try:
                et = datetime.fromisoformat(item["end_time"].replace("Z", "+00:00"))
                mins_left = (et - now_utc).total_seconds() / 60.0
                if mins_left <= 0:
                    continue
            except Exception:
                mins_left = None

        disc = item.get("discount_pct")
        comp = item.get("market_comp")
        is_deal = disc is not None and disc >= min_disc
        is_watched_ending = is_watched and mins_left is not None and mins_left <= ending_window_min and (comp is None or item["total_cost"] <= comp)

        if not (is_deal or is_watched_ending):
            continue

        tag = "ENDING SOON" if is_watched_ending else (f"{item['deal_tier']} -{disc:.0f}%" if disc is not None else "WATCHED")
        card_lbl = f"{item['matched_card_name']} ({item['matched_set_name']} #{item['matched_card_number']})" if item.get("matched_card_name") else item["title"]
        grade_lbl = "Raw" if item["detected_grader"] == "RAW" else f"{item['detected_grader']} {item['detected_grade']}"
        comp_str = f" vs ${comp:,.2f} comp" if comp else ""
        time_str = f" | {int(mins_left)}m left" if mins_left is not None else ""

        res = await send_alert(
            title=f"[{tag}] {card_lbl}",
            message=f"{grade_lbl} • Total ${item['total_cost']:,.2f} (${item['current_price']:,.2f} + ${item['shipping_cost']:,.2f} ship){comp_str}{time_str}\n{item['title']}",
            url=item["url"],
            image_url=item.get("image_url") or "",
            priority=9 if (is_watched_ending or item["deal_tier"] == "SNIPE") else 7,
            db_path=db_path,
        )
        if res.get("sent"):
            with get_conn(db_path) as conn:
                conn.execute("UPDATE ebay_listings SET alert_sent = 1 WHERE ebay_item_id = ?;", (item["ebay_item_id"],))
            sent_count += 1

    return sent_count


async def run_ebay_radar_scan(
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes a full official eBay Browse API scan across all enabled radar_queries,
    refreshes watched listings, auto-matches against the Master Set, and dispatches alerts.
    """
    cfg = get_radar_config(db_path, mask_secrets=False)
    expire_ended_listings(db_path)

    if not cfg["ebay_configured"]:
        msg = "Add your free eBay Developer Client ID & Secret in Radar Setup to enable automatic scanning."
        if progress_cb:
            progress_cb(0, 0, msg)
        return {"ok": False, "configured": False, "message": msg}

    with get_conn(db_path) as conn:
        queries = [dict(r) for r in conn.execute("SELECT * FROM radar_queries WHERE enabled = 1 ORDER BY id ASC;").fetchall()]
        catalog_cards = [dict(r) for r in conn.execute("SELECT * FROM catalog_cards;").fetchall()]
        watched_ids = [
            r["ebay_item_id"] for r in conn.execute(
                "SELECT ebay_item_id FROM ebay_listings WHERE is_watched = 1 AND is_active = 1 AND ebay_item_id LIKE 'v1|%';"
            ).fetchall()
        ]

    total_steps = len(queries) + (1 if watched_ids else 0)
    fetched_items: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()
    errors: List[str] = []

    async with httpx.AsyncClient(timeout=18.0, follow_redirects=True) as client:
        token = await get_ebay_access_token(client, cfg)
        base = _ebay_api_base(cfg["ebay_env"])
        headers = {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": cfg["ebay_marketplace"],
        }

        for idx, qrow in enumerate(queries, start=1):
            q_str = qrow["query"]
            b_filt = (qrow.get("buying_filter") or "ALL").upper()
            if progress_cb:
                progress_cb(idx - 1, total_steps, f"Scanning eBay ({idx}/{len(queries)}): {qrow['label'] or q_str}...")

            filter_str = "buyingOptions:{AUCTION}" if b_filt == "AUCTION" else (
                "buyingOptions:{FIXED_PRICE}" if b_filt == "FIXED_PRICE" else "buyingOptions:{AUCTION|FIXED_PRICE}"
            )
            params: Dict[str, Any] = {
                "q": q_str,
                "category_ids": EBAY_TCG_SINGLE_CATEGORY,
                "filter": filter_str,
                "limit": "50",
            }
            if b_filt == "AUCTION":
                params["sort"] = "endingSoonest"

            try:
                resp = await client.get(f"{base}/buy/browse/v1/item_summary/search", params=params, headers=headers)
                if resp.status_code == 200:
                    summaries = resp.json().get("itemSummaries") or []
                    for s_item in summaries:
                        parsed = _parse_browse_item_summary(s_item, source_query=qrow["label"] or q_str)
                        if not parsed or parsed["ebay_item_id"] in seen_ids:
                            continue
                        if is_junk_listing(parsed["title"]):
                            continue
                        seen_ids.add(parsed["ebay_item_id"])
                        fetched_items.append(parsed)
                else:
                    errors.append(f"{q_str}: HTTP {resp.status_code}")
            except Exception as exc:
                errors.append(f"{q_str}: {exc}")

        # Refresh active watched items directly so bids stay fresh right up to the last minute
        if watched_ids:
            if progress_cb:
                progress_cb(len(queries), total_steps, f"Refreshing {len(watched_ids)} watched auction(s)...")
            for wid in watched_ids:
                if wid in seen_ids:
                    continue
                try:
                    r = await client.get(f"{base}/buy/browse/v1/item/{wid}", headers=headers)
                    if r.status_code == 200:
                        parsed = _parse_browse_item_summary(r.json(), source_query="watched_refresh")
                        if parsed:
                            seen_ids.add(parsed["ebay_item_id"])
                            fetched_items.append(parsed)
                    elif r.status_code == 404:
                        with get_conn(db_path) as conn:
                            conn.execute("UPDATE ebay_listings SET is_active = 0 WHERE ebay_item_id = ?;", (wid,))
                except Exception:
                    pass

    # Persist all fetched items in a single fast SQLite transaction
    matched_count = 0
    hot_deals = 0
    with get_conn(db_path) as conn:
        c = conn.cursor()
        for raw_item in fetched_items:
            saved = _upsert_radar_listing(c, raw_item, catalog_cards)
            if saved["catalog_key"]:
                matched_count += 1
            if saved["deal_tier"] in ("SNIPE", "GOOD"):
                hot_deals += 1

    alerts_sent = await dispatch_radar_alerts(db_path)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    summary = f"Scanned {len(queries)} queries: {len(fetched_items)} live listings ({matched_count} matched, {hot_deals} hot deals, {alerts_sent} alerts)."
    set_setting("radar_last_scan_at", now_str, db_path)
    set_setting("radar_last_scan_summary", summary, db_path)

    if progress_cb:
        progress_cb(total_steps, total_steps, summary)

    return {
        "ok": True,
        "configured": True,
        "queries_run": len(queries),
        "listings_found": len(fetched_items),
        "matched": matched_count,
        "hot_deals": hot_deals,
        "alerts_sent": alerts_sent,
        "errors": errors[:5],
        "summary": summary,
    }
