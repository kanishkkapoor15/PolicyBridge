"""FastAPI route definitions."""

from fastapi import APIRouter, Query

from models.rag import RetrievalResult
from rag.retrieval import retrieve_relevant_law, retrieve_for_policy_category
from rag.store import get_collection_stats

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "PolicyBridge"}


@router.get("/rag/stats")
async def rag_stats():
    """Return knowledge base ingestion statistics."""
    return get_collection_stats()


@router.get("/rag/test")
async def rag_test(
    query: str = Query(..., description="Search query"),
    category: str = Query(None, description="Policy category filter"),
    top_k: int = Query(8, ge=1, le=20),
) -> dict:
    """Test RAG retrieval — returns ranked results with scores and sources."""
    if category:
        results = retrieve_for_policy_category(category, query, top_k=top_k)
    else:
        results = retrieve_relevant_law(query, top_k=top_k)

    return {
        "query": query,
        "category": category,
        "result_count": len(results),
        "results": [r.model_dump() for r in results],
    }
