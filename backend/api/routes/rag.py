"""RAG test routes — kept from Step 3."""

from fastapi import APIRouter, Query

from rag.retrieval import retrieve_relevant_law, retrieve_for_policy_category
from rag.store import get_collection_stats

router = APIRouter(prefix="/rag")


@router.get("/stats")
async def rag_stats():
    return get_collection_stats()


@router.get("/test")
async def rag_test(
    query: str = Query(...),
    category: str = Query(None),
    top_k: int = Query(8, ge=1, le=20),
):
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
