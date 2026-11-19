"""
Multi-language translator for Pokémon TCG Vulpix card names & set names across all 14 official languages.
Turns native foreign names (e.g. 'タケシのロコン', 'Goupix d'Alola-VSTAR', 'リーダーズスタジアム', 'Tempête Argentée')
into clean readable English while preserving the original native text for auction listing verification.
"""

from __future__ import annotations

import re
from typing import Dict, Optional, Tuple


# Canonical TCGdex set_id -> Official English set name (covers Base Set through 2026 SV / Mega eras)
TCGDEX_SET_ID_TO_EN: Dict[str, str] = {
    # WOTC / Original / Neo / e-Card
    "base1": "Base Set",
    "base2": "Jungle",
    "base3": "Fossil",
    "base4": "Base Set 2",
    "base5": "Team Rocket",
    "basep": "Wizards Black Star Promos",
    "gym1": "Gym Heroes",
    "gym2": "Gym Challenge",
    "neo1": "Neo Genesis",
    "neo2": "Neo Discovery",
    "neo3": "Neo Revelation",
    "neo4": "Neo Destiny",
    "lc": "Legendary Collection",
    "ecard1": "Expedition Base Set",
    "ecard2": "Aquapolis",
    "ecard3": "Skyridge",
    # EX Era
    "ex1": "EX Ruby & Sapphire",
    "ex2": "EX Sandstorm",
    "ex3": "EX Dragon",
    "ex4": "EX Team Magma vs Team Aqua",
    "ex5": "EX Hidden Legends",
    "ex6": "EX FireRed & LeafGreen",
    "ex7": "EX Team Rocket Returns",
    "ex8": "EX Deoxys",
    "ex9": "EX Emerald",
    "ex10": "EX Unseen Forces",
    "ex11": "EX Delta Species",
    "ex12": "EX Legend Maker",
    "ex13": "EX Holon Phantoms",
    "ex14": "EX Crystal Guardians",
    "ex15": "EX Dragon Frontiers",
    "ex16": "EX Power Keepers",
    "np": "Nintendo Black Star Promos",
    # Diamond & Pearl / Platinum / HGSS
    "dp1": "Diamond & Pearl",
    "dp2": "Mysterious Treasures",
    "dp3": "Secret Wonders",
    "dp4": "Great Encounters",
    "dp5": "Majestic Dawn",
    "dp6": "Legends Awakened",
    "dp7": "Stormfront",
    "dpp": "DP Black Star Promos",
    "pl1": "Platinum",
    "pl2": "Rising Rivals",
    "pl3": "Supreme Victors",
    "pl4": "Arceus",
    "hgss1": "HeartGold & SoulSilver",
    "hgss2": "HS—Unleashed",
    "hgss3": "HS—Undaunted",
    "hgss4": "HS—Triumphant",
    "hgssp": "HGSS Black Star Promos",
    "col1": "Call of Legends",
    # Black & White
    "bw1": "Black & White",
    "bw2": "Emerging Powers",
    "bw3": "Noble Victories",
    "bw4": "Next Destinies",
    "bw5": "Dark Explorers",
    "bw6": "Dragons Exalted",
    "bw7": "Boundaries Crossed",
    "bw8": "Plasma Storm",
    "bw9": "Plasma Freeze",
    "bw10": "Plasma Blast",
    "bw11": "Legendary Treasures",
    "bwp": "BW Black Star Promos",
    # XY
    "xy0": "Kalos Starter Set",
    "xy1": "XY",
    "xy2": "Flashfire",
    "xy3": "Furious Fists",
    "xy4": "Phantom Forces",
    "xy5": "Primal Clash",
    "xy6": "Roaring Skies",
    "xy7": "Ancient Origins",
    "xy8": "BREAKthrough",
    "xy9": "BREAKpoint",
    "g1": "Generations",
    "xy10": "Fates Collide",
    "xy11": "Steam Siege",
    "xy12": "Evolutions",
    "xyp": "XY Black Star Promos",
    # Sun & Moon
    "sm1": "Sun & Moon",
    "sm2": "Guardians Rising",
    "sm3": "Burning Shadows",
    "sm3.5": "Shining Legends",
    "sm4": "Crimson Invasion",
    "sm5": "Ultra Prism",
    "sm6": "Forbidden Light",
    "sm7": "Celestial Storm",
    "sm7.5": "Dragon Majesty",
    "sm8": "Lost Thunder",
    "sm9": "Team Up",
    "det1": "Detective Pikachu",
    "sm10": "Unbroken Bonds",
    "sm11": "Unified Minds",
    "sm115": "Hidden Fates",
    "sma": "Hidden Fates Shiny Vault",
    "sm12": "Cosmic Eclipse",
    "smp": "SM Black Star Promos",
    # Sword & Shield
    "swsh1": "Sword & Shield",
    "swsh2": "Rebel Clash",
    "swsh3": "Darkness Ablaze",
    "swsh3.5": "Champion's Path",
    "swsh4": "Vivid Voltage",
    "swsh4.5": "Shining Fates",
    "swsh5": "Battle Styles",
    "swsh6": "Chilling Reign",
    "swsh7": "Evolving Skies",
    "cel25": "Celebrations",
    "swsh8": "Fusion Strike",
    "swsh9": "Brilliant Stars",
    "swsh10": "Astral Radiance",
    "swsh10.5": "Pokémon GO",
    "swsh11": "Lost Origin",
    "swsh12": "Silver Tempest",
    "swsh12.5": "Crown Zenith",
    "swshp": "SWSH Black Star Promos",
    # Scarlet & Violet
    "sv01": "Scarlet & Violet",
    "sv02": "Paldea Evolved",
    "sv03": "Obsidian Flames",
    "sv03.5": "Scarlet & Violet—151",
    "sv04": "Paradox Rift",
    "sv04.5": "Paldean Fates",
    "sv05": "Temporal Forces",
    "sv06": "Twilight Masquerade",
    "sv06.5": "Shrouded Fable",
    "sv07": "Stellar Crown",
    "sv08": "Surging Sparks",
    "sv08.5": "Prismatic Evolutions",
    "sv09": "Journey Together",
    "sv10": "Destined Rivals",
    "svp": "SVP Black Star Promos",
    # McDonald's & Specials
    "2018fr": "McDonald's Collection 2018",
    "2019fr": "McDonald's Collection 2019",
    "mcd18": "McDonald's Collection 2018",
    "mcd19": "McDonald's Collection 2019",
    "mcd21": "McDonald's Collection 2021",
    "mcd22": "McDonald's Match Battle 2022",
    "fut20": "Pokémon Futsal",
    "tk-sm-a": "Sun & Moon Trainer Kit (Alolan Sandslash & Alolan Ninetales)",
    # Japanese TCGdex set IDs
    "pmcg1": "Expansion Pack",
    "pmcg4": "Leaders' Stadium",
    "pmcg5": "Challenge from the Darkness",
    "vs1": "Pokémon VS",
    "web1": "Pokémon Web",
    "e1": "Base Expansion Pack",
    "e2": "The Town on No Map",
    "e3": "Wind from the Sea",
    "adv4": "Undone Seal",
    "pcg3": "Rocket Gang Strikes Back",
    "pcg4": "Golden Sky, Silvery Ocean",
    "pcg8": "Miracle Crystal",
    "pcg9": "Offense and Defense of the Furthest Ends",
    "pcg10": "World Champions Pack",
    "dpbp": "Space-Time Creation",
    "dpt1": "Galactic's Conquest",
    "l2": "Reviving Legends",
    "bw5": "Dragon Blade",
    "cp6": "Expansion Pack 20th Anniversary",
    "sm2k": "Islands Await You",
    "sm2+": "Facing a New Trial",
    "sm4+": "GX Battle Boost",
    "sm7a": "Fairy Rise",
    "sm8b": "GX Ultra Shiny",
    "sm9": "Tag Bolt",
    "sm12": "Alter Genesis",
    "sm12a": "Tag All Stars",
    "s1w": "Sword",
    "s1a": "VMAX Rising",
    "s7r": "Blue Sky Stream",
    "s11a": "Incandescent Arcana",
    "sv2a": "Pokémon Card 151",
    "sv3": "Ruler of the Black Flame",
    "sv6": "Mask of Change",
    "sv8": "Super Electric Breaker",
    "m1l": "Mega Brave",
}

