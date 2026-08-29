"""
Seed data module for initializing The Vulpix Vault with comprehensive Master Set Catalog,
sample collection slabs & raw cards, and historical multi-tier market sales.
"""

from datetime import datetime, timedelta
import random
from typing import Optional
from db import (
    bulk_upsert_master_catalog,
    get_db_connection,
    insert_collection_card,
    insert_market_sale,
)

# Comprehensive Master Set Catalog of known Vulpix cards across all eras
MASTER_VULPIX_CATALOG = [
    # --- Base Set & Vintage Era (1996-2002) ---
    {
        "card_name": "Vulpix",
        "set_name": "Base Set",
        "card_number": "68/102",
        "release_year": 1999,
        "language": "English",
        "edition": "1st Edition",
        "rarity": "Common",
        "is_error": 0,
        "est_raw_price": 8.00,
        "est_grade10_price": 240.00,
        "image_url": "https://images.pokemontcg.io/base1/68_hires.png",
        "notes": "Original 1999 1st Edition Base Set.",
    },
    {
        "card_name": "Vulpix (Shadowless)",
        "set_name": "Base Set",
        "card_number": "68/102",
        "release_year": 1999,
        "language": "English",
        "edition": "Shadowless",
        "rarity": "Common",
        "is_error": 0,
        "est_raw_price": 5.00,
        "est_grade10_price": 130.00,
        "image_url": "https://images.pokemontcg.io/base1/68_hires.png",
        "notes": "Early Shadowless print run.",
    },
    {
        "card_name": "Vulpix (Unlimited)",
        "set_name": "Base Set",
        "card_number": "68/102",
        "release_year": 1999,
        "language": "English",
        "edition": "Unlimited",
        "rarity": "Common",
        "is_error": 0,
        "est_raw_price": 2.00,
        "est_grade10_price": 65.00,
        "image_url": "https://images.pokemontcg.io/base1/68_hires.png",
        "notes": "Unlimited print run.",
    },
    {
        "card_name": "Vulpix (HP 50 Error)",
        "set_name": "Base Set",
        "card_number": "68/102",
        "release_year": 1999,
        "language": "English",
        "edition": "Unlimited",
        "rarity": "Common",
        "is_error": 1,
        "error_description": "HP 50 printed instead of 50 HP (misplaced letters).",
        "est_raw_price": 35.00,
        "est_grade10_price": 350.00,
        "image_url": "https://images.pokemontcg.io/base1/68_hires.png",
        "notes": "Iconic Base Set error variant.",
    },
    {
        "card_name": "Vulpix (No Rarity Symbol)",
        "set_name": "Japanese Expansion Pack (Base Set)",
        "card_number": "No Number",
        "release_year": 1996,
        "language": "Japanese",
        "edition": "1st Print",
        "rarity": "Common",
        "is_error": 1,
        "error_description": "Missing bottom-right rarity star symbol (Japanese 1st edition equivalent).",
        "est_raw_price": 75.00,
        "est_grade10_price": 650.00,
        "image_url": "https://images.pokemontcg.io/base1/68_hires.png",
        "notes": "Holy grail vintage Japanese Vulpix variant.",
    },
    {
        "card_name": "Vulpix",
        "set_name": "Japanese Base Set",
        "card_number": "No Number",
        "release_year": 1996,
        "language": "Japanese",
        "edition": "Unlimited",
        "rarity": "Common",
        "is_error": 0,
        "est_raw_price": 4.00,
        "est_grade10_price": 55.00,
        "image_url": "https://images.pokemontcg.io/base1/68_hires.png",
        "notes": "Japanese standard print with rarity star.",
    },
    {
        "card_name": "Erika's Vulpix",
        "set_name": "Gym Heroes",
        "card_number": "49/132",
        "release_year": 2000,
        "language": "English",
        "edition": "1st Edition",
        "rarity": "Uncommon",
        "is_error": 0,
        "est_raw_price": 6.00,
        "est_grade10_price": 95.00,
        "image_url": "https://images.pokemontcg.io/gym1/49_hires.png",
        "notes": "1st Edition Gym Heroes.",
    },
    {
        "card_name": "Erika's Vulpix",
        "set_name": "Gym Heroes",
        "card_number": "49/132",
        "release_year": 2000,
        "language": "English",
        "edition": "Unlimited",
        "rarity": "Uncommon",
        "is_error": 0,
        "est_raw_price": 2.50,
        "est_grade10_price": 45.00,
        "image_url": "https://images.pokemontcg.io/gym1/49_hires.png",
        "notes": "Unlimited Gym Heroes.",
    },
    {
        "card_name": "Brock's Vulpix",
        "set_name": "Gym Challenge",
        "card_number": "73/132",
        "release_year": 2000,
        "language": "English",
        "edition": "1st Edition",
        "rarity": "Common",
        "is_error": 0,
        "est_raw_price": 5.00,
        "est_grade10_price": 85.00,
        "image_url": "https://images.pokemontcg.io/gym2/73_hires.png",
        "notes": "1st Edition Gym Challenge.",
    },
    {
        "card_name": "Brock's Vulpix",
        "set_name": "Gym Challenge",
        "card_number": "73/132",
        "release_year": 2000,
        "language": "English",
        "edition": "Unlimited",
        "rarity": "Common",
        "is_error": 0,
        "est_raw_price": 2.00,
        "est_grade10_price": 40.00,
        "image_url": "https://images.pokemontcg.io/gym2/73_hires.png",
        "notes": "Unlimited Gym Challenge.",
    },
    {
        "card_name": "Light Vulpix",
        "set_name": "Neo Destiny",
        "card_number": "80/105",
        "release_year": 2002,
        "language": "English",
        "edition": "1st Edition",
        "rarity": "Common",
        "is_error": 0,
        "est_raw_price": 18.00,
        "est_grade10_price": 210.00,
        "image_url": "https://images.pokemontcg.io/neo4/80_hires.png",
        "notes": "1st Edition Neo Destiny artwork.",
    },
    {
        "card_name": "Light Vulpix",
        "set_name": "Neo Destiny",
        "card_number": "80/105",
        "release_year": 2002,
        "language": "English",
        "edition": "Unlimited",
        "rarity": "Common",
        "is_error": 0,
        "est_raw_price": 6.00,
        "est_grade10_price": 75.00,
        "image_url": "https://images.pokemontcg.io/neo4/80_hires.png",
        "notes": "Unlimited Neo Destiny.",
    },

    # --- E-Card & EX Series Era (2002-2007) ---
    {
        "card_name": "Vulpix",
        "set_name": "Expedition",
        "card_number": "136/165",
        "release_year": 2002,
        "language": "English",
        "edition": "Unlimited",
        "rarity": "Common",
        "is_error": 0,
        "est_raw_price": 4.00,
        "est_grade10_price": 70.00,
        "image_url": "https://images.pokemontcg.io/ecard1/136_hires.png",
        "notes": "E-Reader dot code card.",
    },
    {
        "card_name": "Vulpix (Reverse Holo)",
        "set_name": "Expedition",
        "card_number": "136/165",
        "release_year": 2002,
        "language": "English",
        "edition": "Reverse Holo",
        "rarity": "Common",
        "is_error": 0,
        "est_raw_price": 22.00,
        "est_grade10_price": 190.00,
        "image_url": "https://images.pokemontcg.io/ecard1/136_hires.png",
        "notes": "Refractive e-Series reverse holo.",
    },
    {
        "card_name": "Vulpix",
        "set_name": "Aquapolis",
        "card_number": "116/147",
        "release_year": 2003,
        "language": "English",
        "edition": "Unlimited",
        "rarity": "Common",
        "is_error": 0,
        "est_raw_price": 5.00,
        "est_grade10_price": 85.00,
        "image_url": "https://images.pokemontcg.io/ecard2/116_hires.png",
        "notes": "Aquapolis standard print.",
    },
    {
        "card_name": "Vulpix (Reverse Holo)",
        "set_name": "Aquapolis",
        "card_number": "116/147",
        "release_year": 2003,
        "language": "English",
        "edition": "Reverse Holo",
        "rarity": "Common",
        "is_error": 0,
        "est_raw_price": 28.00,
        "est_grade10_price": 230.00,
        "image_url": "https://images.pokemontcg.io/ecard2/116_hires.png",
        "notes": "Aquapolis reverse holo variant.",
    },
    {
        "card_name": "Vulpix (Delta Species)",
        "set_name": "EX Dragon Frontiers",
        "card_number": "69/101",
        "release_year": 2006,
        "language": "English",
        "edition": "Unlimited",
        "rarity": "Common",
        "is_error": 0,
        "est_raw_price": 5.00,
        "est_grade10_price": 90.00,
        "image_url": "https://images.pokemontcg.io/ex15/69_hires.png",
        "notes": "Psychic type Delta Species Vulpix.",
    },
    {
        "card_name": "Vulpix (Delta Species Reverse Holo)",
        "set_name": "EX Dragon Frontiers",
        "card_number": "69/101",
        "release_year": 2006,
        "language": "English",
        "edition": "Reverse Holo",
        "rarity": "Common",
        "is_error": 0,
        "est_raw_price": 25.00,
        "est_grade10_price": 220.00,
        "image_url": "https://images.pokemontcg.io/ex15/69_hires.png",
        "notes": "Stamped EX Dragon Frontiers reverse holo.",
    },

    # --- Diamond & Pearl, Platinum, HGSS Era (2007-2011) ---
    {
        "card_name": "Vulpix",
        "set_name": "Platinum",
        "card_number": "102/127",
        "release_year": 2009,
        "language": "English",
        "edition": "Unlimited",
        "rarity": "Common",
        "is_error": 0,
        "est_raw_price": 2.00,
        "est_grade10_price": 45.00,
        "image_url": "https://images.pokemontcg.io/pl1/102_hires.png",
        "notes": "Platinum era.",
    },
    {
        "card_name": "Vulpix",
        "set_name": "HeartGold SoulSilver",
        "card_number": "87/123",
        "release_year": 2010,
        "language": "English",
        "edition": "Unlimited",
        "rarity": "Common",
        "is_error": 0,
        "est_raw_price": 3.00,
        "est_grade10_price": 55.00,
        "image_url": "https://images.pokemontcg.io/hgss1/87_hires.png",
        "notes": "HGSS classic border.",
    },
    {
        "card_name": "Vulpix (Reverse Holo)",
        "set_name": "HeartGold SoulSilver",
        "card_number": "87/123",
        "release_year": 2010,
        "language": "English",
        "edition": "Reverse Holo",
        "rarity": "Common",
        "is_error": 0,
        "est_raw_price": 12.00,
        "est_grade10_price": 110.00,
        "image_url": "https://images.pokemontcg.io/hgss1/87_hires.png",
        "notes": "HGSS mirror reverse foil.",
    },

    # --- Modern & Alolan Era (2016-Present) ---
    {
        "card_name": "Alolan Vulpix",
        "set_name": "Guardians Rising",
        "card_number": "21/145",
        "release_year": 2017,
        "language": "English",
        "edition": "Unlimited",
        "rarity": "Common",
        "is_error": 0,
        "est_raw_price": 1.00,
        "est_grade10_price": 35.00,
        "image_url": "https://images.pokemontcg.io/sm2/21_hires.png",
        "notes": "Iconic Beacon attack Alolan Vulpix.",
    },
    {
        "card_name": "Alolan Vulpix (Promo)",
        "set_name": "SM Black Star Promos",
        "card_number": "SM159",
        "release_year": 2018,
        "language": "English",
        "edition": "Promo",
        "rarity": "Promo",
        "is_error": 0,
        "est_raw_price": 5.00,
        "est_grade10_price": 60.00,
        "image_url": "https://images.pokemontcg.io/smp/SM159_hires.png",
        "notes": "Black Star Holo Promo.",
    },
    {
        "card_name": "Alolan Vulpix V",
        "set_name": "Silver Tempest",
        "card_number": "033/195",
        "release_year": 2022,
        "language": "English",
        "edition": "Unlimited",
        "rarity": "Ultra Rare",
        "is_error": 0,
        "est_raw_price": 2.50,
        "est_grade10_price": 45.00,
        "image_url": "https://images.pokemontcg.io/swsh12/33_hires.png",
        "notes": "Silver Tempest Ultra Rare V.",
    },
    {
        "card_name": "Alolan Vulpix V (Full Art)",
        "set_name": "Silver Tempest",
        "card_number": "173/195",
        "release_year": 2022,
        "language": "English",
        "edition": "Unlimited",
        "rarity": "Ultra Rare",
        "is_error": 0,
        "est_raw_price": 6.00,
        "est_grade10_price": 65.00,
        "image_url": "https://images.pokemontcg.io/swsh12/173_hires.png",
        "notes": "Full Art Ultra Rare.",
    },
    {
        "card_name": "Alolan Vulpix VSTAR",
        "set_name": "Silver Tempest",
        "card_number": "034/195",
        "release_year": 2022,
        "language": "English",
        "edition": "Unlimited",
        "rarity": "Holo Rare VSTAR",
        "is_error": 0,
        "est_raw_price": 3.00,
        "est_grade10_price": 45.00,
        "image_url": "https://images.pokemontcg.io/swsh12/34_hires.png",
        "notes": "VSTAR regular art.",
    },
    {
        "card_name": "Alolan Vulpix VSTAR (Rainbow Secret Rare)",
        "set_name": "Silver Tempest",
        "card_number": "197/195",
        "release_year": 2022,
        "language": "English",
        "edition": "Unlimited",
        "rarity": "Secret Rare",
        "is_error": 0,
        "est_raw_price": 12.00,
        "est_grade10_price": 75.00,
        "image_url": "https://images.pokemontcg.io/swsh12/197_hires.png",
        "notes": "Rainbow Secret Rare slab.",
    },
    {
        "card_name": "Vulpix",
        "set_name": "Scarlet & Violet 151",
        "card_number": "037/165",
        "release_year": 2023,
        "language": "English",
        "edition": "Unlimited",
        "rarity": "Common",
        "is_error": 0,
        "est_raw_price": 1.00,
        "est_grade10_price": 30.00,
        "image_url": "https://images.pokemontcg.io/sv3pt5/37_hires.png",
        "notes": "SV 151 standard.",
    },
    {
        "card_name": "Vulpix (Reverse Holo)",
        "set_name": "Scarlet & Violet 151",
        "card_number": "037/165",
        "release_year": 2023,
        "language": "English",
        "edition": "Reverse Holo",
        "rarity": "Common",
        "is_error": 0,
        "est_raw_price": 2.00,
        "est_grade10_price": 40.00,
        "image_url": "https://images.pokemontcg.io/sv3pt5/37_hires.png",
        "notes": "SV 151 Pokéball reverse holo pattern.",
    },

    # --- Japanese Exclusive & Special Promos ---
    {
        "card_name": "Vulpix (CoroCoro Comics Promo)",
        "set_name": "CoroCoro Comics (1996)",
        "card_number": "Promo",
        "release_year": 1996,
        "language": "Japanese",
        "edition": "Promo",
        "rarity": "Promo",
        "is_error": 0,
        "est_raw_price": 25.00,
        "est_grade10_price": 180.00,
        "image_url": "https://images.pokemontcg.io/base1/68_hires.png",
        "notes": "Glossy CoroCoro Japanese promo card.",
    },
    {
        "card_name": "Vulpix (Vending Series 1)",
        "set_name": "Vending Series 1 (Blue)",
        "card_number": "No Number",
        "release_year": 1998,
        "language": "Japanese",
        "edition": "Vending",
        "rarity": "Common",
        "is_error": 0,
        "est_raw_price": 20.00,
        "est_grade10_price": 160.00,
        "image_url": "https://images.pokemontcg.io/base1/68_hires.png",
        "notes": "Peel-off Japanese Vending Sheet release.",
    },
    {
        "card_name": "Vulpix (Vending Series 3)",
        "set_name": "Vending Series 3 (Green)",
        "card_number": "No Number",
        "release_year": 1998,
        "language": "Japanese",
        "edition": "Vending",
        "rarity": "Common",
        "is_error": 0,
        "est_raw_price": 28.00,
        "est_grade10_price": 210.00,
        "image_url": "https://images.pokemontcg.io/base1/68_hires.png",
        "notes": "Ooyama unique art Vending Series.",
    },
    {
        "card_name": "Vulpix (Pokémon Web)",
        "set_name": "Pokémon Web",
        "card_number": "015/048",
        "release_year": 2001,
        "language": "Japanese",
        "edition": "1st Edition",
        "rarity": "Common",
        "is_error": 0,
        "est_raw_price": 35.00,
        "est_grade10_price": 280.00,
        "image_url": "https://images.pokemontcg.io/base1/68_hires.png",
        "notes": "Rare Japanese Web series reprint with e-Card border.",
    },
    {
        "card_name": "Alolan Vulpix (Poncho-clad Pikachu Special Box)",
        "set_name": "SM-P Japanese Promos",
        "card_number": "037/SM-P",
        "release_year": 2017,
        "language": "Japanese",
        "edition": "Promo",
        "rarity": "Promo",
        "is_error": 0,
        "est_raw_price": 180.00,
        "est_grade10_price": 850.00,
        "image_url": "https://images.pokemontcg.io/smp/SM159_hires.png",
        "notes": "Pokémon Center exclusive Special Box promo.",
    },
]

