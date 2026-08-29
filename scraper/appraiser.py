"""
AI Appraisal module for Pokémon cards using Google Gemini API.
Evaluates Raw cards and Grade 10 slabs (Gem Mint, Pristine, Black Label)
cross-referenced with recent eBay comparables, PriceCharting benchmarks, and PSA/CGC Population rarity.
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
    listing: Dict[str, Any],
    comparables: List[Dict[str, Any]],
    pricecharting_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Deterministic rule-based appraisal fallback when Gemini API key is unavailable or fails.
    Fuses eBay historical comps with PriceCharting benchmark prices.
    """
    total_price = listing.get("total_price", listing.get("price", 0.0))
    condition_type = listing.get("condition_type", "Graded")
    grade_label = listing.get("grade_label", "Gem Mint")

    comp_prices = [c["total_price"] for c in comparables if c.get("total_price", 0) > 0] if comparables else []

    pc_benchmark = 0.0
    if pricecharting_data:
        if condition_type == "Raw":
            pc_benchmark = float(pricecharting_data.get("pricecharting_raw") or 0.0)
        else:
            pc_benchmark = float(pricecharting_data.get("pricecharting_grade10") or 0.0)

    if comp_prices and pc_benchmark > 0:
        median_price = statistics.median(comp_prices)
        fair_value = round((median_price * 0.5) + (pc_benchmark * 0.5), 2)
    elif comp_prices:
        median_price = statistics.median(comp_prices)
        mean_price = statistics.mean(comp_prices)
        fair_value = round((median_price * 0.6) + (mean_price * 0.4), 2)
    elif pc_benchmark > 0:
        fair_value = pc_benchmark
    else:
        default_val = 15.0 if condition_type == "Raw" else 65.0
        if "Black Label" in grade_label:
            default_val = 200.0
        elif "Pristine" in grade_label:
            default_val = 110.0
        fair_value = default_val

    if fair_value <= 0:
        fair_value = total_price

    discount_pct = round(((fair_value - total_price) / fair_value) * 100, 1)

    if discount_pct >= 30.0:
        deal_rating = "amazing_deal"
        rationale = f"🔥 Amazing Deal: Listed at ${total_price:.2f} is {discount_pct:.1f}% below fair market benchmark of ${fair_value:.2f}."
    elif discount_pct >= 15.0:
        deal_rating = "great_deal"
        rationale = f"⭐ Great Deal: Listed at ${total_price:.2f} ({discount_pct:.1f}% discount vs ${fair_value:.2f} benchmark)."
    elif discount_pct >= 5.0:
        deal_rating = "good_deal"
        rationale = f"✨ Good Deal: Listed at ${total_price:.2f} with a {discount_pct:.1f}% discount."
    else:
        deal_rating = "avoid_price"
        rationale = f"Listing at ${total_price:.2f} is at or above estimated fair market value (${fair_value:.2f})."

    return {
        "deal_rating": deal_rating,
        "fair_value_estimate": fair_value,
        "discount_percentage": discount_pct,
        "rationale": rationale,
    }


def clean_json_response(text: str) -> Optional[Dict[str, Any]]:
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
    pricecharting_data: Optional[Dict[str, Any]] = None,
    pop_info: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Appraise a Raw card or Graded slab using Gemini AI with PriceCharting and Population context.
    Returns 4-tier deal rating: amazing_deal, great_deal, good_deal, avoid_price.
    """
    key = api_key or os.getenv("GEMINI_API_KEY", "")

    if not GENAI_AVAILABLE or not key or key == "your_gemini_api_key_here":
        return statistical_appraisal_fallback(listing, comparables, pricecharting_data)

    comp_summary = []
    for c in comparables[:10]:
        comp_summary.append(
            f"- {c.get('card_name', 'Vulpix')} [{c.get('condition_type', 'Graded')} / {c.get('grading_company', '')} {c.get('grade_label', '')}] sold/listed for ${c.get('total_price', 0):.2f}"
        )
    comps_text = "\n".join(comp_summary) if comp_summary else "None available yet."

    pc_text = "Not available"
    if pricecharting_data:
        pc_text = f"Raw: ${pricecharting_data.get('pricecharting_raw', 0):.2f} | Grade 9: ${pricecharting_data.get('pricecharting_grade9', 0):.2f} | PSA 10: ${pricecharting_data.get('pricecharting_grade10', 0):.2f}"

    pop_text = "Unknown"
    if pop_info:
        pop_text = f"PSA 10 Pop: {pop_info.get('pop_grade10', 'N/A')}, Pristine 10: {pop_info.get('pop_pristine10', 'N/A')}"

    prompt = f"""
You are an elite Pokémon TCG master appraiser specializing in Vulpix cards (Raw singles, PSA/CGC/BGS Grade 10s, Pristine 10s, and BGS Black Label 10s).
Evaluate this new eBay listing against recent market sales, PriceCharting aggregated benchmarks, and Population rarity:

NEW LISTING:
- Title: {listing.get('title')}
- Card: {listing.get('card_name')}
- Condition: {listing.get('condition_type')} ({listing.get('grading_company')} - {listing.get('grade_label')})
- Edition: {listing.get('edition')}
- Language: {listing.get('language')}
- Is Error Card: {'Yes' if listing.get('is_error') else 'No'}
- Total Price (Inc. Shipping): ${listing.get('total_price', 0):.2f}

PRICECHARTING AGGREGATED BENCHMARKS:
{pc_text}

POPULATION RARITY:
{pop_text}

RECENT COMPARABLE SALES:
{comps_text}

TASK:
1. Estimate true fair market value in USD. Factor in premiums for 1st Edition, Shadowless, Japanese vintage, Pristine 10 (~1.3x Gem Mint), Black Label 10 (~2.5x+ Gem Mint), and Low Population counts (Pop <= 20).
2. Calculate discount percentage vs fair market value.
3. Classify into EXACTLY one category:
   - "amazing_deal" (>=30% discount below fair value, or ultra-rare low-pop steal)
   - "great_deal" (15% to 29% discount)
   - "good_deal" (5% to 14% discount)
   - "avoid_price" (0% or overpriced)
4. Provide a concise 1-2 sentence market rationale.

Respond ONLY with valid JSON in this exact structure:
{{
  "deal_rating": "amazing_deal" | "great_deal" | "good_deal" | "avoid_price",
  "fair_value_estimate": 120.00,
  "discount_percentage": 32.5,
  "rationale": "1-2 sentence concise valuation rationale."
}}
"""

    try:
        genai.configure(api_key=key)
        try:
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(prompt)
        except Exception:
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)

        parsed = clean_json_response(response.text)
        if parsed and "deal_rating" in parsed:
            rating = parsed.get("deal_rating", "").lower()
            if rating not in ["amazing_deal", "great_deal", "good_deal", "avoid_price"]:
                rating = "good_deal" if parsed.get("discount_percentage", 0) > 10 else "avoid_price"

            return {
                "deal_rating": rating,
                "fair_value_estimate": float(parsed.get("fair_value_estimate", listing.get("total_price", 0))),
                "discount_percentage": float(parsed.get("discount_percentage", 0.0)),
                "rationale": parsed.get("rationale", "AI appraisal completed."),
            }
    except Exception as e:
        print(f"[Appraiser] Gemini API error: {e}. Utilizing fallback calculation.")

    return statistical_appraisal_fallback(listing, comparables, pricecharting_data)
