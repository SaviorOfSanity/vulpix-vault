"""Pydantic schemas for The Vulpix Vault API."""

from __future__ import annotations

from typing import Any, List, Optional
from pydantic import BaseModel, Field


class VisualCallout(BaseModel):
    x: float = Field(..., ge=0, le=100, description="Left offset % on card image")
    y: float = Field(..., ge=0, le=100, description="Top offset % on card image")
    w: float = Field(..., ge=1, le=100, description="Width % on card image")
    h: float = Field(..., ge=1, le=100, description="Height % on card image")
    label: str
    detail: str = ""
    severity: str = "error"  # "error" | "verify" | "stamp"


class VaultItemCreate(BaseModel):
    catalog_key: Optional[str] = None
    card_name: str
    set_name: str
    card_number: str = ""
    language: str = "English"
    edition: str = "Unlimited"
    is_raw: bool = True
    grading_company: str = "RAW"
    grade: float = 0.0
    grade_label: str = "Raw Single"
    cert_number: str = ""
    purchase_price: float = 0.0
    purchase_date: str = ""
    image_url: str = ""
    notes: str = ""


class VaultItemUpdate(BaseModel):
    catalog_key: Optional[str] = None
    card_name: Optional[str] = None
    set_name: Optional[str] = None
    card_number: Optional[str] = None
    language: Optional[str] = None
    edition: Optional[str] = None
    is_raw: Optional[bool] = None
    grading_company: Optional[str] = None
    grade: Optional[float] = None
    grade_label: Optional[str] = None
    cert_number: Optional[str] = None
    purchase_price: Optional[float] = None
    purchase_date: Optional[str] = None
    image_url: Optional[str] = None
    notes: Optional[str] = None


class PriceOverrideIn(BaseModel):
    price_raw: Optional[float] = None
    price_grade9: Optional[float] = None
    price_grade10: Optional[float] = None
    pricecharting_url: Optional[str] = None
    tcgplayer_url: Optional[str] = None
    unlock_auto_pricing: bool = False


class CustomCardCreate(BaseModel):
    card_name: str
    set_name: str
    card_number: str = ""
    release_year: int = 2000
    release_date: str = ""
    language: str = "English"
    edition: str = "Unlimited"
    rarity: str = "Common"
    artist: str = "Ken Sugimori"
    is_error: bool = False
    error_description: str = ""
    image_url: str = ""
    notes: str = ""


class SyncJobRequest(BaseModel):
    only_unpriced: bool = True
    languages: Optional[List[str]] = None
    limit: Optional[int] = None


# =============================================================
# Phase 2: eBay Auction Radar & Alerts Models
# =============================================================

class RadarSettingsUpdate(BaseModel):
    ebay_client_id: Optional[str] = None
    ebay_client_secret: Optional[str] = None
    ebay_env: Optional[str] = None  # "production" | "sandbox"
    ebay_marketplace: Optional[str] = None  # default "EBAY_US"
    auto_scan_enabled: Optional[bool] = None
    auto_scan_interval_min: Optional[int] = None
    alert_min_discount_pct: Optional[int] = None
    alert_ending_soon_min: Optional[int] = None
    alert_needed_only: Optional[bool] = None
    gotify_url: Optional[str] = None
    gotify_token: Optional[str] = None
    discord_webhook_url: Optional[str] = None
    ntfy_url: Optional[str] = None


class RadarQueryCreate(BaseModel):
    query: str
    label: str = ""
    buying_filter: str = "ALL"  # "ALL" | "AUCTION" | "FIXED_PRICE"


class RadarQueryToggle(BaseModel):
    enabled: bool


class TrackAuctionRequest(BaseModel):
    url: str
    title: str = ""
    current_price: Optional[float] = None
    shipping_cost: Optional[float] = None
    end_time: str = ""  # ISO UTC or minutes from now if omitted
    minutes_remaining: Optional[int] = None
    buying_option: str = "AUCTION"
    catalog_key: Optional[str] = None


class ListingActionUpdate(BaseModel):
    is_watched: Optional[bool] = None
    is_dismissed: Optional[bool] = None
    catalog_key: Optional[str] = None
    current_price: Optional[float] = None
    shipping_cost: Optional[float] = None
    end_time: Optional[str] = None


class ListingWonRequest(BaseModel):
    purchase_price: Optional[float] = None
    cert_number: str = ""
    notes: str = ""