# Foreign localized set names -> English set names (lowercased keys)
FOREIGN_SET_NAME_TO_EN: Dict[str, str] = {
    # Japanese
    "拡張パック": "Expansion Pack",
    "第1弾 拡張パック": "Expansion Pack",
    "リーダーズスタジアム": "Leaders' Stadium",
    "ジム拡張第1弾 リーダーズスタジアム": "Leaders' Stadium",
    "闇からの挑戦": "Challenge from the Darkness",
    "ジム拡張第2弾 闇からの挑戦": "Challenge from the Darkness",
    "闇、そして光へ...": "Darkness, and to Light...",
    "闇、そして光へ": "Darkness, and to Light...",
    "基本拡張パック": "Base Expansion Pack",
    "地図にない町": "The Town on No Map",
    "海からの風": "Wind from the Sea",
    "とかれた封印": "Undone Seal",
    "クイック・コンストラクション・パック": "Quick Construction Pack",
    "さいはての攻防": "Offense and Defense of the Furthest Ends",
    "ワールドチャンピオンズパック": "World Champions Pack",
    "ギンガの覇道": "Galactic's Conquest",
    "よみがえる伝説": "Reviving Legends",
    "リューズブラスト": "Dragon Blast",
    "リューノブレード": "Dragon Blade",
    "exバトルブースト": "EX Battle Boost",
    "ガイアボルケーノ": "Gaia Volcano",
    "タイダルストーム": "Tidal Storm",
    "ポケットモンスターカードゲーム 拡張パック 20th anniversary": "Expansion Pack 20th Anniversary",
    "キミを待つ島々": "Islands Await You",
    "新たなる試練の向こう": "Facing a New Trial",
    "gxバトルブースト": "GX Battle Boost",
    "フェアリーライズ": "Fairy Rise",
    "gxウルトラシャイニー": "GX Ultra Shiny",
    "タッグボルト": "Tag Bolt",
    "オルタージェネシス": "Alter Genesis",
    "タッグオールスターズ": "Tag All Stars",
    "ソード": "Sword",
    "vマックスライジング": "VMAX Rising",
    "vmaxライジング": "VMAX Rising",
    "蒼空ストリーム": "Blue Sky Stream",
    "フュージョンアーツ": "Fusion Arts",
    "白熱のアルカナ": "Incandescent Arcana",
    "黒炎の支配者": "Ruler of the Black Flame",
    "ポケモンカード151": "Pokémon Card 151",
    "変幻の仮面": "Mask of Change",
    "超電ブレイカー": "Super Electric Breaker",
    "メガブレイブ": "Mega Brave",
    "サン＆ムーン プロモカード": "Sun & Moon Promos",
    "ソード＆シールド プロモカード": "Sword & Shield Promos",
    "スカーレット＆バイオレット プロモカード": "Scarlet & Violet Promos",
    "xy プロモカード": "XY Promos",
    "ファミリーポケモンカードゲーム": "Family Pokémon Card Game",
    "スタートデッキ100": "Start Deck 100",
    # French
    "set de base": "Base Set",
    "neo destiny": "Neo Destiny",
    "destinée néo": "Neo Destiny",
    "expédition": "Expedition Base Set",
    "ex légendes oubliées": "EX Hidden Legends",
    "ex émeraude": "EX Emerald",
    "ex gardiens de cristal": "EX Crystal Guardians",
    "ex île des dragons": "EX Dragon Frontiers",
    "ex gardiens du pouvoir": "EX Power Keepers",
    "platine": "Platinum",
    "hs déchaînement": "HS—Unleashed",
    "l'appel des légendes": "Call of Legends",
    "dragons exaltés": "Dragons Exalted",
    "trésors légendaires": "Legendary Treasures",
    "primo-choc": "Primal Clash",
    "évolutions": "Evolutions",
    "gardiens ascendants": "Guardians Rising",
    "ombres ardentes": "Burning Shadows",
    "tonnerre perdu": "Lost Thunder",
    "duo de choc": "Team Up",
    "destinées occultes": "Hidden Fates",
    "éclipse cosmique": "Cosmic Eclipse",
    "épée et bouclier": "Sword & Shield",
    "clash des rebelles": "Rebel Clash",
    "la voie du maître": "Champion's Path",
    "poing de fusion": "Fusion Strike",
    "tempête argentée": "Silver Tempest",
    "flammes obsidiennes": "Obsidian Flames",
    "151": "Scarlet & Violet—151",
    "mascarade crépusculaire": "Twilight Masquerade",
    "étincelles déferlantes": "Surging Sparks",
    # German
    "grundset": "Base Set",
    "ex verborgene mächte": "EX Hidden Legends",
    "ex smaragd": "EX Emerald",
    "ex dragon frontiers": "EX Dragon Frontiers",
    "ex power keepers": "EX Power Keepers",
    "platin": "Platinum",
    "entfesselt": "HS—Unleashed",
    "ruf der legenden": "Call of Legends",
    "hoheit der drachen": "Dragons Exalted",
    "legendäre schätze": "Legendary Treasures",
    "protoschock": "Primal Clash",
    "evolution": "Evolutions",
    "stunde der wächter": "Guardians Rising",
    "nacht in flammen": "Burning Shadows",
    "echo des donners": "Lost Thunder",
    "teams sind trumpf": "Team Up",
    "verborgenes schicksal": "Hidden Fates",
    "welten im wandel": "Cosmic Eclipse",
    "schwert & schild": "Sword & Shield",
    "clash der rebellen": "Rebel Clash",
    "weg des champs": "Champion's Path",
    "fusionsangriff": "Fusion Strike",
    "silberne sturmwinde": "Silver Tempest",
    "obsidianflammen": "Obsidian Flames",
    "maskerade im zwielicht": "Twilight Masquerade",
    "stürmische funken": "Surging Sparks",
    # Italian
    "set base": "Base Set",
    "ex leggende nascoste": "EX Hidden Legends",
    "ex smeraldo": "EX Emerald",
    "ex l'isola dei draghi": "EX Dragon Frontiers",
    "ex guardiani dei cristalli": "EX Crystal Guardians",
    "platino": "Platinum",
    "forze scatenate": "HS—Unleashed",
    "richiamo delle leggende": "Call of Legends",
    "stirpe dei draghi": "Dragons Exalted",
    "tesori leggendari": "Legendary Treasures",
    "scontro primordiale": "Primal Clash",
    "evoluzioni": "Evolutions",
    "guardiani nascenti": "Guardians Rising",
    "ombre infuocate": "Burning Shadows",
    "tuoni perduti": "Lost Thunder",
    "gioco di squadra": "Team Up",
    "destino sfuggente": "Hidden Fates",
    "eclissi cosmica": "Cosmic Eclipse",
    "spada e scudo": "Sword & Shield",
    "fragore ribelle": "Rebel Clash",
    "futuri campioni": "Champion's Path",
    "colpo fusione": "Fusion Strike",
    "tempesta argentata": "Silver Tempest",
    "ossidiana infuocata": "Obsidian Flames",
    "crepuscolo mascherato": "Twilight Masquerade",
    "scintille folgoranti": "Surging Sparks",
    # Spanish
    "set básico": "Base Set",
    "ex leyendas ocultas": "EX Hidden Legends",
    "ex esmeralda": "EX Emerald",
    "ex frontera dragón": "EX Dragon Frontiers",
    "platino": "Platinum",
    "liberados": "HS—Unleashed",
    "llamada de las leyendas": "Call of Legends",
    "dragones majestuosos": "Dragons Exalted",
    "tesoros legendarios": "Legendary Treasures",
    "duelo primigenio": "Primal Clash",
    "evoluciones": "Evolutions",
    "albor de guardianes": "Guardians Rising",
    "sombras ardientes": "Burning Shadows",
    "truenos perdidos": "Lost Thunder",
    "unión de aliados": "Team Up",
    "destinos ocultos": "Hidden Fates",
    "eclipse cósmico": "Cosmic Eclipse",
    "espada y escudo": "Sword & Shield",
    "choque rebelde": "Rebel Clash",
    "camino de campeones": "Champion's Path",
    "golpe fusión": "Fusion Strike",
    "tempestad plateada": "Silver Tempest",
    "llamas obsidian": "Obsidian Flames",
    "llamas obsidianas": "Obsidian Flames",
    "mascarada crepuscular": "Twilight Masquerade",
    "chispas fulgurantes": "Surging Sparks",
    # Portuguese
    "coleção básica": "Base Set",
    "guardiões ascendentes": "Guardians Rising",
    "sombras ardentes": "Burning Shadows",
    "trovões perdidos": "Lost Thunder",
    "união de aliados": "Team Up",
    "destinos ocultos": "Hidden Fates",
    "eclipse cósmico": "Cosmic Eclipse",
    "espada e escudo": "Sword & Shield",
    "rixa rebelde": "Rebel Clash",
    "caminho do campeão": "Champion's Path",
    "golpe fusão": "Fusion Strike",
    "tempestade prateada": "Silver Tempest",
    "obsidiana em chamas": "Obsidian Flames",
    "máscaras do crepúsculo": "Twilight Masquerade",
    "fagulhas impetuosas": "Surging Sparks",
    # Korean
    "백열의 아르카나": "Incandescent Arcana",
    "흑염의 지배자": "Ruler of the Black Flame",
    "포켓몬 카드 151": "Pokémon Card 151",
    "변환의 가면": "Mask of Change",
    "초전 브레이커": "Super Electric Breaker",
    "창공스트림": "Blue Sky Stream",
    "퓨전아츠": "Fusion Arts",
    "소드": "Sword",
    "v맥스 라이징": "VMAX Rising",
    "얼터제네시스": "Alter Genesis",
    "태그볼트": "Tag Bolt",
    "태그올스타즈": "Tag All Stars",
    "페어리라이즈": "Fairy Rise",
    "gx 울트라샤이니": "GX Ultra Shiny",
    # Traditional / Simplified Chinese
    "白熱奧秘": "Incandescent Arcana",
    "黯焰支配者": "Ruler of the Black Flame",
    "寶可夢卡牌151": "Pokémon Card 151",
    "變幻假面": "Mask of Change",
    "超電突破": "Super Electric Breaker",
    "蒼空摩天": "Blue Sky Stream",
    "匯流藝術": "Fusion Arts",
    "雙璧戰士": "Matchless Fighters",
    "眾星雲集組合篇": "All Stars Collection",
    "美夢成真組合篇": "Dreams Come True Collection",
    "劍": "Sword",
    "無極力量": "Infinity Zone",
    # Thai / Indonesian
    "อาคานาเปลวเพลิงขาว": "Incandescent Arcana",
    "ผู้ปกครองแห่งเปลวเพลิงดำ": "Ruler of the Black Flame",
    "โปเกมอนการ์ด 151": "Pokémon Card 151",
    "หน้ากากแห่งการเปลี่ยนแปลง": "Mask of Change",
    "Kilau Hitam": "Obsidian Flames",
    "kilau hitam": "Obsidian Flames",
    "topeng transfigurasi": "Twilight Masquerade",
    "badai perak": "Silver Tempest",
    "percikan menyengat": "Surging Sparks",
}


