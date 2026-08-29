"""
Push notification client for Gotify server.
Sends high-priority alerts when an 'amazing_deal' or 'great_deal' is discovered,
as well as Priority 10 urgent alerts for eBay Sniper Watchlist targets closing soon.
"""

import os
from typing import Any, Dict, Optional
import requests


def send_gotify_alert(
    listing: Dict[str, Any],
    appraisal: Dict[str, Any],
    gotify_url: Optional[str] = None,
    gotify_token: Optional[str] = None,
) -> bool:
    """
    Sends a push notification to Gotify with card details, condition/grade, fair value estimate, and click action.
    """
    base_url = (gotify_url or os.getenv("GOTIFY_URL", "http://10.0.0.48")).rstrip("/")
    token = gotify_token or os.getenv("GOTIFY_APP_TOKEN", "")
    if not token or not token.strip():
        print("[Notifier] Info: GOTIFY_APP_TOKEN not configured. Skipping push notification.")
        return False

    rating = appraisal.get("deal_rating", "good_deal")
    priority = 8 if rating == "amazing_deal" else 6

    condition_info = (
        f"{listing.get('grading_company', '')} {listing.get('grade_label', '')}"
        if listing.get("condition_type") == "Graded"
        else "Raw Single"
    )

    emoji = "🔥" if rating == "amazing_deal" else "⭐"
    title = f"{emoji} {rating.replace('_', ' ').title()}: {listing.get('card_name', 'Vulpix')} ({condition_info})"

    total_price = listing.get("total_price", listing.get("price", 0.0))
    fair_value = appraisal.get("fair_value_estimate", 0.0)
    discount = appraisal.get("discount_percentage", 0.0)
    rationale = appraisal.get("rationale") or appraisal.get("ai_rationale", "")
    listing_url = listing.get("listing_url", "")
    edition = listing.get("edition", "Unlimited")
    language = listing.get("language", "English")

    message_body = (
        f"**Card:** {listing.get('title')}\n"
        f"**Condition:** {condition_info} • {edition} ({language})\n"
        f"**Listed Price:** ${total_price:.2f}\n"
        f"**Est. Fair Value:** ${fair_value:.2f} ({discount:+.1f}% OFF)\n\n"
        f"**AI Appraisal:** {rationale}\n\n"
        f"[View eBay Listing]({listing_url})"
    )

    payload = {
        "title": title,
        "message": message_body,
        "priority": priority,
        "extras": {
            "client::notification": {
                "click": {"url": listing_url}
            },
            "client::display": {
                "contentType": "text/markdown"
            }
        }
    }

    headers = {
        "X-Gotify-Key": token,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(f"{base_url}/message", json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            print(f"[Notifier] Sent Gotify alert: '{title}' to {base_url}")
            return True
        else:
            print(f"[Notifier] Failed to send Gotify alert. Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        print(f"[Notifier] Gotify connection error to {base_url}: {e}")
        return False


def send_sniper_urgent_alert(
    sniper_item: Dict[str, Any],
    minutes_left: int = 10,
    gotify_url: Optional[str] = None,
    gotify_token: Optional[str] = None,
) -> bool:
    """
    Sends a Priority 10 urgent Gotify notification for an eBay auction nearing end under target price.
    """
    base_url = (gotify_url or os.getenv("GOTIFY_URL", "http://10.0.0.48")).rstrip("/")
    token = gotify_token or os.getenv("GOTIFY_APP_TOKEN", "")
    if not token or not token.strip():
        return False

    title = f"🚨 SNIPER ALERT: {sniper_item.get('card_name', 'Vulpix')} Closes in ~{minutes_left}m!"
    curr_bid = float(sniper_item.get("current_bid", 0.0))
    max_bid = float(sniper_item.get("custom_max_bid") or sniper_item.get("max_calculated_bid") or 0.0)
    listing_url = sniper_item.get("listing_url", "")

    message_body = (
        f"**Target Auction:** {sniper_item.get('title')}\n"
        f"**Current Bid:** ${curr_bid:.2f}\n"
        f"**Your Bid Cap:** ${max_bid:.2f}\n"
        f"**Status:** 🟢 Under Cap! Ready to snipe.\n\n"
        f"[⚡ Place Your Bid on eBay Now]({listing_url})"
    )

    payload = {
        "title": title,
        "message": message_body,
        "priority": 10,
        "extras": {
            "client::notification": {
                "click": {"url": listing_url}
            },
            "client::display": {
                "contentType": "text/markdown"
            }
        }
    }

    headers = {
        "X-Gotify-Key": token,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(f"{base_url}/message", json=payload, headers=headers, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"[Notifier] Sniper Gotify error: {e}")
        return False
