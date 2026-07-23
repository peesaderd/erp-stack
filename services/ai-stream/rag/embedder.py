"""
Embeddings provider — ใช้ Cloudflare Workers AI (ฟรี) เป็นหลัก
Fallback ไป sentence-transformers (local CPU)
"""
import os
import json
import hashlib
from typing import List
import httpx
from dotenv import load_dotenv

load_dotenv()

CLOUDFLARE_TOKEN = os.getenv("CLOUDFLARE_AI_TOKEN")
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_EMBED_MODEL = os.getenv("CLOUDFLARE_EMBED_MODEL", "@cf/baai/bge-small-en-v1.5")
EMBED_BASE = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run"

# Cache embeddings to avoid re-compute
_embed_cache: dict[str, list[float]] = {}


def _cache_key(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


async def embed_texts(texts: List[str]) -> List[List[float]]:
    """Batch embed texts using Cloudflare Workers AI (free)."""
    uncached = []
    indices = []
    results = [None] * len(texts)

    for i, t in enumerate(texts):
        ck = _cache_key(t)
        if ck in _embed_cache:
            results[i] = _embed_cache[ck]
        else:
            uncached.append(t)
            indices.append(i)

    if uncached:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{EMBED_BASE}/{CLOUDFLARE_EMBED_MODEL}",
                    headers={"Authorization": f"Bearer {CLOUDFLARE_TOKEN}"},
                    json={"text": uncached},
                )
                data = resp.json()
                if data.get("success"):
                    embeddings = data["result"]["data"]
                    for idx, emb in zip(indices, embeddings):
                        _embed_cache[_cache_key(texts[idx])] = emb
                        results[idx] = emb
                else:
                    # Fallback to local
                    return await _fallback_embed(texts)
        except Exception:
            return await _fallback_embed(texts)

    return [r for r in results if r is not None]


async def _fallback_embed(texts: List[str]) -> List[List[float]]:
    """CPU-based fallback using sentence-transformers."""
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
    embeddings = model.encode(texts, show_progress_bar=False)
    return [emb.tolist() for emb in embeddings]


async def embed_text(text: str) -> List[float]:
    """Single text embed."""
    return (await embed_texts([text]))[0]
