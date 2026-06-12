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