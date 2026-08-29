"""
Push notification client for Gotify server.
Sends high-priority alerts when an 'amazing_deal' is discovered.
"""

import os
from typing import Any, Dict, Optional
import requests


def send_gotify_alert(
    listing: Dict[str, Any],
    appraisal: Dict[str, Any],
    gotify_url: Optional[str] = None,
    gotify_token: Optional[str] = None,
    priority: int = 8,
) -> bool:
    """
    Sends a push notification to Gotify with card details, fair value estimate, and click action.
    """
    base_url = (gotify_url or os.getenv("GOTIFY_URL", "http://gotify:80")).rstrip("/")
    token = gotify_token or os.getenv("GOTIFY_APP_TOKEN", "")

    if not token or token == "your_gotify_app_token_here":
        print("[Notifier] Info: GOTIFY_APP_TOKEN not configured. Skipping push notification.")
        return False

    title = f"🔥 Amazing Vulpix Deal: {listing.get('card_name', 'Vulpix')} {listing.get('grading_company', '')} {listing.get('grade', '')}"
    
    total_price = listing.get("total_price", listing.get("price", 0.0))
    fair_value = appraisal.get("fair_value_estimate", 0.0)
    discount = appraisal.get("discount_percentage", 0.0)
    rationale = appraisal.get("rationale") or appraisal.get("ai_rationale", "")
    listing_url = listing.get("listing_url", "")

    message_body = (
        f"**Card:** {listing.get('title')}\n"
        f"**Listed Price:** ${total_price:.2f}\n"
        f"**Estimated Fair Value:** ${fair_value:.2f} ({discount:.1f}% OFF)\n\n"
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
        url = f"{base_url}/message"
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            print(f"[Notifier] Successfully sent Gotify notification for listing {listing.get('listing_id')}")
            return True
        else:
            print(f"[Notifier] Gotify error (HTTP {response.status_code}): {response.text}")
            return False
    except Exception as e:
        print(f"[Notifier] Failed to connect to Gotify server at {base_url}: {e}")
        return False
