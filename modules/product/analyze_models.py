from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class AnalyzeRequest(BaseModel):
    raw_data: Dict[str, Any]
    source: str = ""

class AnalyzeResponse(BaseModel):
    tus_ready: bool
    products: List[Dict[str, Any]]
    count: int
    timestamp: str
    error: Optional[str] = None

class BatchAnalyzeRequest(BaseModel):
    raw_data_list: List[Dict[str, Any]]
    source: str = ""
    filters: Optional[Dict[str, Any]] = None

class BatchAnalyzeResponse(BaseModel):
    tus_ready: bool
    products: List[Dict[str, Any]]
    count: int
    timestamp: str
    error: Optional[str] = None

class ExportResponse(BaseModel):
    tus_ready: bool
    products: List[Dict[str, Any]]
    count: int
    timestamp: str

# ──────────────────────────────────────────────
# From-Scrape (Scraper → Analyzer pipeline)
# ──────────────────────────────────────────────

class AnalyzeFromScrapeRequest(BaseModel):
    """Analyze from previously scraped products. Choose products by filters."""
    source_site: Optional[str] = None         # tiktok, shopee, lazada, amazon, facebook
    seller_name: Optional[str] = None          # filter by seller
    limit: int = 50
    min_rating: float = 0.0
    skip_enrich: bool = False                  # skip AI enrichment?

class AnalyzeFromScrapeResponse(BaseModel):
    success: bool
    count: int
    products: List[Dict[str, Any]] = []
    skipped: int = 0
    message: str = ""


class ScrapedProductListItem(BaseModel):
    """Lightweight scraped product list item for Dashboard"""
    id: str
    name: str
    price: Optional[float] = None
    currency: str = "THB"
    source_site: str = ""
    sku: str = ""
    scraped_at: Optional[str] = None
    has_analyzed: bool = False

class ScrapedProductListResponse(BaseModel):
    success: bool
    products: List[ScrapedProductListItem] = []
    total: int = 0
    sources: List[str] = []