def is_ascii_english_like(text: str) -> bool:
    """True when text contains only Latin/ASCII characters (no CJK/Hangul/Thai)."""
    return all(ord(ch) < 0x0250 for ch in (text or ""))


def translate_card_name(raw_name: str, language: str = "") -> Tuple[str, str]:
    """
    Translates any localized Vulpix card title across all 14 official languages into English.
    Returns (english_name, native_name). `native_name` is empty if already identical to English.
    """
    orig = (raw_name or "").strip()
    if not orig:
        return "Vulpix", ""

    low = orig.lower()

    # Keep special non-Vulpix-name themes intact (e.g. Poncho-wearing Pikachu)
    if "poncho" in low or "ポンチョ" in orig:
        if "alolan" in low or "アローラ" in orig:
            en = "Poncho-wearing Pikachu (Alolan Vulpix)"
        else:
            en = "Poncho-wearing Pikachu (Vulpix)"
        return en, (orig if orig != en else "")

    # Check trainer prefixes first across all languages
    is_brock = any(k in low for k in ("brock", "pierre", "rocko")) or any(k in orig for k in ("タケシ", "웅의", "小剛", "小刚"))
    is_blaine = any(k in low for k in ("blaine", "auguste", "pyro")) or any(k in orig for k in ("カツラ", "강연의", "夏伯"))
    is_alolan = (
        any(k in low for k in ("alola", "alolan"))
        or any(k in orig for k in ("アローラ", "알로라", "阿羅拉", "阿罗拉", "อโลลา"))
    )

    # Check card mechanic suffixes (VSTAR / V-ASTRO / VMAX / V / GX / ex / EX / δ)
    suffix = ""
    if re.search(r"(?:vstar|v-star|v-astro|vastro|v\s*astro)", low):
        suffix = " VSTAR"
    elif re.search(r"(?:vmax|v-max)", low):
        suffix = " VMAX"
    elif re.search(r"(?:[\s\-]V\b|V$)", orig):
        suffix = " V"
    elif re.search(r"(?:[\s\-]gx\b|gx$)", low):
        suffix = " GX"
    elif re.search(r"[\s\-]ex\b", low):
        suffix = " ex" if "ex" in orig and "EX" not in orig else " EX"
    elif "δ" in orig or "delta" in low:
        suffix = " δ"

    if is_brock:
        en = f"Brock's Vulpix{suffix}"
    elif is_blaine:
        en = f"Blaine's Vulpix{suffix}"
    elif is_alolan:
        en = f"Alolan Vulpix{suffix}"
    else:
        # Check if it's any localized form of plain Vulpix
        vulpix_tokens = ("vulpix", "goupix", "ロコン", "식스테일", "六尾", "โรคอน")
        if any(tok in low or tok in orig for tok in vulpix_tokens):
            en = f"Vulpix{suffix}"
        else:
            en = orig

    native = orig if orig.lower() != en.lower() else ""
    return en, native


