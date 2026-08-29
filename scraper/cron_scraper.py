"""
Main automation daemon for The Vulpix Vault.
Runs APScheduler to scrape eBay for graded Vulpix cards, appraises them via Gemini AI,
stores data in SQLite, and sends Gotify push alerts for amazing deals.
"""

import os
import signal
import sys
import time
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


def run_scrape_and_appraisal_cycle() -> None:
    """Executes a full scraping, appraisal, and alerting cycle."""
    search_query = os.getenv("EBAY_SEARCH_QUERY", "Vulpix graded (PSA, CGC, BGS)")
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting scrape cycle for: '{search_query}'")

    try:
        listings = scrape_ebay_listings(search_query)
        print(f"[Scraper] Found {len(listings)} listings from eBay search.")

        new_count = 0
        amazing_deals_count = 0

        for item in listings:
            listing_id = item["listing_id"]

            if is_listing_recorded(listing_id):
                continue

            new_count += 1
            print(f"\n[Scraper] Analyzing new listing: {item['title']} (${item['total_price']:.2f})")

            # Fetch recent comparable sales for appraisal context
            comps = get_recent_comparables(
                card_name=item["card_name"],
                grading_company=item["grading_company"],
                grade=item["grade"],
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

            # Trigger Gotify Push Notification for Amazing Deals
            if item["deal_rating"] == "amazing_deal":
                amazing_deals_count += 1
                send_gotify_alert(item, appraisal)

        print(
            f"\n[Scraper] Cycle finished: {new_count} new listings recorded, "
            f"{amazing_deals_count} amazing deals notified."
        )

    except Exception as e:
        print(f"[Scraper] Error in scraping cycle: {e}")


def main() -> None:
    print("=" * 60)
    print("  The Vulpix Vault - Background Scraper & AI Appraiser")
    print("=" * 60)

    # Initialize SQLite schema and seed baseline data if empty
    init_db()
    seed_database_if_empty()

    # Determine interval (default: 24 hours)
    interval_hours_str = os.getenv("SCRAPE_INTERVAL_HOURS", "24")
    try:
        interval_hours = float(interval_hours_str)
    except ValueError:
        interval_hours = 24.0

    print(f"[Scheduler] Configured scrape interval: {interval_hours} hours.")

    # Initialize APScheduler
    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_scrape_and_appraisal_cycle,
        "interval",
        hours=interval_hours,
        id="vulpix_scraper_job",
        next_run_time=datetime.now(),  # Run immediately upon start
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
