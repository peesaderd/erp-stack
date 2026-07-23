"""
ChromaDB vector store — persistent, CPU-only, ~50MB RAM
"""
import os
import uuid
from typing import List, Optional
import chromadb
import chromadb.errors
from chromadb.config import Settings
from dotenv import load_dotenv

from .embedder import embed_texts

load_dotenv()

PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "data/chroma")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "ai_stream_kb")
TOP_K = int(os.getenv("TOP_K", "5"))

_client = None
_collection = None


def _get_client():
    global _client
    if _client is None:
        os.makedirs(PERSIST_DIR, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=PERSIST_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def _get_collection():
    global _collection
    if _collection is None:
        client = _get_client()
        # Try get or create
        try:
            _collection = client.get_collection(COLLECTION_NAME)
        except (ValueError, chromadb.errors.NotFoundError):
            _collection = client.create_collection(COLLECTION_NAME)
    return _collection


async def add_documents(docs: List[dict]):
    """Add documents to vector store.
    
    Each doc: {"id": str, "text": str, "metadata": dict, "title": str}
    """
    collection = _get_collection()
    
    texts = [d["text"] for d in docs]
    embeddings = await embed_texts(texts)
    
    ids = []
    metadatas = []
    documents = []
    
    for i, doc in enumerate(docs):
        doc_id = doc.get("id", str(uuid.uuid4()))
        ids.append(doc_id)
        documents.append(doc["text"])
        meta = doc.get("metadata", {})
        meta["title"] = doc.get("title", "")
        metadatas.append(meta)
    
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
    )
    return len(docs)


async def search(query: str, k: int = TOP_K) -> List[dict]:
    """Search vector store, return top-k chunks."""
    collection = _get_collection()
    query_embedding = await embed_texts([query])
    
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=k,
    )
    
    hits = []
    if results["ids"] and results["ids"][0]:
        for i in range(len(results["ids"][0])):
            hits.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "score": results["distances"][0][i] if results["distances"] else 0,
            })
    return hits


def get_stats() -> dict:
    """Get collection stats."""
    collection = _get_collection()
    count = collection.count()
    return {"collection": COLLECTION_NAME, "document_count": count}


def clear_all():
    """Reset collection."""
    global _collection
    client = _get_client()
    try:
        client.delete_collection(COLLECTION_NAME)
    except ValueError:
        pass
    _collection = None