def translate_set_name(
    raw_set_name: str,
    set_id: str = "",
    en_set_lookup: Optional[Dict[str, str]] = None,
) -> Tuple[str, str]:
    """
    Translates a localized Pokémon TCG set name to its official English set name.
    Priority:
      1. Live TCGdex English set lookup by canonical `set_id` (when provided during sync)
      2. Static `TCGDEX_SET_ID_TO_EN` map by `set_id`
      3. Static `FOREIGN_SET_NAME_TO_EN` dictionary by normalized foreign name
      4. Original string fallback (preserved cleanly)
    Returns (english_set_name, native_set_name).
    """
    orig = (raw_set_name or "").strip()
    sid = (set_id or "").strip().lower()

    en = ""
    if sid and en_set_lookup and sid in en_set_lookup:
        en = en_set_lookup[sid]
    elif sid and sid in TCGDEX_SET_ID_TO_EN:
        en = TCGDEX_SET_ID_TO_EN[sid]
    else:
        key = orig.lower().strip()
        if key in FOREIGN_SET_NAME_TO_EN:
            en = FOREIGN_SET_NAME_TO_EN[key]
        else:
            # Handle common localized Promo naming patterns (e.g. "Promos SM", "Promo XY", "SWSH Black Star Promos")
            if "promo" in key or "プロモ" in orig or "프로모" in orig:
                if "sv" in sid or "sv" in key or "スカーレット" in orig:
                    en = "Scarlet & Violet Promos"
                elif "swsh" in sid or "ソード" in orig:
                    en = "Sword & Shield Promos"
                elif "sm" in sid or "サン" in orig:
                    en = "Sun & Moon Promos"
                elif "xy" in sid or "xy" in key:
                    en = "XY Promos"
                elif "bw" in sid:
                    en = "Black & White Promos"
                elif "dp" in sid:
                    en = "Diamond & Pearl Promos"
                elif "base" in sid or "wotc" in key:
                    en = "Wizards Black Star Promos"
            elif "mcdonald" in key or "マクドナルド" in orig:
                m = re.search(r"(20\d{2})", orig)
                en = f"McDonald's Collection {m.group(1)}" if m else "McDonald's Collection"

    if not en:
        en = orig

    native = orig if (orig and orig.lower() != en.lower()) else ""
    return en, native
