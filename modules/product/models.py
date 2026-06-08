"""Product scraper data models"""
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict

class ScrapeRequest(BaseModel):
    url: str
    use_vision: bool = True  # Use Gemini Vision as fallback
    proxy: Optional[str] = None  # Specific proxy (e.g. "http://user:pass@ip:port")
    rotate_proxy: bool = True    # Auto-rotate from PROXY_LIST if no proxy specified

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


class BatchScrapeItem(BaseModel):
    url: str
    use_vision: bool = True


class BatchScrapeRequest(BaseModel):
    items: List[BatchScrapeItem]
    max_concurrent: int = 5
    notify_on_complete: bool = False


class BatchScrapeResponse(BaseModel):
    success: bool
    batch_id: str
    total: int
    completed: int
    results: List[dict] = []
    error: Optional[str] = None


class ExportToPipelineRequest(BaseModel):
    product_ids: List[str] = []
    limit: int = 10
    hook: Optional[str] = None
    cta: Optional[str] = None
    duration: int = 10


class ExportToPipelineResponse(BaseModel):
    success: bool
    jobs: List[dict] = []
    error: Optional[str] = None


class ScheduledScrapeCreate(BaseModel):
    name: str
    urls: List[str]
    schedule: str = "daily"
    export_to_pipeline: bool = False


class ScheduledScrapeResponse(BaseModel):
    success: bool
    id: str
    name: str
    urls: List[str]
    schedule: str
    status: str
    next_run: Optional[str] = None
    last_run: Optional[str] = None
    error: Optional[str] = None


class ProductCategory(BaseModel):
    category: str
    confidence: float
    subcategory: Optional[str] = None


# ─── Batch Scrape ───────────────────────────────────────────────────

class BatchScrapeItem(BaseModel):
    url: str
    use_vision: bool = True

class BatchScrapeRequest(BaseModel):
    items: List[BatchScrapeItem]
    max_concurrent: int = 5
    notify_on_complete: bool = False

class BatchScrapeResponse(BaseModel):
    success: bool
    batch_id: str
    total: int
    completed: int
    results: List[dict] = []
    error: Optional[str] = None


# ─── Export to Pipeline ─────────────────────────────────────────────

class ExportToPipelineRequest(BaseModel):
    product_ids: List[str] = []
    limit: int = 10
    hook: Optional[str] = None
    cta: Optional[str] = None
    duration: int = 10

class ExportToPipelineResponse(BaseModel):
    success: bool
    jobs: List[dict] = []
    error: Optional[str] = None


# ─── Scheduled Scrape ───────────────────────────────────────────────

class ScheduledScrapeCreate(BaseModel):
    name: str
    urls: List[str]
    schedule: str = "daily"  # hourly, daily, weekly, monthly
    export_to_pipeline: bool = False

class ScheduledScrapeResponse(BaseModel):
    success: bool
    id: str
    name: str
    urls: List[str]
    schedule: str
    status: str
    next_run: Optional[str] = None
    last_run: Optional[str] = None
    error: Optional[str] = None


# ─── Category Detection ─────────────────────────────────────────────

class ProductCategory(BaseModel):
    category: str
    confidence: float
    subcategory: Optional[str] = None
