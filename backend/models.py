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
