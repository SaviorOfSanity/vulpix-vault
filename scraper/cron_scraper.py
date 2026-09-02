"""
Main automation daemon for The Vulpix Vault.
Runs APScheduler to scrape eBay for graded Vulpix cards, raw singles, and error cards,
appraises them via Gemini AI, stores data in SQLite, and sends Gotify alerts for top deals.
"""

import os
import signal
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from db import (
    get_recent_comparables,
    init_db,
    insert_market_sale,
    is_listing_recorded,
)
from ebay import scrape_ebay_listings
from appraiser import appraise_listing
from notifier import send_gotify_alert
from seed_data import seed_database_if_empty

from apscheduler.schedulers.blocking import BlockingScheduler

SEARCH_QUERIES = [
    "Vulpix PSA 10",
    "Vulpix CGC 10 Pristine",
    "Vulpix CGC 10 Gem Mint",
    "Alolan Vulpix PSA 10",
    "Alolan Vulpix CGC 10 Pristine",
    "Vulpix BGS 10 Black Label",
    "Vulpix 1st Edition (PSA 10, CGC 10)",
    "Vulpix Shadowless (PSA 10, CGC 10)",
    "Vulpix (PSA 10, CGC 10, Pristine 10)",
]


def run_scrape_and_appraisal_cycle() -> None:
    """Executes a full scraping, appraisal, and alerting cycle across multiple target queries."""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting multi-tier scrape cycle...")

    new_count = 0
    amazing_deals_count = 0
    great_deals_count = 0

    for query in SEARCH_QUERIES:
        print(f"[Scraper] Querying: '{query}'")
        try:
            listings = scrape_ebay_listings(query)
            print(f"[Scraper] Found {len(listings)} results for '{query}'")

            for item in listings:
                listing_id = item["listing_id"]

                if is_listing_recorded(listing_id):
                    continue

                new_count += 1
                cond_str = (
                    f"{item.get('grading_company')} {item.get('grade_label')}"
                    if item.get("condition_type") == "Graded"
                    else "Raw"
                )
                print(f"[Scraper] New listing: {item['title']} (${item['total_price']:.2f}) [{cond_str}]")

                # Fetch recent comparable sales for appraisal context
                comps = get_recent_comparables(
                    card_name=item["card_name"],
                    grading_company=item["grading_company"],
                    grade=item["grade"],
                    condition_type=item["condition_type"],
                    limit=10,
                )

                # Gemini AI Appraisal
                appraisal = appraise_listing(item, comps)
                item["deal_rating"] = appraisal.get("deal_rating", "unrated")
                item["fair_value_estimate"] = appraisal.get("fair_value_estimate")
                item["discount_percentage"] = appraisal.get("discount_percentage")
                item["ai_rationale"] = appraisal.get("rationale")
                item["sale_date"] = datetime.now().strftime("%Y-%m-%d")

                print(
                    f"[Appraiser] Rating: {item['deal_rating'].upper()} | "
                    f"Est. Value: ${item['fair_value_estimate']} | "
                    f"Discount: {item['discount_percentage']}%"
                )

                # Store in SQLite database
                insert_market_sale(item)

                # Trigger Gotify Push Notification for Amazing and Great Deals
                if item["deal_rating"] in ["amazing_deal", "great_deal"]:
                    if item["deal_rating"] == "amazing_deal":
                        amazing_deals_count += 1
                    else:
                        great_deals_count += 1
                    send_gotify_alert(item, appraisal)

        except Exception as e:
            print(f"[Scraper] Error during query '{query}': {e}")

    print(
        f"\n[Scraper] Cycle completed: {new_count} new listings recorded, "
        f"{amazing_deals_count} amazing deals and {great_deals_count} great deals found."
    )


def main() -> None:
    print("=" * 60)
    print("  The Vulpix Vault - Background Scraper & AI Appraiser")
    print("=" * 60)

    # Initialize SQLite schema and seed baseline data if empty
    init_db()
    seed_database_if_empty()

    interval_hours_str = os.getenv("SCRAPE_INTERVAL_HOURS", "24")
    try:
        interval_hours = float(interval_hours_str)
    except ValueError:
        interval_hours = 24.0

    print(f"[Scheduler] Configured scrape interval: {interval_hours} hours.")

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_scrape_and_appraisal_cycle,
        "interval",
        hours=interval_hours,
        id="vulpix_scraper_job",
        next_run_time=datetime.now(),
    )

    def handle_shutdown(signum, frame):
        print("\n[Scheduler] Shutting down scraper daemon gracefully...")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    print("[Scheduler] Starting scheduler loop. Press Ctrl+C to exit.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
