"""Product scraper data models"""
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict

class ScrapeRequest(BaseModel):
    url: str
    use_vision: bool = True  # Use Gemini Vision as fallback

class ProductData(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    currency: str = "THB"
    images: List[str] = []
    description: Optional[str] = None
    sku: Optional[str] = None
    brand: Optional[str] = None
    source_url: str = ""
    source_site: str = ""

class ScrapeResponse(BaseModel):
    success: bool
    method: str  # "playwright" | "vision" | "failed"
    product: Optional[ProductData] = None
    error: Optional[str] = None