SAMPLE_USER_COLLECTION = [
    {
        "card_name": "Vulpix",
        "set_name": "Base Set",
        "card_number": "68/102",
        "grading_company": "PSA",
        "grade": 10.0,
        "grade_label": "Gem Mint",
        "cert_number": "48291039",
        "purchase_price": 220.00,
        "purchase_date": "2023-05-12",
        "edition": "1st Edition",
        "language": "English",
        "is_error": 0,
        "error_type": None,
        "is_raw": 0,
        "image_url": "https://images.pokemontcg.io/base1/68_hires.png",
        "notes": "Grail slab. 1st Edition Base Set Gem Mint 10.",
    },
    {
        "card_name": "Vulpix (Shadowless)",
        "set_name": "Base Set",
        "card_number": "68/102",
        "grading_company": "PSA",
        "grade": 9.0,
        "grade_label": "Mint",
        "cert_number": "59102934",
        "purchase_price": 45.00,
        "purchase_date": "2023-08-19",
        "edition": "Shadowless",
        "language": "English",
        "is_error": 0,
        "error_type": None,
        "is_raw": 0,
        "image_url": "https://images.pokemontcg.io/base1/68_hires.png",
        "notes": "Clean shadowless copy.",
    },
    {
        "card_name": "Erika's Vulpix",
        "set_name": "Gym Heroes",
        "card_number": "49/132",
        "grading_company": "CGC",
        "grade": 9.5,
        "grade_label": "Gem Mint",
        "cert_number": "14093820",
        "purchase_price": 60.00,
        "purchase_date": "2023-11-04",
        "edition": "1st Edition",
        "language": "English",
        "is_error": 0,
        "error_type": None,
        "is_raw": 0,
        "image_url": "https://images.pokemontcg.io/gym1/49_hires.png",
        "notes": "CGC with subgrades.",
    },
    {
        "card_name": "Light Vulpix",
        "set_name": "Neo Destiny",
        "card_number": "80/105",
        "grading_company": "CGC",
        "grade": 10.0,
        "grade_label": "Pristine 10",
        "cert_number": "67392019",
        "purchase_price": 280.00,
        "purchase_date": "2024-02-14",
        "edition": "1st Edition",
        "language": "English",
        "is_error": 0,
        "error_type": None,
        "is_raw": 0,
        "image_url": "https://images.pokemontcg.io/neo4/80_hires.png",
        "notes": "Gold label CGC Pristine 10.",
    },
    {
        "card_name": "Vulpix (HP 50 Error)",
        "set_name": "Base Set",
        "card_number": "68/102",
        "grading_company": "RAW",
        "grade": 0.0,
        "grade_label": "Raw Single",
        "cert_number": "",
        "purchase_price": 30.00,
        "purchase_date": "2024-03-18",
        "edition": "Unlimited",
        "language": "English",
        "is_error": 1,
        "error_type": "HP 50 Error",
        "is_raw": 1,
        "image_url": "https://images.pokemontcg.io/base1/68_hires.png",
        "notes": "Near Mint raw copy of HP 50 error.",
    },
    {
        "card_name": "Alolan Vulpix VSTAR (Rainbow Secret Rare)",
        "set_name": "Silver Tempest",
        "card_number": "197/195",
        "grading_company": "BGS",
        "grade": 10.0,
        "grade_label": "Black Label 10",
        "cert_number": "00149201",
        "purchase_price": 140.00,
        "purchase_date": "2024-06-22",
        "edition": "Unlimited",
        "language": "English",
        "is_error": 0,
        "error_type": None,
        "is_raw": 0,
        "image_url": "https://images.pokemontcg.io/swsh12/197_hires.png",
        "notes": "BGS Quad 10 Black Label.",
    },
]


