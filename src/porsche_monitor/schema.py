from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List, Dict


class Listing(BaseModel):
    source: str
    source_id: str
    url: str
    title: str
    price_eur: Optional[int] = None
    mileage_km: Optional[int] = None
    first_registration: Optional[str] = None
    year: Optional[int] = None
    location: Optional[str] = None
    accident_free: Optional[bool] = None
    porsche_approved_months: Optional[int] = None
    owners: Optional[int] = None
    generation: Optional[str] = None
    body_type: Optional[str] = None
    variant: Optional[str] = None
    options_text: str = ""
    options_list: List[str] = Field(default_factory=list)
    status: Optional[str] = None
    image_url: Optional[str] = None
    dealer_name: Optional[str] = None
    raw: Dict = Field(default_factory=dict)


class FilterResult(BaseModel):
    listing: Listing
    is_match: bool
    score: int = 0
    must_have_missing: List[str] = Field(default_factory=list)
    nice_to_have_present: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    detected: Dict[str, bool] = Field(default_factory=dict)


class ChangeInfo(BaseModel):
    is_new: bool = False
    is_changed: bool = False
    changes: Dict[str, tuple] = Field(default_factory=dict)
    previous_price: Optional[int] = None
    previous_status: Optional[str] = None
