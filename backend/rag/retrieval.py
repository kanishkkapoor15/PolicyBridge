"""RAG retrieval functions for querying the legal knowledge base."""

import logging

from models.rag import RetrievalResult
from rag.store import get_collection

logger = logging.getLogger(__name__)

# Maps policy categories to the relevant legal frameworks (by source_file stem)
CATEGORY_FRAMEWORK_MAP: dict[str, list[str]] = {
    "hr_employment": [
        "irish_employment_equality_acts",
        "organisation_working_time_act",
        "gdpr",
        "dpc_guidance",
    ],
    "data_protection": [
        "gdpr",
        "data_protection_act_2018",
        "dpc_guidance",
    ],
    "it_security": [
        "nis2_directive",
        "gdpr",
        "eu_ai_act",
    ],
    "corporate_governance": [
        "companies_act_2014",
        "gdpr",
    ],
    "health_safety": [
        "organisation_working_time_act",
        "irish_employment_equality_acts",
    ],
}


def retrieve_relevant_law(
    query: str,
    frameworks: list[str] | None = None,
    top_k: int = 8,
) -> list[RetrievalResult]:
    """Retrieve relevant legal chunks for a query, optionally filtered by framework."""
    collection = get_collection()

    where_filter = None
    if frameworks:
        # Filter by source_file matching any of the framework stems
        source_files = [f"{fw}.md" for fw in frameworks]
        if len(source_files) == 1:
            where_filter = {"source_file": source_files[0]}
        else:
            where_filter = {"source_file": {"$in": source_files}}

    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

    retrieval_results = []
    if results["documents"] and results["documents"][0]:
        for doc, meta, distance in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            # ChromaDB cosine distance: 0 = identical, 2 = opposite
            # Convert to similarity score: 1 - (distance / 2)
            similarity = 1.0 - (distance / 2.0)
            retrieval_results.append(
                RetrievalResult(
                    chunk_text=doc,
                    source_framework=meta.get("framework_name", ""),
                    section_title=meta.get("section_title", ""),
                    relevance_score=round(similarity, 4),
                    source_file=meta.get("source_file", ""),
                )
            )

    return retrieval_results


def retrieve_for_policy_category(
    category: str,
    query: str,
    top_k: int = 8,
) -> list[RetrievalResult]:
    """Retrieve legal context filtered to frameworks relevant to a policy category."""
    frameworks = CATEGORY_FRAMEWORK_MAP.get(category)
    if not frameworks:
        logger.warning(f"Unknown category '{category}', retrieving from all frameworks")
    return retrieve_relevant_law(query, frameworks=frameworks, top_k=top_k)
