"""
Visual error & verification callout overlays for Vulpix TCG cards.
Coordinates (x, y, w, h) are percentages on standard 2.5" x 3.5" Pokémon card geometry
so the UI can highlight the exact spot on the photo where an error, stamp, or print mark appears.
"""

from __future__ import annotations

from typing import Dict, List


def get_visual_callouts(
    *,
    set_name: str,
    language: str,
    edition: str,
    variant_key: str,
    is_error: bool = False,
    error_description: str = "",
    pokecottage_id: str = "",
) -> List[Dict]:
    """Returns structured visual callout boxes to render directly on top of the card scan."""
    s_low = (set_name or "").lower()
    l_low = (language or "").lower()
    ed_low = (edition or "").lower()
    vk_low = (variant_key or "").lower()
    pc_low = (pokecottage_id or "").lower()
    err_low = (error_description or "").lower()

    callouts: List[Dict] = []

    # --- 1996 Japanese Base Set / Expansion Pack ---
    if "expansion pack" in s_low and l_low == "japanese":
        if "no_rarity" in vk_low or "no rarity" in ed_low or "norarity" in pc_low:
            callouts.append({
                "x": 83, "y": 89, "w": 13, "h": 7,
                "label": "No Rarity Symbol",
                "detail": "Bottom-right corner is completely blank (missing ● circle). Authentic 1st Print 1996 Japanese Base Set.",
                "severity": "error",
            })
        else:
            callouts.append({
                "x": 83, "y": 89, "w": 13, "h": 7,
                "label": "Rarity Symbol ●",
                "detail": "Bottom-right corner shows the Common ● circle symbol (Standard print).",
                "severity": "verify",
            })
        return callouts

    # --- 1999 English Base Set #68/102 (HP 50, Shadowless, Blue Dot, Ink, Water Symbol, 4th Print) ---
    if s_low == "base set" and l_low == "english":
        if "bluedoterror" in pc_low or "blue dot" in ed_low or "blue dot" in err_low:
            callouts.append({
                "x": 54, "y": 54, "w": 18, "h": 13,
                "label": "Blue Dot Error",
                "detail": "Distinct stray blue printer ink dot / hickey visible on the card body.",
                "severity": "error",
            })
            if "1st" in ed_low or pc_low.endswith("bluedoterror"):
                callouts.append({
                    "x": 5, "y": 47, "w": 13, "h": 9,
                    "label": "1st Edition Stamp",
                    "detail": "Black '1' Edition stamp directly beneath the left art frame.",
                    "severity": "stamp",
                })
            callouts.append({
                "x": 67, "y": 4, "w": 25, "h": 7,
                "label": '"HP 50" Typo',
                "detail": 'Early Base Set print reads "HP 50" reversed instead of "50 HP".',
                "severity": "verify",
            })
            return callouts

        if "watersymbolerror" in pc_low or "water symbol" in ed_low or "water symbol" in err_low:
            callouts.append({
                "x": 5, "y": 79, "w": 25, "h": 11,
                "label": "Water Symbol Error",
                "detail": "Check the weakness Water energy icon at bottom-left for the documented symbol/ink anomaly.",
                "severity": "error",
            })
            callouts.append({
                "x": 67, "y": 4, "w": 25, "h": 7,
                "label": '"HP 50" Typo',
                "detail": 'Reads "HP 50" instead of "50 HP".',
                "severity": "verify",
            })
            return callouts

        if "inkerror" in pc_low or "ink error" in ed_low:
            callouts.append({
                "x": 14, "y": 14, "w": 72, "h": 34,
                "label": "Ink Print Error",
                "detail": "Visible ink smudge / registration print defect across the artwork/frame.",
                "severity": "error",
            })
            return callouts

        if "4th_print" in vk_low or "1999-2000" in ed_low or "fourthprint" in pc_low:
            callouts.append({
                "x": 67, "y": 4, "w": 25, "h": 7,
                "label": 'Corrected "50 HP"',
                "detail": 'ONLY English Base Set printing where "HP 50" was fixed to "50 HP"!',
                "severity": "verify",
            })
            callouts.append({
                "x": 12, "y": 90, "w": 76, "h": 6,
                "label": "©1999-2000 Copyright",
                "detail": "Bottom copyright line must explicitly end with ©1999-2000 Wizards (UK/4th Print).",
                "severity": "stamp",
            })
            return callouts

        if "1st" in ed_low or "firstedition" in pc_low:
            callouts.append({
                "x": 5, "y": 47, "w": 13, "h": 9,
                "label": "1st Edition Stamp",
                "detail": "Black 1st Edition stamp below bottom-left of art box.",
                "severity": "stamp",
            })
            callouts.append({
                "x": 85, "y": 11, "w": 7, "h": 37,
                "label": "Shadowless Border",
                "detail": "No dark drop shadow along the right edge of the artwork border.",
                "severity": "verify",
            })
            callouts.append({
                "x": 67, "y": 4, "w": 25, "h": 7,
                "label": '"HP 50" Typo',
                "detail": 'Printed as "HP 50" (reversed) rather than "50 HP".',
                "severity": "verify",
            })
            return callouts

        if "shadowless" in ed_low or "shadowless" in vk_low:
            callouts.append({
                "x": 85, "y": 11, "w": 7, "h": 37,
                "label": "No Drop Shadow",
                "detail": "Clean right art border with NO dark drop shadow and NO 1st Edition stamp.",
                "severity": "verify",
            })
            callouts.append({
                "x": 12, "y": 90, "w": 76, "h": 6,
                "label": '©1995, 96, 98, 99',
                "detail": 'Copyright includes the extra "99" year.',
                "severity": "stamp",
            })
            callouts.append({
                "x": 67, "y": 4, "w": 25, "h": 7,
                "label": '"HP 50" Typo',
                "detail": 'Reads "HP 50" reversed.',
                "severity": "verify",
            })
            return callouts

        # Standard Unlimited Base Set English
        callouts.append({
            "x": 67, "y": 4, "w": 25, "h": 7,
            "label": '"HP 50" (Uncorrected)',
            "detail": 'Unlimited 3rd Print still reads "HP 50" reversed (corrected only in 4th Print ©1999-2000).',
            "severity": "verify",
        })
        callouts.append({
            "x": 85, "y": 11, "w": 7, "h": 37,
            "label": "Drop Shadow Present",
            "detail": "Thick dark drop shadow along right border of artwork frame.",
            "severity": "verify",
        })
        return callouts

    # --- Gym Heroes Grey Stamp 1st Edition Error ---
    if "grey stamp" in ed_low or "grey stamp" in err_low:
        callouts.append({
            "x": 5, "y": 47, "w": 14, "h": 10,
            "label": "Grey 1st Ed Stamp Error",
            "detail": "1st Edition stamp printed visibly faded/grey due to low ink on the press instead of crisp jet black.",
            "severity": "error",
        })
        return callouts

    # --- Gym Challenge Brock's Vulpix W-Stamp Promo ---
    if "w_stamp" in vk_low or "wotc" in pc_low or "w-stamp" in ed_low or "wizards of the coast" in ed_low:
        callouts.append({
            "x": 74, "y": 42, "w": 17, "h": 11,
            "label": 'Gold Foil "W" Stamp',
            "detail": 'Metallic gold Wizards of the Coast "W" logo stamped in lower-right corner of the artwork (TopDeck Magazine #9).',
            "severity": "stamp",
        })
        return callouts

    # --- General 1st Edition Stamp ---
    if "1st_edition" in vk_low or "1st edition" in ed_low:
        if l_low == "japanese":
            callouts.append({
                "x": 5, "y": 89, "w": 15, "h": 7,
                "label": "JP 1st Edition Mark",
                "detail": 'Small "1" Edition emblem at the bottom-left corner of Japanese cards.',
                "severity": "stamp",
            })
        else:
            callouts.append({
                "x": 5, "y": 47, "w": 13, "h": 9,
                "label": "1st Edition Stamp",
                "detail": "Edition 1 stamp below bottom-left corner of the artwork frame.",
                "severity": "stamp",
            })

    # --- EX Era Expansion Stamps ---
    if "setstamp" in pc_low or "expansion stamp" in ed_low:
        callouts.append({
            "x": 55, "y": 40, "w": 36, "h": 12,
            "label": "Expansion Logo Stamp",
            "detail": "Foil set name logo stamped directly onto the bottom-right corner of the card illustration (EX-era Reverse Holo).",
            "severity": "stamp",
        })

    # --- Master Ball / Poké Ball Holo (151 / Terastal) ---
    if "master_ball" in vk_low or "master ball" in ed_low:
        callouts.append({
            "x": 15, "y": 52, "w": 70, "h": 34,
            "label": 'Master Ball ("M") Foil',
            "detail": 'Reverse holo pattern features Master Balls with the distinct "M" and twin bumps on top (1 per Japanese booster box!).',
            "severity": "stamp",
        })
    elif "poke_ball" in vk_low or "poké ball" in ed_low or "poke ball" in ed_low:
        callouts.append({
            "x": 15, "y": 52, "w": 70, "h": 34,
            "label": "Poké Ball Foil Pattern",
            "detail": 'Standard Poké Ball reverse holo pattern (NO "M" emblem on the balls — check carefully vs Master Ball!).',
            "severity": "verify",
        })

    # --- Holiday Calendar / Snowflake Stamp ---
    if "calendar" in ed_low or "snowflake" in ed_low or "holidaycalendar" in pc_low:
        callouts.append({
            "x": 68, "y": 40, "w": 22, "h": 13,
            "label": "Snowflake Stamp",
            "detail": "Silver/foil snowflake emblem stamped on the lower-right artwork (Pokémon Holiday Calendar exclusive).",
            "severity": "stamp",
        })

    # --- Play! Pokémon Prize Pack Stamp ---
    if "play" in ed_low or "playpokemon" in pc_low:
        callouts.append({
            "x": 66, "y": 40, "w": 25, "h": 12,
            "label": "Play! Pokémon Stamp",
            "detail": "Play! Pokémon Prize Pack logo stamped on bottom-right corner of the artwork.",
            "severity": "stamp",
        })

    # --- Store / Event Stamps (Build-A-Bear, Toys R Us, Pokémon TCG Gym) ---
    if any(k in ed_low for k in ("build-a-bear", "toys r us", "tcg gym", "pokemon center", "pokémon center")):
        callouts.append({
            "x": 58, "y": 40, "w": 32, "h": 13,
            "label": f"{edition} Stamp",
            "detail": f"Verify the official {edition} promotional stamp on the card artwork.",
            "severity": "stamp",
        })

    # --- Generic Error Fallback ---
    if is_error and not callouts:
        callouts.append({
            "x": 10, "y": 10, "w": 80, "h": 80,
            "label": "Documented Error Variant",
            "detail": error_description or "Verify specific misprint details against high-res seller photos.",
            "severity": "error",
        })

    return callouts
