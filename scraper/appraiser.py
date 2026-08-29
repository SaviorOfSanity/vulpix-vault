"""
AI Appraisal module for Pokémon card listings using Google Gemini API.
Evaluates current listing price against the last 10 historical comparable sales.
"""

import json
import os
import re
import statistics
from typing import Any, Dict, List, Optional

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


def statistical_appraisal_fallback(
    listing: Dict[str, Any], comparables: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Deterministic rule-based appraisal fallback when Gemini API key is unavailable or fails.
    Calculates median/mean from recent comparables.
    """
    total_price = listing.get("total_price", listing.get("price", 0.0))

    if comparables:
        comp_prices = [c["total_price"] for c in comparables if c.get("total_price", 0) > 0]
    else:
        comp_prices = []

    if not comp_prices:
        # No comparables available in database yet
        return {
            "deal_rating": "good_deal" if total_price < 35.0 else "avoid_price",
            "fair_value_estimate": round(total_price * 1.05, 2),
            "discount_percentage": 5.0,
            "rationale": "No previous sales on record. Baseline estimate established from listing price.",
        }

    median_price = statistics.median(comp_prices)
    mean_price = statistics.mean(comp_prices)
    fair_value = round((median_price * 0.6) + (mean_price * 0.4), 2)

    if fair_value <= 0:
        fair_value = total_price

    discount_pct = round(((fair_value - total_price) / fair_value) * 100, 1)

    if discount_pct >= 25.0:
        deal_rating = "amazing_deal"
        rationale = f"Listing at ${total_price:.2f} is {discount_pct:.1f}% below the market fair value estimate of ${fair_value:.2f} (based on {len(comp_prices)} comparable sales)."
    elif discount_pct >= 10.0:
        deal_rating = "good_deal"
        rationale = f"Listing at ${total_price:.2f} is {discount_pct:.1f}% below market fair value of ${fair_value:.2f}."
    else:
        deal_rating = "avoid_price"
        rationale = f"Listing at ${total_price:.2f} is at or above estimated fair market value of ${fair_value:.2f}."

    return {
        "deal_rating": deal_rating,
        "fair_value_estimate": fair_value,
        "discount_percentage": discount_pct,
        "rationale": rationale,
    }


def clean_json_response(text: str) -> Optional[Dict[str, Any]]:
    """Extract and parse JSON from model output text, stripping markdown code blocks."""
    # Match ```json ... ``` or raw {...}
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        raw_json = match.group(1)
    else:
        raw_match = re.search(r"\{.*\}", text, re.DOTALL)
        raw_json = raw_match.group(0) if raw_match else text

    try:
        return json.loads(raw_json)
    except Exception:
        return None


def appraise_listing(
    listing: Dict[str, Any],
    comparables: List[Dict[str, Any]],
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Appraise a graded Pokémon card listing using Gemini AI (or statistical fallback).
    
    Returns:
        Dict with keys: deal_rating ('amazing_deal'|'good_deal'|'avoid_price'),
        fair_value_estimate (float), discount_percentage (float), rationale (str).
    """
    key = api_key or os.getenv("GEMINI_API_KEY", "")

    if not GENAI_AVAILABLE or not key or key == "your_gemini_api_key_here":
        return statistical_appraisal_fallback(listing, comparables)

    # Format comparable data for prompt
    comp_summary = []
    for c in comparables[:10]:
        comp_summary.append(
            f"- {c.get('card_name', 'Vulpix')} {c.get('grading_company', 'PSA')} {c.get('grade', 10)} sold/listed for ${c.get('total_price', 0):.2f}"
        )
    comps_text = "\n".join(comp_summary) if comp_summary else "None available yet in local database."

    prompt = f"""
You are an expert vintage and modern Pokémon TCG market analyst specializing in graded slabs (PSA, CGC, BGS).
Evaluate this new eBay listing against the recent comparable sales:

NEW LISTING:
- Title: {listing.get('title')}
- Card: {listing.get('card_name')}
- Grading Company: {listing.get('grading_company')}
- Grade: {listing.get('grade')}
- Listed Price: ${listing.get('price', 0):.2f}
- Shipping: ${listing.get('shipping_cost', 0):.2f}
- Total Price: ${listing.get('total_price', 0):.2f}

RECENT COMPARABLE SALES (Last 10 records):
{comps_text}

TASK:
1. Estimate the true fair market value for this card in this specific slab/grade.
2. Calculate the discount percentage (or premium).
3. Classify into EXACTLY one of: "amazing_deal" (>=20% below fair market value), "good_deal" (5-19% below fair value), or "avoid_price" (overpriced or at fair value).
4. Provide a 1-2 sentence concise rationale explaining your reasoning.

Respond ONLY with valid JSON in this exact structure:
{{
  "deal_rating": "amazing_deal" | "good_deal" | "avoid_price",
  "fair_value_estimate": 120.00,
  "discount_percentage": 25.5,
  "rationale": "Brief 1-2 sentence rationale."
}}
"""

    try:
        genai.configure(api_key=key)
        # Try gemini-2.5-flash or fallback model
        model_name = "gemini-2.5-flash"
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
        except Exception:
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)

        parsed = clean_json_response(response.text)
        if parsed and "deal_rating" in parsed:
            # Validate deal rating enum
            rating = parsed.get("deal_rating", "").lower()
            if rating not in ["amazing_deal", "good_deal", "avoid_price"]:
                rating = "good_deal" if parsed.get("discount_percentage", 0) > 10 else "avoid_price"

            return {
                "deal_rating": rating,
                "fair_value_estimate": float(parsed.get("fair_value_estimate", listing.get("total_price", 0))),
                "discount_percentage": float(parsed.get("discount_percentage", 0.0)),
                "rationale": parsed.get("rationale", "AI appraisal completed."),
            }
    except Exception as e:
        print(f"[Appraiser] Gemini API error: {e}. Utilizing fallback calculation.")

    return statistical_appraisal_fallback(listing, comparables)
