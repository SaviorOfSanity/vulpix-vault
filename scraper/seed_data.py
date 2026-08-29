"""
Seed data module for initializing The Vulpix Vault with sample collection and historical sales.
Ensures the dashboard has baseline data and historical charts immediately on fresh deploy.
"""

from datetime import datetime, timedelta
import random
from typing import Optional
from db import get_db_connection, insert_collection_card, insert_market_sale

SAMPLE_COLLECTION = [
    {
        "card_name": "Base Set 1st Edition Vulpix #68",
        "set_name": "Base Set (1999)",
        "card_number": "68/102",
        "grading_company": "PSA",
        "grade": 10.0,
        "cert_number": "48291039",
        "purchase_price": 220.00,
        "purchase_date": "2023-05-12",
        "image_url": "https://images.pokemontcg.io/base1/68_hires.png",
        "notes": "Grail slab. 1st Edition Base Set Gem Mint 10.",
    },
    {
        "card_name": "Base Set Shadowless Vulpix #68",
        "set_name": "Base Set (1999)",
        "card_number": "68/102",
        "grading_company": "PSA",
        "grade": 9.0,
        "cert_number": "59102934",
        "purchase_price": 45.00,
        "purchase_date": "2023-08-19",
        "image_url": "https://images.pokemontcg.io/base1/68_hires.png",
        "notes": "Clean shadowless copy.",
    },
    {
        "card_name": "Erika's Vulpix (Gym Heroes)",
        "set_name": "Gym Heroes (2000)",
        "card_number": "49/132",
        "grading_company": "CGC",
        "grade": 9.5,
        "cert_number": "14093820",
        "purchase_price": 60.00,
        "purchase_date": "2023-11-04",
        "image_url": "https://images.pokemontcg.io/gym1/49_hires.png",
        "notes": "Old blue CGC label with subgrades.",
    },
    {
        "card_name": "Light Vulpix (Neo Destiny)",
        "set_name": "Neo Destiny (2002)",
        "card_number": "80/105",
        "grading_company": "PSA",
        "grade": 10.0,
        "cert_number": "67392019",
        "purchase_price": 185.00,
        "purchase_date": "2024-02-14",
        "image_url": "https://images.pokemontcg.io/neo4/80_hires.png",
        "notes": "Vintage Japanese/English Neo era artwork.",
    },
    {
        "card_name": "Vulpix Japanese CoroCoro Promo",
        "set_name": "CoroCoro Comics (1996)",
        "card_number": "Promo",
        "grading_company": "PSA",
        "grade": 9.0,
        "cert_number": "72918392",
        "purchase_price": 75.00,
        "purchase_date": "2024-04-10",
        "image_url": "https://images.pokemontcg.io/base1/68_hires.png",
        "notes": "Glossy CoroCoro Japanese release.",
    },
    {
        "card_name": "Alolan Vulpix VSTAR",
        "set_name": "Silver Tempest (2022)",
        "card_number": "197/195",
        "grading_company": "BGS",
        "grade": 9.5,
        "cert_number": "00149201",
        "purchase_price": 40.00,
        "purchase_date": "2024-06-22",
        "image_url": "https://images.pokemontcg.io/swsh12/197_hires.png",
        "notes": "Rainbow Secret Rare slab.",
    },
]

CARD_BASE_PRICES = {
    ("Base Set 1st Edition Vulpix #68", "PSA", 10.0): 240.0,
    ("Base Set 1st Edition Vulpix #68", "PSA", 9.0): 85.0,
    ("Base Set Shadowless Vulpix #68", "PSA", 9.0): 50.0,
    ("Base Set Shadowless Vulpix #68", "PSA", 10.0): 130.0,
    ("Erika's Vulpix (Gym Heroes)", "CGC", 9.5): 65.0,
    ("Erika's Vulpix (Gym Heroes)", "PSA", 10.0): 95.0,
    ("Light Vulpix (Neo Destiny)", "PSA", 10.0): 195.0,
    ("Light Vulpix (Neo Destiny)", "PSA", 9.0): 70.0,
    ("Vulpix Japanese CoroCoro Promo", "PSA", 9.0): 80.0,
    ("Alolan Vulpix VSTAR", "BGS", 9.5): 42.0,
    ("Alolan Vulpix VSTAR", "PSA", 10.0): 55.0,
}


def seed_database_if_empty(db_path: Optional[str] = None) -> None:
    """Populates database with sample collection cards and historical market sales if tables are empty."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM my_collection;")
        collection_count = cursor.fetchone()[0]

    # Seed Collection
    if collection_count == 0:
        print("[Seed] Populating initial personal collection...")
        for card in SAMPLE_COLLECTION:
            insert_collection_card(card, db_path=db_path)

    # Seed Market Sales History
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM market_sales;")
        sales_count = cursor.fetchone()[0]

    if sales_count == 0:
        print("[Seed] Populating baseline market sales history for analytics...")
        now = datetime.now()
        listing_counter = 1000

        for (card_name, grading_co, grade), base_val in CARD_BASE_PRICES.items():
            # Generate 8-12 historical data points across the past 90 days
            num_points = random.randint(8, 12)
            for i in range(num_points):
                days_ago = int((90 / num_points) * (num_points - i) + random.uniform(-2, 2))
                days_ago = max(1, days_ago)
                sale_time = now - timedelta(days=days_ago)
                date_str = sale_time.strftime("%Y-%m-%d")

                # Price trend fluctuation (+- 15%)
                fluctuation = random.uniform(-0.12, 0.15)
                # Gradual historical trend
                trend_factor = 1.0 + ((90 - days_ago) / 90.0) * 0.08
                price = round(base_val * trend_factor * (1.0 + fluctuation), 2)
                shipping = 0.0 if random.random() > 0.4 else 4.99
                total_price = round(price + shipping, 2)
                listing_counter += 1

                # Deal appraisal simulation
                fair_val = round(base_val * trend_factor, 2)
                discount_pct = round(((fair_val - total_price) / fair_val) * 100, 1)

                if discount_pct >= 20.0:
                    deal_rating = "amazing_deal"
                    rationale = f"Priced significantly below market baseline of ${fair_val:.2f}."
                elif discount_pct >= 8.0:
                    deal_rating = "good_deal"
                    rationale = f"Fair value is estimated at ${fair_val:.2f}."
                else:
                    deal_rating = "avoid_price"
                    rationale = f"Priced in line with or above market value (${fair_val:.2f})."

                sale_data = {
                    "listing_id": f"seed_{listing_counter}",
                    "title": f"{card_name} {grading_co} {grade} Graded Pokemon Card",
                    "card_name": card_name,
                    "grading_company": grading_co,
                    "grade": grade,
                    "price": price,
                    "shipping_cost": shipping,
                    "total_price": total_price,
                    "listing_url": f"https://www.ebay.com/itm/{listing_counter}",
                    "image_url": "https://images.pokemontcg.io/base1/68_hires.png",
                    "listing_type": "Buy It Now" if random.random() > 0.3 else "Auction",
                    "deal_rating": deal_rating,
                    "fair_value_estimate": fair_val,
                    "discount_percentage": discount_pct,
                    "ai_rationale": rationale,
                    "sale_date": date_str,
                }
                insert_market_sale(sale_data, db_path=db_path)

        print("[Seed] Seed data successfully generated.")
