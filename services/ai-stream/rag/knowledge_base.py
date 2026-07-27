"""
Knowledge ingestion — ดึงข้อมูลจาก BookStack เข้า ChromaDB
"""
import os
import hashlib
from typing import List
import httpx
from dotenv import load_dotenv

from .vector_store import add_documents, get_stats

load_dotenv()

BOOKSTACK_URL = os.getenv("BOOKSTACK_URL", "http://89.167.82.205:54515")
BOOKSTACK_TOKEN_ID = os.getenv("BOOKSTACK_TOKEN_ID", "")
BOOKSTACK_TOKEN_SECRET = os.getenv("BOOKSTACK_TOKEN_SECRET", "")

CHUNK_SIZE = 500  # characters per chunk
CHUNK_OVERLAP = 50


def _headers():
    return {
        "Authorization": f"Token {BOOKSTACK_TOKEN_ID}:{BOOKSTACK_TOKEN_SECRET}",
        "Content-Type": "application/json",
    }


def _chunk_text(text: str, source: str, metadata: dict) -> List[dict]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk_text = text[start:end]
        chunk_id = hashlib.md5(f"{source}:{start}".encode()).hexdigest()
        chunks.append({
            "id": chunk_id,
            "text": chunk_text,
            "title": metadata.get("title", ""),
            "metadata": {
                **metadata,
                "chunk_start": start,
                "source": source,
            },
        })
        start += CHUNK_SIZE - CHUNK_OVERLAP
        if start >= len(text):
            break
    return chunks


async def sync_from_bookstack() -> dict:
    """Pull all pages from BookStack and add to vector store.
    Uses /api/pages endpoint with per-book filtering.
    """
    result = {"synced": 0, "errors": 0, "pages": 0}
    import re
    
    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        # 1. Get all books first (for metadata)
        books_resp = await client.get(
            f"{BOOKSTACK_URL}/api/books",
            headers=_headers(),
        )
        if books_resp.status_code != 200:
            return {"error": f"BookStack API error: {books_resp.status_code}"}
        
        books = {b["id"]: b["name"] for b in books_resp.json().get("data", [])}
        
        # 2. Get all pages via /api/pages (flat endpoint)
        offset = 0
        total_pages = 0
        
        while True:
            pages_resp = await client.get(
                f"{BOOKSTACK_URL}/api/pages",
                headers=_headers(),
                params={"count": 100, "offset": offset},
            )
            if pages_resp.status_code != 200:
                result["errors"] += 1
                break
            
            data = pages_resp.json()
            pages = data.get("data", [])
            total_pages = data.get("total", 0)
            
            if not pages:
                break
            
            for page in pages:
                try:
                    # 3. Get page detail with HTML content
                    page_detail = await client.get(
                        f"{BOOKSTACK_URL}/api/pages/{page['id']}",
                        headers=_headers(),
                    )
                    if page_detail.status_code != 200:
                        continue
                    
                    html = page_detail.json().get("html", "")
                    text = re.sub(r"<[^>]+>", " ", html)
                    text = re.sub(r"\s+", " ", text).strip()
                    
                    if not text:
                        continue
                    
                    book_id = page.get("book_id", 0)
                    metadata = {
                        "book": books.get(book_id, f"Book {book_id}"),
                        "page_id": page["id"],
                        "page_slug": page.get("slug", ""),
                        "updated_at": page.get("updated_at", ""),
                    }
                    
                    chunks = _chunk_text(
                        text,
                        source=f"bookstack:page:{page['id']}",
                        metadata=metadata,
                    )
                    
                    if chunks:
                        await add_documents(chunks)
                        result["synced"] += len(chunks)
                        result["pages"] += 1
                        
                except Exception as e:
                    result["errors"] += 1
            
            offset += len(pages)
            if offset >= total_pages:
                break
    
    stats = get_stats()
    result["total_docs"] = stats["document_count"]
    return result


async def sync_single_page(page_id: int) -> dict:
    """Sync a single BookStack page by ID."""
    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        resp = await client.get(
            f"{BOOKSTACK_URL}/api/pages/{page_id}",
            headers=_headers(),
        )
        if resp.status_code != 200:
            return {"error": f"Page not found: {resp.status_code}"}
        
        data = resp.json()
        import re
        text = re.sub(r"<[^>]+>", " ", data.get("html", ""))
        text = re.sub(r"\s+", " ", text).strip()
        
        if not text:
            return {"error": "Empty page"}
        
        chunks = _chunk_text(text, source=f"bookstack:page:{page_id}", metadata={
            "book": data.get("book_name", ""),
            "page_id": page_id,
            "page_slug": data.get("slug", ""),
        })
        
        if chunks:
            await add_documents(chunks)
        
        return {"synced": len(chunks), "page": data.get("name", "")}