def seed_database_if_empty(db_path: Optional[str] = None) -> None:
    """Populates database with Master Set Catalog, collection cards, and baseline multi-tier sales."""
    # 1. Bulk Upsert Master Set Catalog
    print("[Seed] Synchronizing Master Set Catalog...")
    bulk_upsert_master_catalog(MASTER_VULPIX_CATALOG, db_path=db_path)

    # 2. Seed Personal Collection
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM my_collection;")
        collection_count = cursor.fetchone()[0]

    if collection_count == 0:
        print("[Seed] Populating initial personal collection...")
        for card in SAMPLE_USER_COLLECTION:
            insert_collection_card(card, db_path=db_path)

    # 3. Seed Market Sales History (Multi-tier: Raw and Grade 10)
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM market_sales;")
        sales_count = cursor.fetchone()[0]

    if sales_count == 0:
        print("[Seed] Populating baseline market sales for Raw and Grade 10 slabs...")
        now = datetime.now()
        listing_counter = 5000

        for card in MASTER_VULPIX_CATALOG:
            # Generate sales for Raw condition
            raw_base = card["est_raw_price"]
            for i in range(random.randint(4, 7)):
                days_ago = random.randint(1, 90)
                sale_time = now - timedelta(days=days_ago)
                fluct = random.uniform(-0.15, 0.15)
                price = round(max(0.99, raw_base * (1.0 + fluct)), 2)
                shipping = 0.0 if random.random() > 0.4 else 1.99
                total_price = round(price + shipping, 2)
                listing_counter += 1

                discount_pct = round(((raw_base - total_price) / raw_base) * 100, 1) if raw_base > 0 else 0
                if discount_pct >= 30:
                    rating = "amazing_deal"
                    rationale = f"Raw copy listed {discount_pct:.1f}% below market average (${raw_base:.2f})."
                elif discount_pct >= 15:
                    rating = "great_deal"
                    rationale = f"Great raw single price vs market (${raw_base:.2f})."
                elif discount_pct >= 5:
                    rating = "good_deal"
                    rationale = f"Solid discount on raw single."
                else:
                    rating = "avoid_price"
                    rationale = f"Priced at or above typical raw market value."

                insert_market_sale({
                    "listing_id": f"seed_raw_{listing_counter}",
                    "title": f"Pokemon Card {card['card_name']} {card['set_name']} #{card['card_number']} {card['edition']} Raw",
                    "card_name": card["card_name"],
                    "grading_company": "RAW",
                    "grade": None,
                    "grade_label": "Raw Single",
                    "condition_type": "Raw",
                    "edition": card["edition"],
                    "language": card["language"],
                    "is_error": card["is_error"],
                    "price": price,
                    "shipping_cost": shipping,
                    "total_price": total_price,
                    "listing_url": f"https://www.ebay.com/itm/{listing_counter}",
                    "image_url": card["image_url"],
                    "listing_type": "Buy It Now",
                    "deal_rating": rating,
                    "fair_value_estimate": raw_base,
                    "discount_percentage": discount_pct,
                    "ai_rationale": rationale,
                    "sale_date": sale_time.strftime("%Y-%m-%d"),
                }, db_path=db_path)

            # Generate sales for Grade 10 Slabs
            grade10_base = card["est_grade10_price"]
            for co in ["PSA", "CGC", "BGS"]:
                for i in range(random.randint(3, 6)):
                    days_ago = random.randint(1, 90)
                    sale_time = now - timedelta(days=days_ago)
                    fluct = random.uniform(-0.12, 0.18)

                    # Pristine / Black Label premium
                    grade_label = "Gem Mint"
                    multiplier = 1.0
                    if co == "BGS" and random.random() > 0.8:
                        grade_label = "Black Label 10"
                        multiplier = 2.5
                    elif co == "CGC" and random.random() > 0.7:
                        grade_label = "Pristine 10"
                        multiplier = 1.35

                    target_fair = round(grade10_base * multiplier, 2)
                    price = round(target_fair * (1.0 + fluct), 2)
                    shipping = 0.0 if random.random() > 0.5 else 4.99
                    total_price = round(price + shipping, 2)
                    listing_counter += 1

                    discount_pct = round(((target_fair - total_price) / target_fair) * 100, 1)
                    if discount_pct >= 30:
                        rating = "amazing_deal"
                        rationale = f"🔥 {grade_label} {co} 10 listed {discount_pct:.1f}% below fair market estimate of ${target_fair:.2f}."
                    elif discount_pct >= 15:
                        rating = "great_deal"
                        rationale = f"⭐ Great value on {co} 10 slab vs market (${target_fair:.2f})."
                    elif discount_pct >= 5:
                        rating = "good_deal"
                        rationale = f"✨ Modest discount on {co} 10."
                    else:
                        rating = "avoid_price"
                        rationale = f"Priced above market average (${target_fair:.2f})."

                    insert_market_sale({
                        "listing_id": f"seed_slab_{listing_counter}",
                        "title": f"{card['card_name']} {card['set_name']} #{card['card_number']} {co} 10 {grade_label} Graded",
                        "card_name": card["card_name"],
                        "grading_company": co,
                        "grade": 10.0,
                        "grade_label": grade_label,
                        "condition_type": "Graded",
                        "edition": card["edition"],
                        "language": card["language"],
                        "is_error": card["is_error"],
                        "price": price,
                        "shipping_cost": shipping,
                        "total_price": total_price,
                        "listing_url": f"https://www.ebay.com/itm/{listing_counter}",
                        "image_url": card["image_url"],
                        "listing_type": "Buy It Now",
                        "deal_rating": rating,
                        "fair_value_estimate": target_fair,
                        "discount_percentage": discount_pct,
                        "ai_rationale": rationale,
                        "sale_date": sale_time.strftime("%Y-%m-%d"),
                    }, db_path=db_path)

        print("[Seed] Seed data successfully generated.")
